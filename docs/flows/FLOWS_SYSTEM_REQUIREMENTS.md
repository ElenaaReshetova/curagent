# FLOWS_SYSTEM_REQUIREMENTS.md
## Governed AI Delivery Platform
### Полное системное ТЗ на реализацию раздела Flows

---

# 0. Простое назначение Flow

Flow — это сквозной маршрут работы через несколько Playbooks.

Playbook отвечает на вопрос:

> Как выполнить один управляемый этап?

Flow отвечает на вопрос:

> Какие этапы должны быть выполнены, в каком порядке и при каких условиях?

Пример:

```text
Feature Delivery Flow

Research
  ↓
Business Requirements
  ↓
System Requirements
  ↓
Development
  ↓
Testing
  ↓
Release
```

Каждый блок — ссылка на опубликованную версию Playbook.

Flow не содержит длинных prompt-инструкций и не исполняет Skills напрямую.

Основная модель:

```text
External Work Item
  ↓
Routing
  ↓
Flow
  ↓
Flow Stages
  ↓
Playbook Runs
  ↓
Skill Runs
```

---

# 1. Назначение раздела Flows

Раздел Flows нужен для:

- моделирования сквозных процессов PDLC/SDLC;
- связывания Playbooks;
- задания переходов;
- branching;
- parallel stages;
- routing;
- stage handoff;
- completion policy;
- cancellation policy;
- retries;
- runtime profile;
- knowledge-space routing;
- simulation;
- versioning;
- execution tracking.

---

# 2. Границы ответственности

Flow отвечает за:

- последовательность этапов;
- выбор Playbook на каждом этапе;
- переходы;
- условия;
- ветвление;
- параллельность;
- retries на уровне stage;
- вход и выход stage;
- routing context;
- completion;
- cancellation;
- compensation;
- Runtime Profile reference.

Flow не отвечает за:

- внутренние шаги Playbook;
- конкретные Skills;
- MCP tools;
- структуру Artifact внутри Playbook;
- Rule content;
- Control definitions;
- model prompt.

---

# 3. Типы Flows

Поддержать:

```text
FEATURE_DELIVERY
BUG_FIX
INCIDENT_RESOLUTION
CHANGE_REQUEST
RELEASE
RESEARCH
COMPLIANCE_REVIEW
CUSTOM
```

Примеры:

- Feature Delivery;
- Emergency Bug Fix;
- Incident Resolution;
- Architecture Review;
- Regulatory Change;
- Release Train.

---

# 4. Жизненный цикл

Flow:

```text
DRAFT
VALIDATING
READY
PUBLISHED
DEPRECATED
ARCHIVED
```

Flow Version:

```text
DRAFT
VALIDATING
READY
PUBLISHED
DEPRECATED
```

Правила:

- published version immutable;
- редактирование создаёт новую version;
- новый Execution использует только published version;
- старые Execution продолжают работать по snapshot;
- deprecated version нельзя выбирать для новых маршрутов;
- rollback создаёт новую version, а не меняет старую.

---

# 5. Основные сущности

```text
Flow
  └── Flow Version
        ├── Trigger Definitions
        ├── Routing Conditions
        ├── Stage Graph
        ├── Stage Contracts
        ├── Runtime Profile
        ├── Knowledge Space Policy
        ├── Completion Policy
        ├── Cancellation Policy
        └── Validation
```

---

# 6. Stage

Stage — узел Flow, который обычно запускает Playbook.

Stage содержит:

- key;
- name;
- playbookVersionId;
- input mapping;
- output mapping;
- transition policy;
- retry policy;
- timeout;
- supervision override;
- knowledge space selector;
- runtime profile override;
- failure behavior;
- compensation stage;
- tags.

Пример:

