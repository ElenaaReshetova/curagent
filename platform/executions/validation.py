"""Execution state validation (MVP)."""

from __future__ import annotations

from typing import Any

from src.platform.executions.models import ExecutionRecord

TERMINAL = {"COMPLETED", "COMPLETED_WITH_WARNINGS", "CANCELLED", "FAILED", "TIMED_OUT"}


def validate_record(record: ExecutionRecord) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not record.title:
        errors.append({"code": "TITLE_REQUIRED", "message": "Execution title is required"})
    if record.execution_type == "FLOW" and not record.flow_name:
        warnings.append({"code": "FLOW_MISSING", "message": "Flow name not set for FLOW execution"})
    if record.status in TERMINAL and record.progress_pct < 100 and record.status == "COMPLETED":
        warnings.append({"code": "PROGRESS_MISMATCH", "message": "Completed execution has progress < 100%"})

    valid = len(errors) == 0
    return {
        "valid": valid,
        "status": "valid" if valid and not warnings else ("warning" if valid else "invalid"),
        "errors": errors,
        "warnings": warnings,
    }
