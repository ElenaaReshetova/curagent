"""Pre-scenario routing: classify → choose which workflow template to run.

Classify runs once for all ingress sources *before* a playbook/E2E template starts.
Templates themselves should execute a single PDLC stage (or a fixed chain), not re-route.
"""

from __future__ import annotations

import os
from typing import Optional

# primary_skill → Temporal workflow template id
SKILL_TO_TEMPLATE: dict[str, str] = {
    "business-requirements": "generate-business-requirements-slack",
    "system-requirements": "generate-system-requirements",
    "test-case-design": "generate-business-requirements-slack",
    "code-analysis": "generate-security-policy-review",
    "normalize-task": "generate-security-policy-review",
    "general": "generate-business-requirements-slack",
}

DEFAULT_TEMPLATE = os.environ.get(
    "DEFAULT_SKILL_WORKFLOW_TEMPLATE_ID",
    "generate-business-requirements-slack",
)

# If set, ignore classify and always run this template (debug / pin).
FORCE_TEMPLATE_ID = os.environ.get("FORCE_WORKFLOW_TEMPLATE_ID", "").strip() or None


def template_for_skill(primary_skill: str) -> str:
    skill = (primary_skill or "").strip() or "general"
    return SKILL_TO_TEMPLATE.get(skill, DEFAULT_TEMPLATE)


def resolve_scenario_template(
    *,
    primary_skill: str,
    requested_template_id: Optional[str] = None,
) -> tuple[str, str]:
    """Return (template_id, reason).

    Priority:
    1. FORCE_WORKFLOW_TEMPLATE_ID env (ops pin)
    2. Classify → skill map (normal path)
    3. Explicit requested_template_id only as fallback if skill unknown
    """
    if FORCE_TEMPLATE_ID:
        return FORCE_TEMPLATE_ID, "force_env"

    skill = (primary_skill or "").strip() or "general"
    if skill in SKILL_TO_TEMPLATE:
        return SKILL_TO_TEMPLATE[skill], f"classify:{skill}"

    requested = (requested_template_id or "").strip() or None
    if requested:
        return requested, "requested_fallback"

    return DEFAULT_TEMPLATE, f"default:{skill}"