```json
{
  "key": "system-requirements",
  "name": "System Requirements",
  "type": "PLAYBOOK",
  "playbookVersionId": "uuid",
  "inputMapping": {
    "artifact": "$.previous.output"
  },
  "outputMapping": {
    "requirements": "$.artifact.currentVersion"
  },
  "retryPolicy": {
    "maxAttempts": 2
  },
  "timeoutSeconds": 3600
}
```

---

# 7. Типы узлов Flow

Поддержать:

```text
START
PLAYBOOK_STAGE
CONDITION
PARALLEL_SPLIT
PARALLEL_JOIN
WAIT_EVENT
HUMAN_DECISION
SUBFLOW
PUBLICATION
COMPENSATION
END
```

## START

Единственный вход Flow.

## PLAYBOOK_STAGE

Запускает Playbook.

## CONDITION

Выбирает transition по expression.

## PARALLEL_SPLIT

Запускает несколько ветвей.

## PARALLEL_JOIN

Ждёт завершения ветвей.

## WAIT_EVENT

Ожидает внешний сигнал или событие.

## HUMAN_DECISION

Запрашивает решение человека на уровне Flow.

## SUBFLOW

Запускает опубликованную версию другого Flow.

## PUBLICATION

Выполняет финальную публикацию, если publication вынесена за пределы Playbook.

## COMPENSATION

Выполняет компенсирующее действие.

## END

Завершает Flow с определённым outcome.

---

# 8. Transitions

Transition связывает nodes.

Содержит:

```text
sourceNodeKey
targetNodeKey
condition
priority
label
isDefault
```

Пример:

```json
{
  "sourceNodeKey": "requirements-review",
  "targetNodeKey": "development",
  "condition": "$.review.status == 'APPROVED'",
  "priority": 100,
  "label": "Approved"
}
```

Expressions должны использовать безопасный DSL.

Запрещено:

- eval;
- JavaScript execution;
- shell;
- SQL;
- network calls.

---

# 9. Trigger Definitions

Flow может запускаться через:

```text
MANUAL
REST_API
WEBHOOK
KAFKA_EVENT
SCHEDULE
WORK_ITEM_CREATED
WORK_ITEM_UPDATED
EXECUTION_COMPLETED
```

Пример:

```json
{
  "type": "WORK_ITEM_CREATED",
  "source": "JIRA",
  "conditions": {
    "projectKey": "PAY",
    "issueType": "Feature"
  }
}
```

---

# 10. Routing Conditions

Routing определяет, какой Flow выбрать до запуска.

Условия могут учитывать:

- workspace;
- source type;
- project;
- work item type;
- labels;
- priority;
- domain;
- team;
- risk;
- data classification;
- manual override.

Пример:

```json
{
  "priority": 100,
  "conditions": [
    {
      "field": "source.projectKey",
      "operator": "EQUALS",
      "value": "PAY"
    },
    {
      "field": "source.issueType",
      "operator": "EQUALS",
      "value": "Feature"
    }
  ]
}
```

---

# 11. Stage Handoff Contracts

Flow должен валидировать совместимость между output предыдущего Playbook и input следующего.

Пример:

```text
BusinessRequirementsArtifact@1
  ↓ compatible with
SystemRequirementsInput@1
```

Для несовместимых contracts:

- публикация запрещена;
- либо требуется explicit mapping adapter.

---

# 12. Completion Policy

Поддержать:

```text
ALL_TERMINAL_STAGES_COMPLETED
ANY_SUCCESS
NAMED_OUTCOME
MANUAL_COMPLETION
```

Пример:

```json
{
  "type": "NAMED_OUTCOME",
  "allowedOutcomes": [
    "RELEASED",
    "REJECTED",
    "CANCELLED"
  ]
}
```

---

# 13. Cancellation Policy

Определяет:

- что делать с активными Playbook Runs;
- запускать ли compensation;
- можно ли отменить при publication;
- кто может отменить;
- что публиковать в Audit.

Пример:

```json
{
  "cancelChildWorkflows": true,
  "runCompensation": true,
  "allowedRoles": ["Operator", "WorkspaceAdmin"]
}
```

