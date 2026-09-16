"""Parse normalized workflow DSL → TemporalPlan (activity/condition steps).

workflow node type → Temporal worker is resolved from `node_types` +
`temporal_activities.worker` (fallback: activity_catalog.DEFAULT_BINDINGS).

  WEBHOOK            → http_webhook
  AI                 → ai_generate_summary
  AI_AGENT           → ai_agent_execute
  INPUT              → human_review (+ wait signal)
  CONDITION          → condition step (in-workflow; ``options``)
  INTERNAL_SERVICE   → internal_service
  SUBFLOW            → execute_subflow (child scenario / PDLC stage)
  KAFKA              → kafka_publish
  UPSERT_ENTITY      → upsert_entity
  INTEGRATION_ACTION → integration_action
  *TRIGGER           → trigger metadata + inputs (not a step)

No End node — leaf nodes with no outgoing edges terminate the run.
"""

from __future__ import annotations

from typing import Any, Optional

from src.platform.graphs.activity_catalog import resolve_worker
from src.platform.graphs.workflow_dsl import DslConnection, DslNode, WorkflowDsl
from src.platform.graphs.temporal_steps import (
    ActivityStep,
    ConditionBranch,
    ConditionStep,
    TemporalPlan,
)


def parse_workflow_to_temporal(doc: WorkflowDsl, *, version: str = "1.0") -> TemporalPlan:
    by_id = {n.identifier: n for n in doc.nodes}
    outgoing = _outgoing(doc.connections)

    trigger = doc.trigger_node()
    steps: dict[str, ActivityStep | ConditionStep] = {}
    order: list[str] = []

    for node in doc.nodes:
        cfg_type = str((node.config or {}).get("type") or "").upper()
        if cfg_type.endswith("TRIGGER") or cfg_type in {
            "SELF_SERVE_TRIGGER", "EVENT_TRIGGER", "SCHEDULE_TRIGGER",
        }:
            continue
        if cfg_type in {"END", ""}:
            # normalize should have dropped END; ignore if leftover
            continue
        if cfg_type == "CONDITION":
            steps[node.identifier] = _condition_step(node, outgoing.get(node.identifier, []))
            order.append(node.identifier)
            continue

        binding = resolve_worker(cfg_type)
        activity = (binding.worker if binding else "") or ""
        if not activity:
            raise ValueError(f"Unsupported workflow node type «{cfg_type}» on {node.identifier}")

        edges = outgoing.get(node.identifier, [])
        wait = bool(binding.wait_for_signal) if binding else activity == "human_review"
        steps[node.identifier] = ActivityStep(
            id=node.identifier,
            name=node.title or node.identifier,
            activity_name=activity,
            input=_activity_input(node, activity),
            output_mapping=_output_mapping(activity),
            wait_for_signal=wait,
            signal_name="review_decision" if wait else None,
            next_step=None if wait or _multi_outlet(edges) else _default_next(edges),
            on_failure=str((node.config or {}).get("onFailure") or "terminate"),
            outlets=_outlet_edges(edges),
            worker=activity,
        )
        order.append(node.identifier)

    order = _bfs_order(doc, trigger.identifier if trigger else None, order)

    return TemporalPlan(
        name=doc.title or doc.identifier,
        version=version,
        description=doc.description or "",
        trigger=_trigger_meta(trigger),
        inputs=_trigger_inputs(trigger),
        steps=steps,
        step_order=order,
    )


def _outgoing(conns: list[DslConnection]) -> dict[str, list[DslConnection]]:
    out: dict[str, list[DslConnection]] = {}
    for c in conns:
        out.setdefault(c.sourceIdentifier, []).append(c)
    return out


def _trigger_meta(trigger: Optional[DslNode]) -> dict[str, Any]:
    if not trigger:
        return {"type": "manual"}
    cfg = trigger.config or {}
    t = str(cfg.get("type") or "SELF_SERVE_TRIGGER").upper()
    if t == "EVENT_TRIGGER":
        event = cfg.get("event") if isinstance(cfg.get("event"), dict) else {}
        return {
            "type": "event",
            "event_type": event.get("type") or "ANY_ENTITY_CHANGE",
            "blueprint": event.get("blueprintIdentifier"),
            "condition": cfg.get("condition"),
            "identifier": trigger.identifier,
            "published": cfg.get("published", True),
        }
    if t == "SCHEDULE_TRIGGER":
        return {
            "type": "schedule",
            "cron": cfg.get("cron") or "0 9 * * 1-5",
            "identifier": trigger.identifier,
            "published": cfg.get("published", True),
        }
    return {
        "type": "self_serve",
        "userInputs": cfg.get("userInputs") or {},
        "identifier": trigger.identifier,
        "published": cfg.get("published", True),
    }


