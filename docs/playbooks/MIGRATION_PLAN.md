# Playbooks — MIGRATION PLAN

## PR-1 (this iteration): Navigation and screens

- Audit docs
- Catalog / Detail / Designer UI from prototype inside platform shell
- Catalog list from `/api/v1/playbooks` (enriched)
- Detail loads `/api/v1/playbooks/{id}` + versions/graph stubs
- No Agents dependency
- Route/component tests

## PR-2: Persistence

- `Playbook` + `PlaybookVersion` JSON store (then PostgreSQL)
- CRUD + version lifecycle
- Graph autosave PUT with revision/If-Match

## PR-3+: Graph editing, bindings, controls, simulation, runtime

Per PLAYBOOKS_SYSTEM_REQUIREMENTS §22.