---

# 14. Retry Policy

Flow-level defaults:

```json
{
  "maximumAttempts": 3,
  "initialIntervalSeconds": 10,
  "backoffCoefficient": 2,
  "maximumIntervalSeconds": 300,
  "nonRetryableErrors": [
    "CONTROL_VIOLATION",
    "APPROVAL_REJECTED"
  ]
}
```

Stage может переопределять policy.

---

# 15. Flow Catalog UI

Отображать:

- name;
- key;
- type;
- current version;
- status;
- stage count;
- trigger count;
- usage count;
- success rate;
- owner;
- updated at.

Функции:

- поиск;
- фильтры;
- create;
- duplicate;
- archive;
- open detail;
- compare versions;
- publish;
- simulate;
- view executions.

API:

```http
GET /api/v1/flows
POST /api/v1/flows
```

---

# 16. Flow Detail UI

Вкладки:

```text
Overview
Stages
Routing
Triggers
Versions
Executions
Validation
Audit
```

## Overview

Показывает:

- metadata;
- status;
- current version;
- owner;
- runtime profile;
- default knowledge space;
- success rate;
- average duration.

## Stages

Показывает graph summary.

## Routing

Показывает routing rules и priority.

## Triggers

Показывает trigger definitions.

## Versions

History, compare, clone, publish, deprecate.

## Executions

Список executions по Flow.

## Validation

Structural, contract, routing and policy issues.

## Audit

Неизменяемая история.

---

# 17. Flow Designer

Fullscreen low-code designer.

Layout:

```text
Top Toolbar
Left Palette
Center Canvas
Right Inspector
Bottom Problems / Simulation Panel
```

## Palette

```text
Start
Playbook Stage
Condition
Parallel Split
Parallel Join
Wait Event
Human Decision
Subflow
Publication
Compensation
End
```

## Canvas

Поддержать:

- drag and drop;
- connect nodes;
- zoom;
- minimap;
- selection;
- keyboard delete;
- copy/paste;
- undo/redo;
- autosave;
- validation markers;
- simulation overlay.

## Inspector

Для Playbook Stage:

- Playbook Version;
- input mapping;
- output mapping;
- timeout;
- retry;
- failure behavior;
- Knowledge Space;
- Runtime Profile;
- supervision.

Для Condition:

- expression;
- outgoing transitions;
- default transition.

Для Wait Event:

- event type;
- correlation field;
- timeout;
- timeout transition.

---

# 18. Simulation

Simulation должна позволять:

- загрузить sample input;
- проверить routing;
- пройти graph без реальных Skills;
- использовать mocked Playbook outcomes;
- увидеть selected path;
- увидеть failed conditions;
- проверить completion policy;
- проверить compensation;
- сохранить simulation report.

API:

```http
POST /api/v1/flows/{flowId}/versions/{versionId}/simulate
```

---

# 19. Validation

## Structural

- один START;
- минимум один END;
- нет orphan nodes;
- все transitions валидны;
- нет unreachable nodes;
- parallel split имеет join или explicit detached policy;
- condition имеет default transition;
- subflow не создаёт запрещённую recursion.

## Contract

- stage input compatible;
- output mapping валиден;
- required artifact существует;
- publication получает publishable artifact.

## Routing

- нет ambiguous rules с одинаковым priority;
- существует default route;
- trigger conditions валидны.

## Governance

- обязательные Controls применимы;
- forbidden Playbooks не используются;
- Runtime Profile разрешён;
- Knowledge Space classification совместим;
- publication защищена approval.

## Runtime

- timeout допустим;
- retry limits допустимы;
- event wait имеет timeout;
- compensation path существует, если обязателен.

---

# 20. Модель данных

## Flow

