# AI Agent Platform — целевая архитектура

**Версия:** 0.2 (experiment)  
**Спека:** [CURSOR_AI_AGENT_PLATFORM_SPEC.md](../requirements/CURSOR_AI_AGENT_PLATFORM_SPEC.md)  
**ADR:** [ADR-001-platform-migration.md](ADR-001-platform-migration.md)

## Продуктовая модель

Платформа **не** является таск-трекером. Работа приходит из внешних систем.

```text
External Sources (Jira / SberTrack / Slack / Confluence)
        │
        ▼
Ingress → Kafka: work-item.received
        │
        ▼
Execution Bootstrap → Contract Compiler
        │
        ▼
Temporal CaseWorkflow
  ├── Artifact Engine
  ├── Planner (LLM)
  ├── Policy Engine
  ├── Operator Executor
  ├── Human Approval
  └── Publisher
        │
        ▼
MCP Gateway → approved tools only
        │
        ▼
PostgreSQL · Kafka · Object Storage · Audit Store
```

## Control Plane vs Runtime Plane

| Plane | Сущности | UI |
|-------|----------|-----|
| Control | Blueprint, Operator, Playbook, Flow, Policy, Contract Template, MCP, Models, RBAC, Audit | настройка до выполнения |
| Runtime | Execution, Contract, Artifact, Evidence, Approval, Operator Run, Tool Call | мониторинг внешних задач |

## Текущее состояние (experiment)

Реализовано:

- спека и ADR в `docs/`;
- доменная модель Control/Runtime в `src/platform/domain/`;
- JSON store `src/platform/store.py` + seed `config/platform/`;
- полный CRUD API `/api/v1/*` (operators, playbooks, blueprints, policies, contracts, models, users, integrations, audit);
- Runtime API: executions (pause/resume/cancel/replan), approvals, activity, queue, events;
- policy DSL evaluator (MVP);
- UI всех экранов Control/Runtime Plane (`platform-pages.js`): list/detail CRUD, execution tabs по спеке 16.4, Flow Studio.

В работе / далее по фазам спеки:

- PostgreSQL + Alembic persistence;
- Execution Contract Compiler + CaseWorkflow loop;
- Artifact Commit Service;
- Qwen adapter;
- React/Vite Flow Studio.
## Совместимость со стеком

Сохраняются: Kafka, Temporal, FastAPI, MCP Jira/Slack, Tool Gateway, существующие workflow JSON.
