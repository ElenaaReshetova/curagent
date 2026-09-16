"""Normalize workflow DSL — strip designer/service fields before Temporal parse.

workflows have no End node: execution stops at leaf actions / branches.
END nodes are dropped. SUBFLOW is kept as a platform child-run node
(target e2e scenario or PDLC stage).

Removes:
  - ui / positions / canvas metadata
  - platform-only keys (_*, testOutputs, …)
  - END nodes and any connections that touch them

Keeps action fields: identifier, title, description, icon, config,
variables, links, verbose, connections (incl. sourceOptionIdentifier).
"""

from __future__ import annotations

from typing import Any

from src.platform.graphs.workflow_dsl import DslConnection, DslNode, WorkflowDsl, parse_workflow_dsl

# Keys never forwarded into Temporal step configs
_STRIP_CONFIG_KEYS = {
    "testOutputs",
    "test_outputs",
    "_source",
    "skill_keys",  # platform glue — agentIdentifier is field
    "skill_key",
    "rule_keys",
    "gate_mode",
    "plan",
    "plan_embedded",
    "assigneeExpr",
    "artifact_name",
    "question",
}

_PORT_ACTION_TYPES = {
    "SELF_SERVE_TRIGGER",
    "EVENT_TRIGGER",
    "SCHEDULE_TRIGGER",
    "WEBHOOK",
    "KAFKA",
    "UPSERT_ENTITY",
    "INTEGRATION_ACTION",
    "INTERNAL_SERVICE",
    "AI",
    "AI_AGENT",
    "CONDITION",
    "INPUT",
    "SUBFLOW",
}

_SUBFLOW_KEYS = {"playbook_key", "flow_key", "graph_key", "graph_kind", "graph_id", "input"}


def normalize_workflow_dsl(raw: dict[str, Any] | WorkflowDsl | str) -> WorkflowDsl:
    """Return a clean workflow ready for Temporal parsing."""
    doc = raw if isinstance(raw, WorkflowDsl) else parse_workflow_dsl(raw)

    nodes: list[DslNode] = []
    dropped: set[str] = set()
    for n in doc.nodes:
        cfg = _clean_config(dict(n.config or {}))
        cfg_type = str(cfg.get("type") or "").upper()
        if cfg_type == "END" or not cfg_type:
            # No END node; drop empty/unknown terminals
            if cfg_type == "END" or str(n.title or "").strip().lower() == "end":
                dropped.add(n.identifier)
                continue
        if cfg_type == "SUBFLOW":
            key = (
                cfg.get("graph_key")
                or cfg.get("flow_key")
                or cfg.get("playbook_key")
                or cfg.get("graph_id")
                or ""
            )
            if key:
                cfg["graph_key"] = key
            cfg.setdefault("graph_kind", "e2e")
            cfg["type"] = "SUBFLOW"
        if cfg_type == "CONDITION":
            cfg = _condition_options(cfg)
        nodes.append(DslNode(
            identifier=n.identifier.strip(),
            title=(n.title or n.identifier).strip(),
            icon=n.icon,
            description=n.description,
            config=cfg,
            variables=n.variables if n.variables else None,
            links=[x for x in (n.links or []) if x][:3] or None,
            verbose=n.verbose if n.verbose else None,
        ))

    keep = {n.identifier for n in nodes}
    by_type = {
        n.identifier: str((n.config or {}).get("type") or "").upper()
        for n in nodes
    }

    connections: list[DslConnection] = []
    seen: set[tuple[str, str, str | None, str | None, bool]] = set()
    for c in doc.connections:
        if c.sourceIdentifier in dropped or c.targetIdentifier in dropped:
            continue
        if c.sourceIdentifier not in keep or c.targetIdentifier not in keep:
            continue
        option = c.sourceOptionIdentifier
        outlet = c.sourceOutletIdentifier
        # CONDITION branches use sourceOptionIdentifier; INPUT uses outlets
        src_type = by_type.get(c.sourceIdentifier, "")
        if src_type == "CONDITION":
            option = option or outlet
            outlet = None
        elif src_type in {"INPUT", "INTERNAL_SERVICE"}:
            outlet = outlet or option
            option = None
        key = (
            c.sourceIdentifier,
            c.targetIdentifier,
            outlet,
            option,
            bool(c.fallback),
        )
        if key in seen:
            continue
        seen.add(key)
        connections.append(DslConnection(
            sourceIdentifier=c.sourceIdentifier,
            targetIdentifier=c.targetIdentifier,
            sourceOutletIdentifier=outlet,
            sourceOptionIdentifier=option,
            fallback=bool(c.fallback),
        ))

    return WorkflowDsl(
        identifier=doc.identifier.strip(),
        title=(doc.title or doc.identifier).strip(),
        description=(doc.description or "").strip(),
        produces=[str(p) for p in (doc.produces or []) if p],
        nodes=nodes,
        connections=connections,
        ui=None,  # always stripped
    )


def _condition_options(cfg: dict[str, Any]) -> dict[str, Any]:
    """CONDITION branches use ``options`` only."""
    options = cfg.get("options") if isinstance(cfg.get("options"), list) else []
    cfg = {**cfg, "options": [o for o in options if isinstance(o, dict) and o.get("identifier")]}
    cfg.pop("outlets", None)
    cfg.pop("outcomes", None)
    return cfg


def _clean_config(cfg: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in cfg.items():
        if k in _STRIP_CONFIG_KEYS or k.startswith("_"):
            continue
        if v is None or v == "" or v == [] or v == {}:
            continue
        out[k] = v
    t = str(out.get("type") or "").upper()
    if not t and out.get("triggerType"):
        out["type"] = str(out.pop("triggerType")).upper()
        t = str(out["type"]).upper()
    elif t:
        out["type"] = t
    if t != "SUBFLOW":
        for k in _SUBFLOW_KEYS:
            out.pop(k, None)
    if t == "END":
        out["type"] = "END"
    return out