def _trigger_inputs(trigger: Optional[DslNode]) -> list[dict[str, Any]]:
    if not trigger:
        return []
    ui = (trigger.config or {}).get("userInputs") or {}
    props = ui.get("properties") if isinstance(ui, dict) else None
    if not isinstance(props, dict):
        return []
    required = set(ui.get("required") or [])
    return [
        {
            "name": key,
            "type": (schema or {}).get("type") or "string" if isinstance(schema, dict) else "string",
            "required": key in required,
            "description": (schema or {}).get("title") or "" if isinstance(schema, dict) else "",
        }
        for key, schema in props.items()
    ]


def _condition_step(node: DslNode, edges: list[DslConnection]) -> ConditionStep:
    cfg = node.config or {}
    options = cfg.get("options") or []
    by_option = {
        (c.sourceOptionIdentifier or c.sourceOutletIdentifier or ""): c.targetIdentifier
        for c in edges
        if (c.sourceOptionIdentifier or c.sourceOutletIdentifier)
    }
    branches: list[ConditionBranch] = []
    fallback: Optional[str] = None
    for c in edges:
        unlabeled = not (c.sourceOptionIdentifier or c.sourceOutletIdentifier)
        if c.fallback or unlabeled:
            fallback = c.targetIdentifier
    for o in options:
        if not isinstance(o, dict):
            continue
        oid = str(o.get("identifier") or "")
        if not oid:
            continue
        branches.append(ConditionBranch(
            id=oid,
            expression=str(o.get("expression") or ""),
            next_step=by_option.get(oid),
        ))
    if not branches:
        for c in edges:
            if c.fallback:
                continue
            oid = c.sourceOptionIdentifier or c.sourceOutletIdentifier or c.targetIdentifier
            branches.append(ConditionBranch(id=str(oid), expression="", next_step=c.targetIdentifier))
    return ConditionStep(id=node.identifier, name=node.title or node.identifier, branches=branches, fallback=fallback)


def _activity_input(node: DslNode, activity: str) -> dict[str, Any]:
    cfg = dict(node.config or {})
    if activity == "http_webhook":
        return {
            "url": cfg.get("url"),
            "method": cfg.get("method") or "POST",
            "headers": cfg.get("headers") or {},
            "body": cfg.get("body"),
            "synchronized": cfg.get("synchronized", True),
            "onTimeout": cfg.get("onTimeout") or "fail",
            "onFailure": cfg.get("onFailure") or "terminate",
            "verbose": bool(cfg.get("verbose") or node.verbose),
            "agent": bool(cfg.get("agent")),
        }
    if activity == "ai_generate_summary":
        return {
            "userPrompt": cfg.get("userPrompt") or "",
            "systemPrompt": cfg.get("systemPrompt"),
            "tools": cfg.get("tools") or [],
            "provider": cfg.get("provider"),
            "model": cfg.get("model"),
            "outputSchema": cfg.get("outputSchema"),
            "mcpServers": cfg.get("mcpServers"),
        }
    if activity == "ai_agent_execute":
        return {
            "agentIdentifier": cfg.get("agentIdentifier"),
            "userPrompt": cfg.get("userPrompt") or "",
            "outputSchema": cfg.get("outputSchema"),
        }
    if activity == "human_review":
        return {
            "description": cfg.get("description") or node.description or "",
            "userInputs": cfg.get("userInputs") or {},
            "outlets": cfg.get("outlets") or [],
            "responders": cfg.get("responders") or {},
            "notifications": cfg.get("notifications") or [],
            "title": node.title,
            "node_id": node.identifier,
        }
    if activity == "internal_service":
        payload = {
            "service": cfg.get("service"),
            "parameter": cfg.get("parameter") or {},
            "onTimeout": cfg.get("onTimeout") or "fail",
            "onFailure": cfg.get("onFailure") or "terminate",
            "verbose": bool(cfg.get("verbose") or node.verbose),
        }
        if cfg.get("governance") or str(cfg.get("service") or "") == "policy.evaluate":
            payload["governance"] = True
            payload["packs"] = cfg.get("packs") or []
            payload["produces"] = cfg.get("produces") or []
            payload["producer"] = cfg.get("producer") or ""
            payload["producer_ids"] = cfg.get("producer_ids") or []
        return payload
    if activity == "execute_subflow":
        return {
            "graph_id": cfg.get("graph_id"),
            "graph_key": cfg.get("graph_key") or cfg.get("flow_key") or cfg.get("playbook_key"),
            "graph_kind": cfg.get("graph_kind"),
            "input": cfg.get("input") or cfg.get("parameter") or {},
            "onFailure": cfg.get("onFailure") or "terminate",
        }
    if activity == "kafka_publish":
        return {"payload": cfg.get("payload"), "onFailure": cfg.get("onFailure") or "terminate"}
    if activity == "upsert_entity":
        return {
            "blueprintIdentifier": cfg.get("blueprintIdentifier"),
            "mapping": cfg.get("mapping") or {},
            "onFailure": cfg.get("onFailure") or "terminate",
        }
    if activity == "integration_action":
        return {
            "integrationProvider": cfg.get("integrationProvider"),
            "repo": cfg.get("repo"),
            "workflow": cfg.get("workflow"),
            "workflowInputs": cfg.get("workflowInputs") or {},
            "onFailure": cfg.get("onFailure") or "terminate",
        }
    return cfg


