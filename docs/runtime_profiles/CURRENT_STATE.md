# Runtime Profiles — CURRENT STATE

**Date:** 2026-07-19  
**Spec:** [RUNTIME_PROFILES_SYSTEM_REQUIREMENTS.md](RUNTIME_PROFILES_SYSTEM_REQUIREMENTS.md)  
**UI:** `src/workflow_ui/static/runtime_profiles/`

## After PR-2 / PR-3

| Area | Location | Notes |
|------|----------|-------|
| Nav | `data-view=runtime-profiles` | «Профили исполнения» |
| Catalog / Detail / Editor / Effective preview | `runtime_profiles/module.js` | Все вкладки drawer заполняются из `detail`; редактор сохраняет draft и активирует |
| Domain | `src/platform/runtime_profiles/` | `RuntimeProfileRecord` + `RuntimeProfileVersion` |
| API | `/api/v1/runtime-profiles*` | Catalog, PATCH draft, POST draft, activate, validate, test, resolve |
| Legacy | `RuntimeProfile` in store | Kept for overview |

## Principle

Runtime Profile defines provider, model, sandbox, limits and capabilities — not Skill instructions or Playbook graphs.
