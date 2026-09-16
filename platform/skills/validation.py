"""Skill package validation (static MVP)."""

from __future__ import annotations

from typing import Any

from src.platform.contracts.registry import validate_contract_references, validate_payload
from src.platform.skills.models import SkillVersion

PROHIBITED_TOKENS = (
    "jira_", "confluence_", "notion_", "mcp://", "mcp_server", "mcp tool",
    "list_tools", "call_tool", "slack.", "jira.get", "confluence.read",
)


def validate_version(
    version: SkillVersion,
    *,
    known_interfaces: set[str] | None = None,
    interface_capabilities: dict[str, list[str]] | None = None,
    interface_contracts: dict[str, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    raw = f"{version.skill_markdown}\n{version.manifest}".lower()
    for token in PROHIBITED_TOKENS:
        if token in raw:
            errors.append({
                "code": "PROHIBITED_TOOL_REF",
                "message": f"prohibited direct MCP/tool reference: {token}",
            })

    if not version.interface_key:
        errors.append({"code": "MISSING_INTERFACE", "message": "Skill version requires interface_key"})
    elif known_interfaces is not None and version.interface_key not in known_interfaces:
        errors.append({
            "code": "UNKNOWN_INTERFACE",
            "message": f"skill interface '{version.interface_key}' not found",
        })

    if not version.skill_markdown.strip():
        errors.append({"code": "EMPTY_SKILL_MD", "message": "SKILL.md is empty"})

    if not version.allowed_capabilities:
        warnings.append({"code": "NO_CAPABILITIES", "message": "No allowed capabilities declared"})

    if interface_capabilities and version.interface_key in interface_capabilities:
        allowed = set(interface_capabilities[version.interface_key])
        if allowed and not set(version.allowed_capabilities).issubset(allowed):
            errors.append({
                "code": "CAPABILITY_EXCEEDS_INTERFACE",
                "message": "allowed_capabilities exceed skill interface capabilities",
            })

    if not any(f.path == "SKILL.md" for f in version.files) and version.skill_markdown:
        warnings.append({"code": "MISSING_SKILL_FILE", "message": "Package tree missing SKILL.md file entry"})

    has_example = any(f.path.startswith("examples/") for f in version.files)
    if not has_example:
        warnings.append({"code": "MISSING_EXAMPLE", "message": "Example output is missing."})

    has_empty_evidence_test = any("empty" in t.key.lower() or "empty" in t.name.lower() for t in version.test_cases)
    if not has_empty_evidence_test:
        warnings.append({
            "code": "MISSING_EMPTY_EVIDENCE_TEST",
            "message": "No regression test for empty evidence.",
        })

    contract_errors, contract_warnings = validate_contract_references(
        version.input_contract_key,
        version.output_contract_key,
        interface_key=version.interface_key or None,
    )
    errors.extend(contract_errors)
    warnings.extend(contract_warnings)

    manifest = version.manifest or {}
    spec = manifest.get("spec") if isinstance(manifest, dict) else {}
    if isinstance(spec, dict):
        manifest_in = spec.get("inputContract") or spec.get("input_contract")
        manifest_out = spec.get("outputContract") or spec.get("output_contract")
        if manifest_in and manifest_in != version.input_contract_key:
            warnings.append({
                "code": "MANIFEST_INPUT_CONTRACT_MISMATCH",
                "message": (
                    f"manifest inputContract '{manifest_in}' differs from "
                    f"version input '{version.input_contract_key}'"
                ),
            })
        if manifest_out and manifest_out != version.output_contract_key:
            warnings.append({
                "code": "MANIFEST_OUTPUT_CONTRACT_MISMATCH",
                "message": (
                    f"manifest outputContract '{manifest_out}' differs from "
                    f"version output '{version.output_contract_key}'"
                ),
            })

    if interface_contracts and version.interface_key in interface_contracts:
        expected_in, expected_out = interface_contracts[version.interface_key]
        if version.input_contract_key != expected_in or version.output_contract_key != expected_out:
            # Already surfaced as warnings by validate_contract_references.
            pass

    contracts_ok = (
        version.input_contract_key
        and version.output_contract_key
        and not contract_errors
    )

    valid = len(errors) == 0
    status = "valid" if valid and not warnings else ("warning" if valid else "invalid")
    return {
        "valid": valid,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "package": "passed" if valid else "failed",
            "manifest": "passed" if version.manifest else "warning",
            "contracts": "passed" if contracts_ok else ("warning" if not contract_errors else "failed"),
            "security": "passed" if valid else "failed",
        },
    }


def validate_skill_output(version: SkillVersion, payload: Any) -> dict[str, Any]:
    """Validate runtime/test output against the skill version output contract."""
    errors = validate_payload(version.output_contract_key, payload)
    return {
        "valid": not errors,
        "contract_key": version.output_contract_key,
        "errors": [{"code": "OUTPUT_CONTRACT_INVALID", "message": msg} for msg in errors],
    }