```text
Flow
- id UUID PK
- workspace_id UUID FK
- key VARCHAR
- name VARCHAR
- description TEXT
- type VARCHAR
- status VARCHAR
- owner_team_id UUID NULL
- current_published_version_id UUID NULL
- created_by UUID
- created_at TIMESTAMP
- updated_at TIMESTAMP
- archived_at TIMESTAMP NULL
```

Constraint:

```text
UNIQUE(workspace_id, key)
```

## FlowVersion

```text
FlowVersion
- id UUID PK
- flow_id UUID FK
- version_number INTEGER
- semantic_version VARCHAR
- status VARCHAR
- graph_json JSONB
- trigger_definitions_json JSONB
- routing_policy_json JSONB
- completion_policy_json JSONB
- cancellation_policy_json JSONB
- default_runtime_profile_id UUID FK NULL
- default_knowledge_space_id UUID FK NULL
- checksum VARCHAR
- created_by UUID
- created_at TIMESTAMP
- published_by UUID NULL
- published_at TIMESTAMP NULL
- deprecated_at TIMESTAMP NULL
```

## FlowNode

```text
FlowNode
- id UUID PK
- flow_version_id UUID FK
- node_key VARCHAR
- node_type VARCHAR
- name VARCHAR
- position_json JSONB
- configuration_json JSONB
- created_at TIMESTAMP
```

## FlowTransition

```text
FlowTransition
- id UUID PK
- flow_version_id UUID FK
- source_node_key VARCHAR
- target_node_key VARCHAR
- label VARCHAR NULL
- condition_expression TEXT NULL
- priority INTEGER
- is_default BOOLEAN
```

## FlowStageReference

```text
FlowStageReference
- id UUID PK
- flow_version_id UUID FK
- node_key VARCHAR
- playbook_version_id UUID FK
- runtime_profile_id UUID NULL
- knowledge_space_id UUID NULL
- input_mapping_json JSONB
- output_mapping_json JSONB
- retry_policy_json JSONB
- timeout_seconds INTEGER NULL
- failure_behavior VARCHAR
```

## FlowTrigger

```text
FlowTrigger
- id UUID PK
- flow_version_id UUID FK
- trigger_type VARCHAR
- source_type VARCHAR NULL
- configuration_json JSONB
- enabled BOOLEAN
```

## FlowRoutingRule

```text
FlowRoutingRule
- id UUID PK
- flow_version_id UUID FK
- priority INTEGER
- conditions_json JSONB
- is_default BOOLEAN
- enabled BOOLEAN
```

## FlowValidationRun

```text
FlowValidationRun
- id UUID PK
- flow_version_id UUID FK
- status VARCHAR
- result_json JSONB
- started_at TIMESTAMP
- completed_at TIMESTAMP
```

## FlowSimulationRun

```text
FlowSimulationRun
- id UUID PK
- flow_version_id UUID FK
- input_json JSONB
- mocked_outcomes_json JSONB
- selected_path_json JSONB
- result_json JSONB
- status VARCHAR
- created_by UUID
- created_at TIMESTAMP
```

---

# 21. REST API

## Flows

```http
GET    /api/v1/flows
POST   /api/v1/flows
GET    /api/v1/flows/{flowId}
PATCH  /api/v1/flows/{flowId}
DELETE /api/v1/flows/{flowId}
POST   /api/v1/flows/{flowId}/archive
POST   /api/v1/flows/{flowId}/restore
POST   /api/v1/flows/{flowId}/duplicate
```

## Versions

```http
GET  /api/v1/flows/{flowId}/versions
POST /api/v1/flows/{flowId}/versions
GET  /api/v1/flows/{flowId}/versions/{versionId}
PATCH /api/v1/flows/{flowId}/versions/{versionId}
POST /api/v1/flows/{flowId}/versions/{versionId}/validate
POST /api/v1/flows/{flowId}/versions/{versionId}/publish
POST /api/v1/flows/{flowId}/versions/{versionId}/deprecate
POST /api/v1/flows/{flowId}/versions/{versionId}/clone
```

