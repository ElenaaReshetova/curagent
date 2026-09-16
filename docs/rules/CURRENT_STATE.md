# Rules — CURRENT STATE

**Date:** 2026-07-17  
**Spec:** [RULES_SYSTEM_REQUIREMENTS.md](RULES_SYSTEM_REQUIREMENTS.md)  
**UI:** `src/workflow_ui/static/rules/` (from RULES_IMPLEMENTATION_PACKAGE)

## After PR-1

| Area | Location | Notes |
|------|----------|-------|
| Nav Rules | `data-view=rules` | Dedicated module |
| Catalog / Detail / Preview | `rules/module.js` | Table + drawer + resolve overlay |
| Domain | `src/platform/rules/` | `RuleRecord` + `RuleVersion` |
| API | `/api/v1/rules*` | Catalog, versions, validate, publish, resolve |
| Legacy | `RuleSet` in store | Kept for overview seed |

## Constraints

- Rules cannot weaken Controls or call MCP tools
- Published versions immutable
- Control wins on conflict with Rules
