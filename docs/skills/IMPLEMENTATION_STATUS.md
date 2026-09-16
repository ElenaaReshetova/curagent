# Skills — IMPLEMENTATION STATUS

**Updated:** 2026-07-17

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 Catalog + domain | done | Catalog / Detail / Editor UI + versioned JSON API |
| Phase 2 Interfaces | partial | Uses existing skill-interfaces; badges in Detail |
| Phase 3 Editor packages | partial | SKILL.md save + file tree; full file API later |
| Phase 4 Imports | stub | Modal only |
| Phase 5 Test Lab | stub | Tests tab + seed cases |
| Phase 6 Bindings | stub | Bindings tab display |
| Phase 7 Runtime | pending | |

## Spec / ADR

- `docs/skills/SKILLS_SYSTEM_REQUIREMENTS.md`
- `docs/adr/ADR-002-skill-interface-and-versioning.md`

## Phase 1 deliverables

- Build → Skills → Catalog (cards, filters, metrics)
- Detail tabs: Overview, Instructions, Manifest, Interfaces, Tests, Bindings, Versions, Validation
- Fullscreen Editor (package / SKILL.md / inspector)
- No MCP tool pickers; capabilities chips only
- API: catalog, versions, SKILL.md PUT, validate, publish
- Tests: `tests/test_skills_module.py`
- Vertical seed: **System Requirements Generator** (`analysis.system_requirements.generate@1`)
