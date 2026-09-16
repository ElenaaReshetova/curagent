"""Pure graph helpers for playbook skill / verify branching (no Temporal deps)."""

from __future__ import annotations

from typing import Optional, Protocol

from src.orchestrator.workflow_config.models import (
    StepType,
    WorkflowStepConfig,
    WorkflowTemplate,
)


class _HasRouting(Protocol):
    routing: object


def edge_matches_branch(label: Optional[str], branch: str) -> bool:
    if not label:
        return False
    bl = branch.lower().strip()
    ll = label.lower().strip()
    if ll == bl:
        return True
    if bl == "yes" and ll in ("yes", "да", "approve", "approved"):
        return True
    if bl == "no" and ll in ("no", "нет"):
        return True
    if bl in ("approve", "approved") and ll in ("approve", "approved", "yes", "да"):
        return True
    # Human «уточнить» — do not alias to binary No (that is Reject).
    if bl in ("request_changes", "changes_requested") and ll in (
        "request_changes",
        "changes_requested",
        "refine",
        "clarify",
        "changes",
    ):
        return True
    if bl in ("reject", "rejected") and ll in ("reject", "rejected", "no", "нет"):
        return True
    if ll == "default" and bl in ("general", "default"):
        return True
    return False


def next_step_id(template: WorkflowTemplate, from_id: str, branch: Optional[str] = None) -> Optional[str]:
    edges = [e for e in template.edges if e.from_step == from_id]
    if not edges:
        return None
    if branch:
        for e in edges:
            if edge_matches_branch(e.label, branch):
                return e.to_step
        for e in edges:
            if e.label and e.label.lower().strip() == "default":
                return e.to_step
        bl = branch.lower().strip()
        # Explicit human outcomes must not silently follow an unlabeled approve→publish edge.
        if bl in {
            "request_changes",
            "changes_requested",
            "clarify",
            "changes",
            "reject",
            "rejected",
        }:
            return None
        # Branch was requested but no edge matched — prefer unlabeled continuation,
        # never silently take the first labeled skill edge (that caused BRD fallback).
        for e in edges:
            if not e.label:
                return e.to_step
        return None
    for e in edges:
        if not e.label:
            return e.to_step
    return edges[0].to_step


def is_classify_step(step: WorkflowStepConfig) -> bool:
    st = StepType(step.type)
    if st == StepType.CLASSIFY:
        return True
    return st == StepType.SKILL and (step.skill_id or "") in ("classify", "classify-task")


def is_skill_router(step: WorkflowStepConfig) -> bool:
    if is_classify_step(step):
        return True
    if StepType(step.type) in (StepType.DECISION, StepType.GATEWAY_OR):
        return str(step.config.get("mode", "")).lower() in ("route_skill", "route_by_skill", "classify")
    return False


def resolve_skill_id(step: WorkflowStepConfig, ctx: _HasRouting) -> str:
    """Resolve playbook skill_id; `$routing` / `auto` reuse classifier decision."""
    raw = (step.skill_id or "").strip()
    if not raw:
        return "general"
    if raw in ("$routing", "from_routing", "auto"):
        routing = getattr(ctx, "routing", None)
        primary = getattr(routing, "primary_skill", None) if routing is not None else None
        return primary or "general"
    return raw