## Graph

```http
GET  /api/v1/flows/{flowId}/versions/{versionId}/graph
PUT  /api/v1/flows/{flowId}/versions/{versionId}/graph
POST /api/v1/flows/{flowId}/versions/{versionId}/graph/validate
POST /api/v1/flows/{flowId}/versions/{versionId}/simulate
```

## Routing and triggers

```http
GET  /api/v1/flows/{flowId}/versions/{versionId}/routing
PUT  /api/v1/flows/{flowId}/versions/{versionId}/routing
GET  /api/v1/flows/{flowId}/versions/{versionId}/triggers
PUT  /api/v1/flows/{flowId}/versions/{versionId}/triggers
POST /api/v1/flows/route
```

## Usage

```http
GET /api/v1/flows/{flowId}/usage
GET /api/v1/flows/{flowId}/executions
GET /api/v1/flows/{flowId}/audit
```

---

# 22. API examples

## Create Flow

```json
{
  "key": "feature-delivery",
  "name": "Feature Delivery",
  "description": "End-to-end governed feature lifecycle",
  "type": "FEATURE_DELIVERY",
  "ownerTeamId": "uuid"
}
```

## Create Version

```json
{
  "semanticVersion": "1.0.0",
  "defaultRuntimeProfileId": "uuid",
  "defaultKnowledgeSpaceId": "uuid"
}
```

## Route request

```json
{
  "workspaceId": "uuid",
  "source": {
    "type": "JIRA",
    "projectKey": "PAY",
    "issueType": "Feature",
    "labels": ["customer-impact"]
  }
}
```

Response:

```json
{
  "flowVersionId": "uuid",
  "matchedRuleId": "uuid",
  "reasons": [
    "projectKey = PAY",
    "issueType = Feature"
  ]
}
```

---

# 23. Runtime Logic

## 23.1. Start

1. Ingress создаёт WorkRequest.
2. Router выбирает Flow Version.
3. Execution Service создаёт Execution.
4. Создаётся frozen snapshot.
5. Запускается Temporal ExecutionWorkflow.

## 23.2. Stage execution

Для каждого stage:

1. Resolve node configuration.
2. Create PlaybookRun или special node run.
3. Map input.
4. Apply Rules and Controls.
5. Resolve Knowledge Space.
6. Resolve Runtime Profile.
7. Start child PlaybookWorkflow.
8. Wait completion.
9. Validate output.
10. Map output.
11. Evaluate transitions.
12. Select next node.

## 23.3. Condition

Condition получает только разрешённый context.

Пример:

```text
$.playbookRuns.requirements-review.outcome == "APPROVED"
```

## 23.4. Parallel

Temporal должен запускать child workflows параллельно.

Join policies:

```text
ALL
ANY
QUORUM
FIRST_SUCCESS
```

## 23.5. Wait Event

Workflow ждёт signal.

Поддержать:

- correlation key;
- timeout;
- timeout transition;
- duplicate event handling.

## 23.6. Failure

Failure behavior:

```text
FAIL_FLOW
RETRY_STAGE
GO_TO_STAGE
ASK_HUMAN
CONTINUE_WITH_WARNING
RUN_COMPENSATION
```

---

# 24. Temporal Workflows

```text
ExecutionWorkflow
  └── FlowRuntimeWorkflow
        ├── PlaybookWorkflow
        ├── SubflowWorkflow
        ├── WaitEvent
        ├── HumanDecision
        └── CompensationWorkflow
```

Activities:

```text
LoadFlowSnapshotActivity
CreateFlowRunActivity
CreateStageRunActivity
MapStageInputActivity
StartPlaybookActivity
ValidateStageOutputActivity
EvaluateTransitionActivity
PublishFlowEventActivity
FinalizeFlowActivity
```

Signals:

```text
external_event_received
human_decision_received
pause_requested
resume_requested
cancel_requested
```

Queries:

