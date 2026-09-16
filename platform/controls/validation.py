"""Control version validation."""

from __future__ import annotations

from typing import Any

from src.platform.controls.models import ControlVersion

FORBIDDEN_EXPRESSIONS = ("skip control", "bypass control", "disable control", "auto approve")


def validate_version(version: ControlVersion) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not version.expression.strip():
        errors.append({"code": "EXPRESSION_REQUIRED", "message": "Evaluation expression is required"})
    lowered = version.expression.lower()
    for token in FORBIDDEN_EXPRESSIONS:
        if token in lowered:
            errors.append({"code": "FORBIDDEN_EXPRESSION", "message": f"Expression contains forbidden phrase: {token}"})

    if version.enforcement_on_failed == "ALLOW_WITH_AUDIT" and version.severity == "CRITICAL":
        warnings.append({"code": "WEAK_ENFORCEMENT", "message": "Critical controls should not allow audit-only enforcement"})

    if not version.applicability:
        warnings.append({"code": "APPLICABILITY_EMPTY", "message": "No applicability conditions defined"})

    if version.control_type == "PUBLICATION_GATE" and version.enforcement_on_failed not in ("BLOCK", "REQUIRE_HUMAN_APPROVAL"):
        warnings.append({"code": "PUBLICATION_ENFORCEMENT", "message": "Publication gates usually block or require approval"})

    valid = not errors
    return {
        "valid": valid,
        "status": "valid" if valid and not warnings else ("warning" if valid else "invalid"),
        "errors": errors,
        "warnings": warnings,
    }
