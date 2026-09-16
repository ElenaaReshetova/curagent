# Playbooks — CURRENT STATE

**Date:** 2026-07-19  
**Spec:** [PLAYBOOKS_SYSTEM_REQUIREMENTS.md](PLAYBOOKS_SYSTEM_REQUIREMENTS.md)  
**UI:** `src/workflow_ui/static/playbooks/` (Catalog / Detail / Designer)

## What exists after Designer PR-1

| Area | Location | Notes |
|------|----------|-------|
| Nav Playbooks | `playbooks-list` | Dedicated module (not generic platform-pages) |
| Catalog / Detail / Designer | `playbooks/module.js` + CSS | RU labels; Detail without Steps; Used in Flows / Skill & Rules bindings |
| Domain | `src/platform/playbooks/` | `PlaybookRecord` + `PlaybookVersion` + graph; PG SoT when `PLATFORM_DATABASE_URL` set |
| API | `/api/v1/playbooks*` | Catalog, versions, graph, designer, validate, publish, simulations, consumers |
| Persistence | JSON fallback **or** PostgreSQL | `playbook_*` tables + `graph_json` / nodes / transitions |
| Seed | `seed_data.py` → JSON or PG | System Requirements + sample catalog |
| Designer | shared `FlowCanvas` + DSL JSON panel | Canvas/DSL toggle; skill+rule bindings sync on save |
| Contextual help | `docs/ux/` + `config/help/` + `static/help/` | Skill Slot stepped inspector + FieldHelp |
| Overview SoT | versioned catalog | Dashboard/overview no longer use `playbooks_governed.json` |

## Agents dependency

None in Playbooks module. Runtime Profiles remain separate under Build.
