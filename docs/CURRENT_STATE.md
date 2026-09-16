# CURRENT_STATE — Governed AI Delivery Platform V2

**Дата:** 2026-07-17  
**Ветка:** `experiment`  
**Source of truth:** [CURSOR_GOVERNED_AI_PLATFORM_SPEC_V2.md](requirements/CURSOR_GOVERNED_AI_PLATFORM_SPEC_V2.md)

## Stack

| Слой | Технологии |
|------|------------|
| Frontend | Static HTML/JS/CSS (`src/workflow_ui/static/`), Cytoscape Playbook Designer |
| Backend UI API | FastAPI `src/workflow_ui/main.py` + `src/platform/api.py` |
| Domain/store | Pydantic + JSON files `config/platform/` |
| Runtime | Temporal (`src/orchestrator/`), Kafka, gateways |
| Integrations | MCP Jira/Slack, `src/tool_gateway` (Capability Gateway base) |
| Infra | Docker Compose |

## HTML-прототип

`src/workflow_ui/static/index.html` + `styles.css` + `app.js` + `overview.js` + `platform-pages.js`

Визуал (navy sidebar, cards) — **сохранять**.

## Раздел Agents (проблема V2)

- UI: `data-view="agents"`, catalog в `platform-pages.js`
- Model: `src/platform/domain/models.py` → `Agent`
- Store: `config/platform/agents.json`, CRUD в `store.py`
- API: `/api/v1/agents`
- Seed: `build_agents()` в `governed_catalog.py`

По V2 Agents **не** доменная сущность → миграция полезных полей в **Runtime Profiles** (LLM/model/limits); routing/playbook bindings уходят в Flow/Routing (позже).

## Что уже близко к V2

Playbooks, Skills, Rules, Knowledge Spaces, Flows, Controls, Capabilities, Executions, Checkpoints, Audit, Integrations, Designer.

## Расхождения с V2

| Сейчас | V2 |
|--------|-----|
| Agents в меню | Runtime Profiles |
| Nav Control/Runtime Plane | Dashboard / Build / Run / Govern |
| Models / Users / Activity / Queue / Events в меню | нет в итоговом меню |
| Нет versioned PlaybookVersion API | нужно в фазах 3+ |
| JSON store | PostgreSQL в фазе 2 |
| Overview payload | Dashboard summary APIs |

## Нельзя потерять

Flow Studio DOM IDs, `/api/templates/*`, MCP/capabilities APIs, Temporal/Kafka stack, `config/platform` seed data.
