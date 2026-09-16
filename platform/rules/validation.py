"""Rule content validation (static MVP)."""

from __future__ import annotations

from typing import Any

from src.platform.rules.models import RuleVersion

PROHIBITED = (
    "mcp://", "mcp_server", "jira_", "confluence_", "notion_",
    "list_tools", "call_tool", "ignore previous instructions",
    "bypass control", "disable control", "skip approval",
    "remove checkpoint", "override control",
)


def validate_version(version: RuleVersion) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    raw = (version.content_markdown or "").lower()

    if not version.content_markdown.strip():
        errors.append({"code": "EMPTY_CONTENT", "message": "Rule content is empty"})

    for token in PROHIBITED:
        if token in raw:
            errors.append({
                "code": "PROHIBITED_INSTRUCTION",
                "message": f"prohibited instruction or tool reference: {token}",
            })

    if not version.conflict_key and version.category in ("LANGUAGE", "OUTPUT_CONSTRAINT"):
        warnings.append({
            "code": "MISSING_CONFLICT_KEY",
            "message": "LANGUAGE/OUTPUT rules should define conflict_key",
        })

    if version.priority < 0 or version.priority > 1000:
        errors.append({"code": "BAD_PRIORITY", "message": "priority must be 0..1000"})

    valid = len(errors) == 0
    status = "valid" if valid and not warnings else ("warning" if valid else "invalid")
    return {
        "valid": valid,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "structure": "passed" if version.content_markdown.strip() else "failed",
            "security": "passed" if valid else "failed",
            "controls": "passed" if "bypass control" not in raw else "failed",
        },
    }
