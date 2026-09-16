# Skills — CURRENT STATE

**Date:** 2026-07-17  
**Spec:** [SKILLS_SYSTEM_REQUIREMENTS.md](SKILLS_SYSTEM_REQUIREMENTS.md)  
**UI:** `src/workflow_ui/static/skills/` (Catalog / Detail / Editor)

## After Phase 1 + inheritance

| Area | Location | Notes |
|------|----------|-------|
| Nav Skills | `data-view=skills` | Dedicated module (RU catalog UX) |
| Catalog / Detail / Editor | `skills/module.js` + CSS | Inheritance + package file tree |
| Domain | `src/platform/skills/` | `SkillRecord` + `SkillVersion` + `parent_skill_id` |
| API | `/api/v1/skills*` | Catalog, inherit, files CRUD, publish |
| DB | `skills` / `skill_versions` | Alembic `003_skills`, dual JSON/Postgres store |
| Seed | JSON or Postgres | CORE/CORPORATE sealed; TEAM mutable |

## Constraints enforced

- No Agents ownership on Skills
- No MCP/tool pickers in UI — capabilities chips only
- Published versions immutable (edits via draft)
- CORE / CORPORATE skills sealed — customise only via inheritance
- Direct MCP refs rejected by validation
