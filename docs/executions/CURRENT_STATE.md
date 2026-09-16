# Executions — CURRENT STATE

**Date:** 2026-07-17  
**Spec:** [EXECUTIONS_SYSTEM_REQUIREMENTS.md](EXECUTIONS_SYSTEM_REQUIREMENTS.md)  
**UI:** `src/workflow_ui/static/executions/`

## After PR-1

| Area | Location | Notes |
|------|----------|-------|
| Nav | `data-view=executions` | Dedicated module |
| Catalog / Inspector | `executions/module.js` | Table + inspector drawer |
| Domain | `src/platform/executions/` | `ExecutionRecord` with snapshot/timeline |
| API | `/api/v1/executions*` | Catalog, detail, pause/cancel, start |
| Legacy | `Execution` in store | Merged into catalog + overview |

## Principle

Execution is a frozen runtime instance — not an editable Flow/Playbook template.