```text
get_current_stage
get_selected_path
get_pending_wait
get_progress
get_flow_state
```

---

# 25. Kafka Events

Topic:

```text
flow-events
```

Events:

```text
flow.created
flow.version.created
flow.version.validated
flow.version.published
flow.execution.started
flow.stage.started
flow.stage.completed
flow.stage.failed
flow.transition.selected
flow.wait.started
flow.wait.completed
flow.compensation.started
flow.execution.completed
flow.execution.failed
```

---

# 26. Execution Snapshot

Snapshot содержит:

```json
{
  "flow": {
    "flowVersionId": "uuid",
    "checksum": "sha256",
    "graph": {},
    "routing": {},
    "completionPolicy": {},
    "cancellationPolicy": {}
  },
  "playbookVersions": [],
  "runtimeProfiles": [],
  "knowledgeSpaces": [],
  "rules": [],
  "controls": []
}
```

Новые публикации не должны менять running execution.

---

# 27. Интеграция с Playbooks

Flow ссылается только на published Playbook Version.

При публикации Flow:

- Playbook Version должна быть PUBLISHED;
- contracts должны быть совместимы;
- deprecated Playbook запрещён;
- mandatory Controls должны быть удовлетворены.

---

# 28. Интеграция с Knowledge Spaces

Flow может задавать:

- default Space;
- stage override;
- routing by domain;
- multiple Spaces;
- temporary Space.

---

# 29. Интеграция с Rules

Rules могут применяться на уровне:

```text
FLOW
STAGE
PLAYBOOK
EXECUTION
```

Flow не хранит Rule content, только requirements или bindings.

---

# 30. Интеграция с Controls

Controls могут:

- требовать stage;
- запрещать transition;
- требовать Human Decision;
- ограничивать routing;
- требовать compensation;
- запрещать publication без approval.

---

# 31. Backend architecture

```text
modules/flows/
├── domain/
│   ├── Flow
│   ├── FlowVersion
│   ├── FlowNode
│   ├── FlowTransition
│   ├── Trigger
│   ├── RoutingRule
│   └── Policies
├── application/
│   ├── CreateFlow
│   ├── CreateFlowVersion
│   ├── ValidateFlow
│   ├── PublishFlow
│   ├── SimulateFlow
│   ├── RouteWorkRequest
│   └── CompareFlowVersions
├── infrastructure/
├── api/
└── tests/
```

Services:

```text
FlowGraphValidator
FlowContractValidator
FlowRoutingEngine
FlowSimulationEngine
FlowSnapshotBuilder
FlowRuntimeService
TransitionEvaluator
StageInputMapper
StageOutputMapper
```

---

# 32. Frontend architecture

```text
pages/flows/
├── FlowsCatalogPage
├── FlowDetailPage
├── FlowDesignerPage
├── FlowSimulationPage
└── FlowRoutingPage

features/flows/
├── create-flow
├── edit-flow
├── publish-flow
├── validate-flow
├── simulate-flow
├── configure-routing
└── compare-versions
```

Components:

```text
FlowCard
FlowTable
FlowStatusBadge
FlowCanvas
FlowNode
FlowEdge
FlowInspector
RoutingRuleBuilder
TriggerEditor
SimulationPanel
VersionDiffViewer
ProblemsPanel
```

---

# 33. RBAC

Permissions:

```text
flow.read
flow.create
flow.edit
flow.validate
flow.publish
flow.archive
flow.simulate
flow.route_preview
flow.execution.read
flow.audit.read
```

---

# 34. Audit Events

```text
flow.created
flow.updated
flow.archived
flow.version.created
flow.version.updated
flow.version.validated
flow.version.published
flow.version.deprecated
flow.simulated
flow.routing.previewed
flow.execution.started
flow.stage.transitioned
```

---

# 35. Нефункциональные требования

