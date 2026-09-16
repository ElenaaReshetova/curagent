# Playbooks — IMPLEMENTATION STATUS

**Updated:** 2026-07-19

| PR | Status | Notes |
|----|--------|-------|
| PR-1 Navigation & screens | done | Catalog / Detail / Designer UI + versioned API seed |
| Designer PR-1 Real load/save | done | Autosave, revision conflict, positions/edges, ACTIVE read-only |
| PR-2 Persistence | done | PostgreSQL SoT when `PLATFORM_DATABASE_URL` set; JSON `playbook_records` / `playbook_versions` fallback |
| PR-3 Graph editing | partial | Add/move/connect in Designer; undo/redo/copy later |
| PR-4 Bindings | pending | Bindings shown; resolver later |
| PR-5 Controls | pending | Control bindings seeded; spine resolver later |
| PR-6 Simulation | partial | MVP simulation summary endpoint |
| PR-7 Runtime | pending | |
| PR-8 Human & publication | pending | |

## Spec

- Domain: `docs/playbooks/PLAYBOOKS_SYSTEM_REQUIREMENTS.md`
- Designer: `docs/playbooks/DESIGNER_CURRENT_STATE.md`

## Designer PR-1 deliverables

- `GET /api/v1/playbooks/{id}/versions/{vid}/designer`
- Real Draft graph load + `PUT .../graph` autosave with revision
- Save states: SAVED / SAVING / UNSAVED / SAVE_FAILED / CONFLICT / OFFLINE
- Structured 409 `PLAYBOOK_VERSION_CONFLICT`
- Node positions + transitions persisted; refresh restores from backend
- PUBLISHED / non-DRAFT opened read-only
- Navigation guard (`beforeunload` + leave confirm)
- No localStorage primary persistence; no fake save
- Tests: `tests/test_playbooks_module.py`

## Earlier PR-1 deliverables

- Nav: Build → Playbooks → Catalog (`#view-playbooks-list`)
- Detail tabs: Overview, Steps, Bindings, Controls, Versions, Executions
- Fullscreen Designer (palette / canvas / inspector / simulation)
- No Agents in Playbook UI or versioned graph model
- API: `GET/POST /api/v1/playbooks`, versions, graph, validate, publish, simulations
