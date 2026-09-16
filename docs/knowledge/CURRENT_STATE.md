# Knowledge Spaces — CURRENT STATE

**Date:** 2026-07-17  
**Spec:** [KNOWLEDGE_SPACES_SYSTEM_REQUIREMENTS.md](KNOWLEDGE_SPACES_SYSTEM_REQUIREMENTS.md)  
**UI:** `src/workflow_ui/static/knowledge/`

## After PR-1

| Area | Location | Notes |
|------|----------|-------|
| Nav | `data-view=knowledge` | Dedicated module |
| Catalog / Detail / Playground | `knowledge/module.js` | Cards + drawer + search playground |
| Domain | `src/platform/knowledge/` | `KnowledgeSpaceRecord` + source bindings |
| API | `/api/v1/knowledge-spaces*` | Catalog, sources, search playground |
| Legacy | `KnowledgeSpace` in store | Kept for overview |

## Principle

Skills call `context.search`; Knowledge Space selects trusted sources. No direct MCP/tool wiring in Skills.
