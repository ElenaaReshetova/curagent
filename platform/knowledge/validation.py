"""Knowledge Space validation (static MVP)."""

from __future__ import annotations

from typing import Any

from src.platform.knowledge.models import KnowledgeSpaceRecord

PROHIBITED = ("mcp://", "list_tools", "call_tool", "jira_get_issue", "slack.search")


def validate_space(space: KnowledgeSpaceRecord) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not space.key.strip():
        errors.append({"code": "MISSING_KEY", "message": "Knowledge Space key is required"})
    if not space.purpose.strip():
        warnings.append({"code": "EMPTY_PURPOSE", "message": "Purpose should describe trusted context"})
    if not space.sources and space.status == "ACTIVE":
        errors.append({"code": "NO_SOURCES", "message": "Active space requires at least one source binding"})

    raw = f"{space.purpose} {space.search_policy}".lower()
    for token in PROHIBITED:
        if token in raw:
            errors.append({
                "code": "DIRECT_TOOL_REF",
                "message": f"Knowledge Space must not embed direct tool/MCP refs: {token}",
            })

    for src in space.sources:
        if src.priority < 0 or src.priority > 1000:
            errors.append({"code": "BAD_PRIORITY", "message": f"Source {src.name} priority out of range"})
        if src.health_pct < 85 and src.status == "ACTIVE":
            warnings.append({
                "code": "DEGRADED_SOURCE",
                "message": f"Source {src.name} health is {src.health_pct}%",
            })

    valid = len(errors) == 0
    return {
        "valid": valid,
        "status": "valid" if valid and not warnings else ("warning" if valid else "invalid"),
        "errors": errors,
        "warnings": warnings,
    }
