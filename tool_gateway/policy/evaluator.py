"""Policy and visibility evaluation (CAP-008, CAP-009, SEC-001, SEC-008)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from src.tool_gateway.models.envelopes import CallerIdentity, DenialCode, ToolIntent
from src.tool_gateway.models.manifest import CapabilityManifest, VisibilityRules

POLICY_VERSION = "1.0.0"


def _policy_path() -> Path:
    base = os.environ.get("REGISTRY_CONFIG_DIR", "")
    if base:
        return Path(base) / "policy.json"
    return Path(__file__).resolve().parents[3] / "config" / "registry" / "policy.json"


def load_policy() -> dict[str, Any]:
    path = _policy_path()
    if not path.exists():
        return {"version": POLICY_VERSION, "deny_capabilities": [], "tenant_rules": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _matches(rule_list: list[str], value: Optional[str]) -> bool:
    if "*" in rule_list:
        return True
    if value is None:
        return False
    return value in rule_list


def check_visibility(
    manifest: CapabilityManifest,
    intent: ToolIntent,
) -> tuple[bool, Optional[DenialCode], dict[str, Any]]:
    """CAP-008, RES-006."""
    v: VisibilityRules = manifest.visibility
    caller = intent.caller
    if not _matches(v.tenants, intent.tenant_id):
        return False, DenialCode.CAPABILITY_NOT_VISIBLE, {"reason": "tenant_not_visible"}
    role = caller.sub_agent_role or caller.service_account or "default"
    if not _matches(v.roles, role):
        return False, DenialCode.CAPABILITY_NOT_VISIBLE, {"reason": "role_not_visible"}
    if not _matches(v.skills, caller.skill_id):
        return False, DenialCode.CAPABILITY_NOT_VISIBLE, {"reason": "skill_not_visible"}
    if not _matches(v.playbooks, intent.playbook_id):
        return False, DenialCode.CAPABILITY_NOT_VISIBLE, {"reason": "playbook_not_visible"}
    return True, None, {}


def check_policy(
    manifest: CapabilityManifest,
    intent: ToolIntent,
) -> tuple[bool, Optional[DenialCode], dict[str, Any]]:
    """CAP-009, SEC-007."""
    policy = load_policy()
    version = policy.get("version", POLICY_VERSION)

    if manifest.capability_id in policy.get("deny_capabilities", []):
        return False, DenialCode.POLICY_DENIED, {"policy_version": version, "rule": "deny_list"}

    tenant_rules = policy.get("tenant_rules", {})
    tenant_rule = tenant_rules.get(intent.tenant_id, tenant_rules.get("*", {}))
    allowed = tenant_rule.get("allowed_side_effects", ["read", "write", "destructive", "external_publish"])
    if manifest.side_effect_class.value not in allowed:
        return False, DenialCode.POLICY_DENIED, {
            "policy_version": version,
            "rule": "side_effect_not_allowed",
            "side_effect": manifest.side_effect_class.value,
        }

    return True, None, {"policy_version": version}


def get_policy_version() -> str:
    return load_policy().get("version", POLICY_VERSION)


def save_policy(policy: dict[str, Any]) -> dict[str, Any]:
    path = _policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return load_policy()
