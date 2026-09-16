"""Validation for protocol integration configs."""

from __future__ import annotations

from typing import Any


def validate_mcp_entry(name: str, entry: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not name.strip():
        errors.append({"code": "NAME_REQUIRED", "message": "MCP server name is required"})
    if not isinstance(entry, dict):
        errors.append({"code": "ENTRY_INVALID", "message": "MCP server entry must be an object"})
        return _result(errors, warnings)
    has_command = bool(entry.get("command"))
    has_url = bool(entry.get("url"))
    if not has_command and not has_url:
        errors.append({
            "code": "TRANSPORT_REQUIRED",
            "message": "MCP server requires command (stdio) or url (SSE/HTTP)",
        })
    if has_command and has_url:
        warnings.append({
            "code": "TRANSPORT_MIXED",
            "message": "Both command and url set — clients typically use one transport",
        })
    env = entry.get("env")
    if env is not None and not isinstance(env, dict):
        errors.append({"code": "ENV_INVALID", "message": "env must be an object of string values"})
    return _result(errors, warnings)


def validate_a2a_entry(name: str, url: Any) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not name.strip():
        errors.append({"code": "NAME_REQUIRED", "message": "A2A server name is required"})
    if not isinstance(url, str) or not url.strip():
        errors.append({"code": "URL_REQUIRED", "message": "A2A server URL is required"})
    elif not (url.startswith("http://") or url.startswith("https://")):
        warnings.append({"code": "URL_SCHEME", "message": "A2A URL should be http(s)"})
    return _result(errors, warnings)


def validate_acp_entry(name: str, entry: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not name.strip():
        errors.append({"code": "NAME_REQUIRED", "message": "ACP agent name is required"})
    if not isinstance(entry, dict):
        errors.append({"code": "ENTRY_INVALID", "message": "ACP agent entry must be an object"})
        return _result(errors, warnings)
    if not entry.get("command"):
        errors.append({"code": "COMMAND_REQUIRED", "message": "ACP agent requires command"})
    args = entry.get("args")
    if args is not None and not isinstance(args, list):
        errors.append({"code": "ARGS_INVALID", "message": "args must be an array of strings"})
    return _result(errors, warnings)


def _result(errors: list[dict[str, str]], warnings: list[dict[str, str]]) -> dict[str, Any]:
    valid = not errors
    return {
        "valid": valid,
        "status": "valid" if valid and not warnings else ("warning" if valid else "invalid"),
        "errors": errors,
        "warnings": warnings,
    }