def _output_mapping(activity: str) -> list[dict[str, str]]:
    if activity == "http_webhook":
        return [
            {"name": "body", "path": "response.body"},
            {"name": "status", "path": "response.status"},
        ]
    if activity == "ai_generate_summary":
        return [{"name": "response", "path": "response.text"}]
    if activity == "ai_agent_execute":
        return [
            {"name": "result", "path": "response.result"},
            {"name": "text", "path": "response.text"},
        ]
    if activity == "human_review":
        return [
            {"name": "selectedOutlet", "path": "signal.selectedOutlet"},
            {"name": "responses", "path": "signal.responses"},
            {"name": "decision", "path": "signal.decision"},
            {"name": "reason", "path": "signal.reason"},
            {"name": "comment", "path": "signal.comment"},
            {"name": "inputs", "path": "signal.inputs"},
        ]
    if activity == "internal_service":
        return [
            {"name": "result", "path": "result"},
            {"name": "passed", "path": "passed"},
            {"name": "ok", "path": "ok"},
        ]
    return [{"name": "result", "path": "result"}]


def _outlet_edges(edges: list[DslConnection]) -> list[dict[str, Any]]:
    return [
        {
            "target": e.targetIdentifier,
            "sourceHandle": e.sourceOutletIdentifier or e.sourceOptionIdentifier,
            "fallback": e.fallback,
        }
        for e in edges
    ]


def _default_next(edges: list[DslConnection]) -> Optional[str]:
    for e in edges:
        if not e.fallback:
            return e.targetIdentifier
    return edges[0].targetIdentifier if edges else None


def _multi_outlet(edges: list[DslConnection]) -> bool:
    handles = {(e.sourceOutletIdentifier or e.sourceOptionIdentifier or "") for e in edges}
    handles.discard("")
    return len(handles) > 1


def _bfs_order(doc: WorkflowDsl, start: Optional[str], fallback: list[str]) -> list[str]:
    if not start:
        return list(fallback)
    adj: dict[str, list[str]] = {n.identifier: [] for n in doc.nodes}
    for c in doc.connections:
        adj.setdefault(c.sourceIdentifier, []).append(c.targetIdentifier)
    seen: set[str] = set()
    order: list[str] = []
    q = [start]
    actionable = set(fallback)
    while q:
        nid = q.pop(0)
        if nid in seen:
            continue
        seen.add(nid)
        if nid in actionable:
            order.append(nid)
        for nxt in adj.get(nid, []):
            if nxt not in seen:
                q.append(nxt)
    for nid in fallback:
        if nid not in order:
            order.append(nid)
    return order
