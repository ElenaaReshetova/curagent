# Contextual Help & Skill Slot UX — CURRENT STATE

**Date:** 2026-07-17  
**Spec:** [PLATFORM_CONTEXTUAL_HELP_AND_SKILL_SLOT_UX_SPEC.md](PLATFORM_CONTEXTUAL_HELP_AND_SKILL_SLOT_UX_SPEC.md)  
**Prompt:** [CURSOR_CONTEXTUAL_HELP_MASTER_PROMPT.md](CURSOR_CONTEXTUAL_HELP_MASTER_PROMPT.md)

## Inventory (before PR)

| Area | Status |
|------|--------|
| Shared FieldHelp / tooltip / popover / drawer | **Missing** |
| Help Content Registry (YAML) | **Missing** → added in this slice |
| i18n framework | **Missing** (mixed RU/EN inline) |
| User prefs / Basic·Advanced·Expert | **Missing** → mode toggle for Skill Slot |
| Playbook Designer Skill Slot editor | Generic inspector: Name + free-text `interface_key` |
| Skill bindings | Read-only on Detail tab |
| Mapping JSON UI | Not present (DB columns exist) |
| Precedent | Knowledge Spaces `#ks-info` modal |

## Skill Slot data model (today)

`PlaybookNode`: `key`, `type=SKILL_SLOT`, `name`, `interface_key`, `config{}`, `position`.  
`SkillBindingRecord` on version: `step_key`, `interface_key`, `skill_key`, `skill_version`, `scope`.  
Validation requires `interface_key` on SKILL_SLOT.

## Files to change / add

| Path | Role |
|------|------|
| `config/help/{locale}/*.yaml` | Help Content Registry |
| `src/platform/help/` | Loader + API models |
| `src/platform/api.py` | `GET /api/v1/help` |
| `src/workflow_ui/static/help/*` | FieldHelp, tooltip, popover, drawer |
| `index.html` + `playbooks/module.js` + CSS | Skill Slot stepped inspector |
| `tests/test_help_registry.py` | Registry API tests |

## Implementation slice (this PR)

1. Help YAML registry (ru-RU primary, en-US fallback)  
2. `/api/v1/help` + `/api/v1/help/{conceptKey}`  
3. Shared help UI components  
4. Skill Slot inspector: steps 1–2 + Advanced (version policy, runtime inherit) + checklist + plain summary  
5. Context help drawer on Skill Slot selection  
6. No production mocks for Skills — load interfaces from existing API  

## Out of scope (next)

Visual input mapping assistant, Guided Tour, Expert raw JSON, full i18n of shell, Skill recommendation engine.
