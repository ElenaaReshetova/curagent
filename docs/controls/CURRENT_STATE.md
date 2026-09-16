# Controls — CURRENT STATE

**Date:** 2026-07-17  
**Spec:** [CONTROLS_SYSTEM_REQUIREMENTS.md](CONTROLS_SYSTEM_REQUIREMENTS.md)  
**UI:** `src/workflow_ui/static/controls/`

## After PR-1

| Area | Location | Notes |
|------|----------|-------|
| Nav | `data-view=controls` | Dedicated module |
| Catalog / Drawer | `controls/module.js` | Cards, detail drawer, editor shell |
| Domain | `src/platform/controls/` | `ControlRecord`, versions, violations |
| API | `/api/v1/controls*` | Catalog, detail, validate, test, resolve |
| Legacy | `ControlPack` in store | Merged into catalog for overview |

## Principle

Control is an enforceable governance requirement with applicability, evaluation logic, and explicit enforcement — not a prompt rule.