- catalog API p95 < 500 ms;
- graph save p95 < 1 s;
- validation p95 < 2 s;
- route preview p95 < 300 ms;
- simulation p95 < 5 s;
- до 10 000 Flows;
- до 200 nodes в Flow;
- до 500 transitions;
- autosave каждые 5 секунд;
- optimistic locking;
- immutable published versions;
- graph rendering 60 FPS до 100 nodes;
- full tracing.

---

# 36. Тестирование

## Unit

- routing rules;
- transition evaluation;
- graph validation;
- contract validation;
- mapping;
- completion policy;
- retry policy;
- cancellation;
- parallel join.

## Integration

- create/publish;
- route;
- snapshot;
- Temporal stage progression;
- signals;
- compensation;
- audit.

## UI

- catalog filters;
- designer;
- connect nodes;
- inspector;
- validation;
- simulation;
- version compare.

## E2E

```text
Create Flow
→ Add Playbook stages
→ Configure transitions
→ Configure routing
→ Validate
→ Publish
→ Route Jira feature
→ Start Execution
→ Run stages
→ Human decision
→ Complete
→ Inspect selected path
```

---

# 37. Миграция текущего прототипа

1. Найти текущую страницу Flows.
2. Найти mock graph.
3. Сохранить UI стиль.
4. Ввести Flow и FlowVersion.
5. Добавить routes:
   - `/flows`;
   - `/flows/:id`;
   - `/flows/:id/versions/:versionId/designer`;
   - `/flows/:id/versions/:versionId/simulate`.
6. Добавить CRUD API.
7. Добавить graph persistence.
8. Добавить validation.
9. Добавить routing engine.
10. Интегрировать Temporal.

---

# 38. Последовательность Pull Requests

## PR-1

- catalog;
- detail shell;
- navigation;
- tests.

## PR-2

- DB schema;
- CRUD;
- versions.

## PR-3

- Designer;
- graph save;
- structural validation.

## PR-4

- routing;
- triggers;
- contract validation.

## PR-5

- simulation;
- version compare;
- publish.

## PR-6

- Temporal runtime;
- snapshot;
- Audit/Kafka.

---

# 39. Vertical Slice

```text
Jira Feature PAY-123
  ↓
Routing selects Feature Delivery Flow
  ↓
Business Requirements Playbook
  ↓
System Requirements Playbook
  ↓
Human Approval
  ↓
Development Playbook
  ↓
Testing Playbook
  ↓
Release Playbook
  ↓
Execution Completed
```

---

# 40. Definition of Done

Раздел завершён, если:

- Flow создаётся;
- версии работают;
- Designer работает;
- nodes и transitions сохраняются;
- validation блокирует invalid graph;
- routing объясним;
- triggers работают;
- simulation показывает path;
- published version immutable;
- Execution Snapshot фиксирует Flow;
- Temporal проходит stages;
- parallel и wait event работают;
- compensation работает;
- RBAC работает;
- Audit и Kafka работают;
- tests проходят;
- production mocks отсутствуют.

---

# 41. Первое задание coding-агенту

1. Просканируй репозиторий.
2. Найди текущий раздел Flows.
3. Создай `docs/flows/CURRENT_STATE.md`.
4. Сравни текущую реализацию с этим ТЗ.
5. Создай schema `flows` и `flow_versions`.
6. Реализуй read-only catalog API.
7. Подключи текущий UI к API.
8. Добавь detail shell.
9. Добавь tests.
10. Обнови `docs/IMPLEMENTATION_STATUS.md`.
11. Не начинай Temporal runtime до прохождения graph validation tests.

---

# 42. Итоговая модель

```text
Work Request
  ↓
Routing
  ↓
Flow Version
  ├── Trigger
  ├── Routing Rules
  ├── Stage Graph
  ├── Completion Policy
  └── Cancellation Policy
        ↓
Stage
  ↓
Playbook Version
  ↓
Playbook Runtime
  ↓
Next Transition
```

Конец документа.
