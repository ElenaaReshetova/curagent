"""Human Checkpoint validation and state transitions."""

from __future__ import annotations

from typing import Any

from src.platform.human_checkpoints.models import HumanCheckpointRecord

ALLOWED_TRANSITIONS = {
    "CREATED": {"OPEN", "CANCELLED"},
    "OPEN": {"ASSIGNED", "IN_REVIEW", "EXPIRED", "ESCALATED", "CANCELLED"},
    "ASSIGNED": {"IN_REVIEW", "OPEN", "ESCALATED", "CANCELLED"},
    "IN_REVIEW": {"APPROVED", "REJECTED", "CHANGES_REQUESTED", "INPUT_PROVIDED", "ESCALATED"},
    "ESCALATED": {"ASSIGNED", "IN_REVIEW", "APPROVED", "REJECTED", "CHANGES_REQUESTED", "CANCELLED"},
    "APPROVED": set(),
    "REJECTED": set(),
    "CHANGES_REQUESTED": set(),
    "INPUT_PROVIDED": set(),
    "EXPIRED": set(),
    "CANCELLED": set(),
    "SUPERSEDED": set(),
}

TERMINAL = {"APPROVED", "REJECTED", "CHANGES_REQUESTED", "INPUT_PROVIDED", "EXPIRED", "CANCELLED", "SUPERSEDED"}


def can_transition(current: str, target: str) -> bool:
    """Return True only for an allowed forward transition (not idempotent self-loops)."""
    return target in ALLOWED_TRANSITIONS.get(current, set())


def validate_record(record: HumanCheckpointRecord) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not record.title:
        errors.append({"code": "TITLE_REQUIRED", "message": "Checkpoint title is required"})
    if not record.execution_id:
        errors.append({"code": "EXECUTION_REQUIRED", "message": "Execution reference is required"})
    if not record.question:
        warnings.append({"code": "QUESTION_MISSING", "message": "Review question is empty"})
    if record.status in TERMINAL and not record.selected_decision:
        warnings.append({"code": "DECISION_MISSING", "message": "Terminal checkpoint is missing recorded decision"})
    if record.status == "ESCALATED" and not record.escalated:
        warnings.append({"code": "ESCALATION_FLAG", "message": "Escalated checkpoint flag not set"})

    valid = not errors
    return {
        "valid": valid,
        "status": "valid" if valid and not warnings else ("warning" if valid else "invalid"),
        "errors": errors,
        "warnings": warnings,
    }
