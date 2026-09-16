"""Shared step helpers for local and Temporal runners."""

from __future__ import annotations

from typing import Any, Optional

from src.orchestrator.activities_workflow import (
    ai_agent_execute,
    ai_generate_summary,
    execute_subflow,
    http_webhook,
    human_review,
    integration_action,
    internal_service,
    kafka_publish,
    upsert_entity,
)
from src.orchestrator.workflows.branch_expr import pick_condition_outlet
from src.platform.graphs.expressions import get_by_path, normalize_hitl_decision, render_templates
from src.platform.graphs.temporal_steps import ActivityStep, ConditionStep

ACTIVITY_FNS = {
    "http_webhook": http_webhook,
    "ai_generate_summary": ai_generate_summary,
    "ai_agent_execute": ai_agent_execute,
    "human_review": human_review,
    "internal_service": internal_service,
    "execute_subflow": execute_subflow,
    "kafka_publish": kafka_publish,
    "upsert_entity": upsert_entity,
    "integration_action": integration_action,
}


def map_step_outputs(step: ActivityStep, result: dict[str, Any]) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for m in step.output_mapping:
        mapped[m["name"]] = get_by_path(result, m["path"])
    mapped.update({k: v for k, v in result.items() if k not in mapped})
    return mapped


def route_hitl_outlets(step: ActivityStep, outputs: dict[str, Any]) -> Optional[str]:
    decision = normalize_hitl_decision(
        str(outputs.get("decision") or (outputs.get("signal") or {}).get("decision") or "")
    )
    for e in step.outlets:
        handle = str(e.get("sourceHandle") or "").strip().lower()
        if handle and handle == decision:
            return e.get("target")
        if decision == "approve" and handle in {"approve", "approved"}:
            return e.get("target")
        if decision in {"decline", "reject"} and handle in {"reject", "decline", "rejected"}:
            return e.get("target")
    if decision == "reject":
        return None
    return step.next_step


def eval_condition_step(
    step: ConditionStep,
    context: dict[str, Any],
    *,
    approvals: dict[str, Any] | None = None,
) -> Optional[str]:
    approvals = approvals or {}
    outlets = [{"identifier": b.id, "expression": b.expression} for b in step.branches]
    edges = [{"target": b.next_step, "sourceHandle": b.id} for b in step.branches if b.next_step]
    if step.fallback:
        edges.append({"target": step.fallback, "sourceHandle": "fallback", "fallback": True})
    expr_ctx = {
        "input": context.get("inputs") or {},
        "outputs": context.get("outputs") or {},
        "approvals": approvals,
    }
    nxt = pick_condition_outlet(outlets, edges, expr_ctx)
    if nxt:
        return nxt
    return step.fallback


def render_activity_input(
    step: ActivityStep,
    context: dict[str, Any],
    *,
    run_id: str,
) -> Any:
    rendered = render_templates(step.input, context)
    if isinstance(rendered, dict):
        return {
            **rendered,
            "run_id": run_id,
            "node_id": step.id,
            "outputs": context.get("outputs") or {},
            "inputs": context.get("inputs") or {},
            "secrets": context.get("secrets") or {},
            "secrets": context.get("secrets") or {},
        }
    return rendered
