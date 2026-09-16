# Системные требования к подсистеме Playbooks
## Governed AI Delivery Platform

**Статус:** целевая спецификация для реализации существующего прототипа  
**Аудитория:** coding agent в Cursor, backend/frontend разработчики, архитекторы, QA, compliance  
**Главный принцип:** Playbook является регулируемой и версионируемой реализацией одного вида работ PDLC. Playbook не является Agent и не является сквозным Flow.

---

## 1. Назначение подсистемы

Подсистема Playbooks должна позволять создавать, проверять, публиковать и исполнять управляемые процессы одного этапа жизненного цикла продукта или ПО.

Примеры Playbooks:

- Business Requirements;
- System Requirements;
- Architecture Review;
- Code Change;
- Code Review;
- Test Design;
- Test Execution;
- Release Readiness;
- Incident Root Cause Analysis.

Playbook отвечает на вопрос: **как выполнить конкретный вид работы с обязательными проверками, заменяемыми Skills, управлением контекстом и участием человека**.

Playbook не должен:

- представлять полного виртуального сотрудника;
- хранить прямые ссылки на Jira, Slack, Confluence или MCP tools;
- описывать весь PDLC от идеи до production;
- исполняться одним большим prompt;
- изменяться после публикации;
- позволять удалять обязательные Controls.

---

## 2. Место Playbook в общей модели

```text
External Work Item
        ↓
Routing
        ↓
Flow
        ↓
Playbook Version
        ↓
Playbook Graph
        ↓
Steps
        ↓
Skill Slots → Skill Bindings → Skill Versions
        ↓
Capabilities → Capability Gateway → Providers / MCP
```

На исполнение дополнительно влияют:

```text
Rules
Control Packs
Knowledge Space
Runtime Profile
Human Supervision
Execution Snapshot
Case Context
```

### 2.1. Отличие от Flow

| Сущность | Назначение |
|---|---|
| Flow | Сквозная последовательность нескольких этапов PDLC |
| Playbook | Реализация одного этапа или одного вида работ |
| Skill | Одна когнитивная операция |
| Runtime Profile | Техническая конфигурация исполнения |

### 2.2. Отличие от Skill

Playbook управляет порядком и правилами. Skill выполняет интеллектуальное преобразование.

```text
Playbook: System Requirements
  1. Regulatory intake
  2. Understand problem          ← Skill Slot
  3. Explore context             ← Adaptive Zone
  4. Generate requirements       ← Skill Slot
  5. Validate coverage           ← Control Gate
  6. Architecture approval       ← Human Checkpoint
  7. Publish artifact            ← Publication Step
```

---

## 3. Пользовательские разделы

## 3.1. Playbooks Catalog

### Назначение

Каталог предназначен для поиска и управления Playbooks. Это не конструктор и не диаграмма.

### Обязательные элементы UI

- заголовок и описание раздела;
- кнопка `New Playbook`;
- метрики Published, Drafts, Executions, Control Coverage;
- текстовый поиск;
- фильтр Family;
- фильтр Status;
- фильтр Owner;
- сортировка;
- таблица или карточки Playbooks;
- pagination;
- bulk archive только для черновиков или deprecated;
- переход на Playbook Detail.

### Колонки списка

- name;
- family;
- latest published version;
- current draft version;
- steps count;
- skill slots count;
- controls count;
- executions in 30 days;
- owner;
- status;
- actions.

### Действия

- open;
- create draft;
- clone;
- compare versions;
- deprecate;
- archive;
- view usage;
- open Designer.

### Состояния

- loading;
- empty workspace;
- no search results;
- permission denied;
- backend unavailable;
- stale data;
- success notification;
- validation failure.

---

## 3.2. Playbook Detail

### Назначение

Экран конфигурации и наблюдения. Он показывает опубликованную версию или выбранный draft, но не заменяет Designer.

### Header

- name;
- description;
- family;
- owner;
- status;
- semantic version;
- validation status;
- `Open Designer`;
- `Create draft`;
- `Publish` при наличии прав;
- overflow actions.

### Вкладки

#### Overview

- purpose;
- input contract;
- output contract;
- execution structure;
- applicable control packs;
- usage metrics;
- consuming Flows;
- ownership;
- permissions.

#### Steps

- упорядоченный список steps;
- type;
- interface key;
- timeout;
- retry policy;
- supervision mode;
- immutable status;
- required capabilities;
- validation errors.

#### Skill Bindings

- slot key;
- interface;
- resolved implementation;
- binding scope;
- priority;
- conditions;
- compatibility;
- fallback implementation.

#### Controls

- control pack;
- source level;
- mandatory status;
- injected locked steps;
- control gates;
- evidence requirements;
- publication restrictions.

#### Versions

- version history;
- author;
- status;
- created/published dates;
- diff;
- restore as new draft;
- deprecate.

#### Executions

- recent executions;
- success rate;
- duration;
- failure reasons;
- open in Execution Inspector.

---

## 3.3. Playbook Designer

### Назначение

Fullscreen IDE для редактирования draft-версии Playbook.

Designer не должен выглядеть как BPMN-редактор. Основной объект — вертикальная цепочка смысловых карточек с ветвлениями.

### Области Designer

#### Top Bar

- back;
- Playbook name;
- draft version;
- autosave status;
- undo;
- redo;
- validate;
- simulate;
- compare;
- publish.

#### Palette

- Skill Slot;
- Locked Step;
- Adaptive Zone;
- Control Gate;
- Human Checkpoint;
- Conditional Branch;
- Parallel Branch;
- Merge;
- Artifact Boundary;
- Publication Step.

#### Canvas

- start/end nodes;
- вертикальное размещение по умолчанию;
- drag-and-drop;
- keyboard navigation;
- branches;
- zoom;
- fit to screen;
- minimap;
- selection;
- copy/paste;
- undo/redo;
- inline validation badges;
- read-only rendering опубликованной версии.

#### Inspector

Показывает свойства выбранного узла и валидирует их до сохранения.

#### Problems Panel

- errors;
- warnings;
- info;
- переход к проблемному node;
- filtering;
- blocking indicator.

#### Simulation Panel

- test input;
- resolved bindings;
- resolved controls;
- expected path;
- branches;
- context estimate;
- capability estimate;
- checkpoints;
- validation outcome.

---

## 4. Типы узлов Playbook Graph

## 4.1. START

Автоматически создаётся системой. Ровно один на граф.

Ограничения:

- нельзя удалить;
- не имеет входящих связей;
- должна быть хотя бы одна исходящая связь.

## 4.2. END

Ровно один логический terminal для простого Playbook. Допускается несколько terminal nodes при нормализации в общий END.

## 4.3. SKILL_SLOT

Ссылка на стабильный Skill Interface, а не на конкретную реализацию.

Поля:

```yaml
key: generate-requirements
name: Generate requirements
type: SKILL_SLOT
interface: analysis.system_requirements.generate@1
input_contract: ProblemUnderstandingArtifact@1
output_contract: SystemRequirementsPatch@1
required_capabilities:
  - context.search
  - context.read
  - artifact.read
  - artifact.patch
timeout_seconds: 900
retry_policy:
  maximum_attempts: 3
  backoff: exponential
context_budget:
  max_tokens: 24000
supervision_mode: OBSERVE
binding_policy:
  fallback_allowed: true
```

Runtime разрешает implementation через frozen Execution Snapshot.

## 4.4. LOCKED_STEP

Обязательный неизменяемый шаг, внедрённый Control Pack или владельцем регулируемого шаблона.

Поля:

- control source;
- immutable reason;
- instruction reference;
- input/output contracts;
- evidence requirement;
- failure behavior;
- timeout.

Пользователь не может удалить или отключить Locked Step. Изменение возможно только через новую версию Control Pack.

## 4.5. ADAPTIVE_ZONE

Ограниченная область, где runtime может выбрать дополнительные действия.

Поля:

- allowed capabilities;
- allowed Skill Interfaces;
- max actions;
- max duration;
- max tokens;
- stop conditions;
- required rationale;
- escalation threshold.

Adaptive Zone не может:

- удалить следующие steps;
- обойти Control Gate;
- вызвать неразрешённый capability;
- изменить frozen snapshot;
- публиковать результат без Publication Step.

## 4.6. CONTROL_GATE

Выполняет Control Engine evaluation.

Поля:

- control references;
- evaluation moment;
- blocking mode;
- evidence requirements;
- remediation path;
- override policy.

Результаты:

```text
PASS
PASS_WITH_WARNING
REQUIRES_REVIEW
BLOCK
ERROR
```

## 4.7. HUMAN_CHECKPOINT

Создаёт Approval Request и приостанавливает Temporal workflow.

Поля:

- supervision mode;
- requested role;
- assignment policy;
- SLA;
- escalation policy;
- allowed decisions;
- comment required;
- payload template;
- return path after request changes.

## 4.8. CONDITIONAL_BRANCH

Ветвление по детерминированному выражению.

Условия не должны исполнять произвольный код.

Разрешённый expression DSL:

```text
artifact.riskLevel == "HIGH"
controlResult.status == "REQUIRES_REVIEW"
caseContext.openQuestions.count > 0
signal.name == "security-impact"
```

## 4.9. PARALLEL_BRANCH и MERGE

Позволяет запустить независимые ветви.

Merge policy:

```text
ALL
ANY
QUORUM
CUSTOM_CONTROLLED
```

Обязательна стратегия разрешения конфликтующих Artifact Patches.

## 4.10. ARTIFACT_BOUNDARY

Создаёт или фиксирует новую логическую фазу Artifact.

Используется для:

- schema validation;
- snapshot;
- review boundary;
- handoff contract;
- разделения черновика и утверждённого результата.

## 4.11. PUBLICATION_STEP

Публикует только утверждённую Artifact Version через capability `publisher.publish`.

Поля:

- destination policy;
- content projection;
- idempotency strategy;
- pre-publication Controls;
- required approval;
- failure compensation.

---

## 5. Жизненный цикл Playbook

```text
DRAFT
  ↓ validate
VALIDATING
  ↓ no blocking errors
READY
  ↓ publish approval
PUBLISHED
  ↓ newer version
SUPERSEDED
  ↓ explicit policy
DEPRECATED
  ↓ retention expiration
ARCHIVED
```

### Правила

1. Только `DRAFT` разрешено редактировать.
2. `PUBLISHED` является immutable.
3. Изменение опубликованного Playbook создаёт новую draft version.
4. Execution всегда использует конкретный `playbook_version_id`.
5. Удаление физической записи запрещено, если версия использовалась в Execution.
6. Archive является soft-delete.
7. Major version изменяется при несовместимом input/output contract или Skill Interface.
8. Minor version изменяется при добавлении совместимых steps или Controls.
9. Patch version изменяется при metadata, rules defaults и незначительных исправлениях.

---

## 6. Модель данных

## 6.1. playbooks

```sql
CREATE TABLE playbooks (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    key VARCHAR(150) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    family VARCHAR(80) NOT NULL,
    owner_team_id UUID,
    status VARCHAR(30) NOT NULL,
    current_published_version_id UUID,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    revision BIGINT NOT NULL DEFAULT 1,
    UNIQUE(workspace_id, key)
);
```

## 6.2. playbook_versions

```sql
CREATE TABLE playbook_versions (
    id UUID PRIMARY KEY,
    playbook_id UUID NOT NULL REFERENCES playbooks(id),
    version_number INTEGER NOT NULL,
    semantic_version VARCHAR(40) NOT NULL,
    status VARCHAR(30) NOT NULL,
    graph_json JSONB NOT NULL,
    input_contract_key VARCHAR(180) NOT NULL,
    output_contract_key VARCHAR(180) NOT NULL,
    validation_status VARCHAR(30) NOT NULL,
    validation_report JSONB,
    checksum VARCHAR(128) NOT NULL,
    created_by UUID NOT NULL,
    published_by UUID,
    created_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ,
    revision BIGINT NOT NULL DEFAULT 1,
    UNIQUE(playbook_id, version_number),
    UNIQUE(playbook_id, semantic_version)
);
```

## 6.3. playbook_nodes

Нормализованная проекция graph JSON для поиска, аналитики и referential validation.

```sql
CREATE TABLE playbook_nodes (
    id UUID PRIMARY KEY,
    playbook_version_id UUID NOT NULL REFERENCES playbook_versions(id),
    node_key VARCHAR(150) NOT NULL,
    node_type VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    interface_key VARCHAR(180),
    immutable BOOLEAN NOT NULL DEFAULT FALSE,
    control_source VARCHAR(180),
    config_json JSONB NOT NULL,
    position_json JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE(playbook_version_id, node_key)
);
```

## 6.4. playbook_edges

```sql
CREATE TABLE playbook_edges (
    id UUID PRIMARY KEY,
    playbook_version_id UUID NOT NULL REFERENCES playbook_versions(id),
    edge_key VARCHAR(150) NOT NULL,
    source_node_key VARCHAR(150) NOT NULL,
    target_node_key VARCHAR(150) NOT NULL,
    condition_expression TEXT,
    priority INTEGER,
    config_json JSONB NOT NULL,
    UNIQUE(playbook_version_id, edge_key)
);
```

## 6.5. playbook_control_bindings

```sql
CREATE TABLE playbook_control_bindings (
    id UUID PRIMARY KEY,
    playbook_version_id UUID NOT NULL,
    control_pack_version_id UUID NOT NULL,
    source_level VARCHAR(30) NOT NULL,
    mandatory BOOLEAN NOT NULL,
    resolved_definition JSONB NOT NULL
);
```

## 6.6. skill_bindings

```sql
CREATE TABLE skill_bindings (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL,
    scope_type VARCHAR(40) NOT NULL,
    scope_id UUID,
    playbook_id UUID,
    node_key VARCHAR(150),
    interface_key VARCHAR(180) NOT NULL,
    skill_version_id UUID NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    conditions_json JSONB,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL
);
```

## 6.7. playbook_validation_runs

```sql
CREATE TABLE playbook_validation_runs (
    id UUID PRIMARY KEY,
    playbook_version_id UUID NOT NULL,
    status VARCHAR(30) NOT NULL,
    report_json JSONB NOT NULL,
    validator_version VARCHAR(50) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ
);
```

## 6.8. playbook_simulations

```sql
CREATE TABLE playbook_simulations (
    id UUID PRIMARY KEY,
    playbook_version_id UUID NOT NULL,
    input_json JSONB NOT NULL,
    resolved_snapshot_json JSONB NOT NULL,
    result_json JSONB,
    status VARCHAR(30) NOT NULL,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ
);
```

---

## 7. Graph document format

```json
{
  "schemaVersion": "playbook-graph@1",
  "playbookVersionId": "uuid",
  "entryNodeKey": "start",
  "nodes": [
    {
      "key": "start",
      "type": "START",
      "name": "Start",
      "config": {}
    },
    {
      "key": "understand-problem",
      "type": "SKILL_SLOT",
      "name": "Understand problem",
      "config": {
        "interfaceKey": "analysis.problem.understand@1",
        "inputContract": "WorkItemArtifact@1",
        "outputContract": "ProblemUnderstandingPatch@1",
        "requiredCapabilities": ["context.search", "context.read", "artifact.patch"],
        "timeoutSeconds": 600,
        "retryPolicy": {"maximumAttempts": 3},
        "contextBudget": {"maxTokens": 16000},
        "supervisionMode": "OBSERVE"
      }
    },
    {
      "key": "approval",
      "type": "HUMAN_CHECKPOINT",
      "name": "Architecture approval",
      "config": {
        "requestedRole": "SolutionArchitect",
        "allowedDecisions": ["APPROVE", "REJECT", "REQUEST_CHANGES"],
        "slaSeconds": 86400,
        "commentRequiredFor": ["REJECT", "REQUEST_CHANGES"]
      }
    }
  ],
  "edges": [
    {"key": "e1", "source": "start", "target": "understand-problem"},
    {"key": "e2", "source": "understand-problem", "target": "approval"}
  ]
}
```

---

## 8. REST API

Base path:

```text
/api/v1
```

## 8.1. Catalog

```http
GET /playbooks
```

Query parameters:

```text
workspaceId
query
family
status
ownerTeamId
usedInFlowId
limit
cursor
sort
```

```http
POST /playbooks
GET /playbooks/{playbookId}
PATCH /playbooks/{playbookId}
DELETE /playbooks/{playbookId}
POST /playbooks/{playbookId}/clone
GET /playbooks/{playbookId}/usage
```

## 8.2. Versions

```http
GET  /playbooks/{playbookId}/versions
POST /playbooks/{playbookId}/versions
GET  /playbooks/{playbookId}/versions/{versionId}
POST /playbooks/{playbookId}/versions/{versionId}/clone
POST /playbooks/{playbookId}/versions/{versionId}/validate
POST /playbooks/{playbookId}/versions/{versionId}/publish
POST /playbooks/{playbookId}/versions/{versionId}/deprecate
GET  /playbooks/{playbookId}/versions/{versionId}/diff?against={otherVersionId}
```

## 8.3. Graph

```http
GET  /playbooks/{playbookId}/versions/{versionId}/graph
PUT  /playbooks/{playbookId}/versions/{versionId}/graph
PATCH /playbooks/{playbookId}/versions/{versionId}/graph
POST /playbooks/{playbookId}/versions/{versionId}/graph/validate
GET  /playbooks/{playbookId}/versions/{versionId}/graph/problems
```

`PUT` должен поддерживать optimistic locking:

```http
If-Match: "17"
```

При конфликте вернуть `409 PLAYBOOK_VERSION_CONFLICT`.

## 8.4. Simulation

```http
POST /playbooks/{playbookId}/versions/{versionId}/simulations
GET  /playbooks/{playbookId}/versions/{versionId}/simulations/{simulationId}
```

Simulation не вызывает write-capabilities и не публикует результат.

## 8.5. Bindings

```http
GET  /playbooks/{playbookId}/versions/{versionId}/bindings
POST /playbooks/{playbookId}/versions/{versionId}/bindings/resolve
PUT  /playbooks/{playbookId}/bindings/{bindingId}
```

## 8.6. Controls

```http
GET  /playbooks/{playbookId}/versions/{versionId}/controls
POST /playbooks/{playbookId}/versions/{versionId}/controls/resolve
POST /playbooks/{playbookId}/versions/{versionId}/controls/evaluate
```

## 8.7. Executions

```http
GET  /playbooks/{playbookId}/executions
POST /playbooks/{playbookId}/versions/{versionId}/executions
```

---

## 9. API contracts

### 9.1. Create Playbook

```json
{
  "workspaceId": "uuid",
  "key": "system-requirements",
  "name": "System Requirements",
  "description": "Generate governed system requirements",
  "family": "ANALYSIS",
  "ownerTeamId": "uuid",
  "templateKey": "governed-empty@1"
}
```

### 9.2. Validation response

```json
{
  "data": {
    "status": "FAILED",
    "blocking": true,
    "problems": [
      {
        "severity": "ERROR",
        "code": "SKILL_IMPLEMENTATION_NOT_FOUND",
        "nodeKey": "generate-requirements",
        "path": "nodes.generate-requirements.config.interfaceKey",
        "message": "No compatible published skill implementation is available"
      }
    ]
  }
}
```

### 9.3. Publish request

```json
{
  "expectedRevision": 17,
  "semanticVersion": "3.3.0",
  "changeSummary": "Added evidence coverage gate",
  "approvalReference": "approval-uuid"
}
```

---

## 10. Валидация Playbook

Публикация запрещена при любой blocking problem.

### 10.1. Structural validation

- один START;
- минимум один END;
- START не имеет incoming edge;
- END не имеет outgoing edge;
- нет dangling edges;
- все nodes достижимы;
- нет бесконтрольных циклов;
- branch имеет минимум две ветви;
- parallel branch имеет Merge;
- node keys уникальны.

### 10.2. Contract validation

- output предыдущего step совместим с input следующего;
- Artifact Patch schema зарегистрирована;
- handoff contract определён;
- Publication Step получает publishable Artifact.

### 10.3. Skill validation

- Skill Slot содержит interface key;
- interface существует и published;
- существует минимум одна совместимая Skill Version;
- required capabilities зарегистрированы;
- runtime поддерживает Skill package;
- fallback policy выполнима.

### 10.4. Control validation

- все mandatory Control Packs разрешены;
- injected Locked Steps присутствуют и не изменены;
- обязательные Control Gates присутствуют;
- Human Checkpoint соответствует effective supervision;
- publication policy выполнена;
- evidence requirements покрыты.

### 10.5. Runtime validation

- timeout в допустимом диапазоне;
- retry policy не превышает platform limits;
- context budget допустим;
- Adaptive Zone имеет лимиты;
- provider restrictions выполнимы;
- секреты доступны через reference.

---

## 11. Skill Binding Resolution

Skill Slot не хранит прямой `skill_version_id` в graph.

Resolver использует приоритет scope:

```text
Execution Override
Playbook Binding
Flow Binding
Knowledge Space Binding
Team Binding
Workspace Binding
Platform Default
```

Алгоритм:

1. Получить interface key и major version.
2. Найти enabled bindings.
3. Отфильтровать по scope.
4. Отфильтровать по conditions.
5. Проверить published status Skill Version.
6. Проверить input/output compatibility.
7. Проверить Runtime Profile compatibility.
8. Проверить required capabilities.
9. Отсортировать по scope specificity и priority.
10. Выбрать implementation.
11. Выбрать fallback implementations.
12. Сохранить результат в Execution Snapshot.

После старта Execution binding не пересчитывается.

---

## 12. Control Spine Resolution

При создании draft Designer отображает эффективный Control Spine.

Источники:

```text
Regulatory
Corporate
Domain / Knowledge Space
Playbook Family
Playbook-specific
Runtime Risk
```

Алгоритм:

1. Получить applicable Control Packs.
2. Отсортировать по level и priority.
3. Объединить ограничения.
4. Вычислить effective supervision.
5. Внедрить Locked Steps.
6. Внедрить или проверить Control Gates.
7. Применить capability restrictions.
8. Применить evidence requirements.
9. Зафиксировать resolved control definition при публикации.

Designer должен визуально отличать:

- user-editable nodes;
- inherited nodes;
- mandatory locked nodes;
- runtime-injected checks.

---

## 13. Runtime-логика исполнения

Для каждого Playbook Run Temporal `PlaybookWorkflow` должен:

1. Загрузить frozen Execution Snapshot.
2. Загрузить graph конкретной Playbook Version.
3. Проверить checksum.
4. Создать `PlaybookRun`.
5. Установить current node = START.
6. Найти следующий node.
7. Выполнить node handler по типу.
8. Сохранить durable state.
9. Применить Artifact Patch атомарно.
10. Записать Evidence и Audit.
11. Определить следующий edge.
12. Повторять до END.
13. Проверить output contract.
14. Завершить Playbook Run.
15. Вернуть Flow handoff result.

### 13.1. Node handlers

```text
StartNodeHandler
EndNodeHandler
SkillSlotNodeHandler
LockedStepNodeHandler
AdaptiveZoneNodeHandler
ControlGateNodeHandler
HumanCheckpointNodeHandler
ConditionalBranchNodeHandler
ParallelBranchNodeHandler
MergeNodeHandler
ArtifactBoundaryNodeHandler
PublicationNodeHandler
```

### 13.2. Skill Slot execution

1. Получить Skill Version из snapshot.
2. Сформировать Stage Brief.
3. Получить relevant Evidence Bundle через Context Broker.
4. Разрешить Rules Bundle.
5. Передать только allowed capabilities.
6. Запустить sandboxed Skill Runtime.
7. Получить structured output.
8. Проверить output schema.
9. Проверить patch base version.
10. Запустить policy validation.
11. Применить patch.
12. Создать новую Artifact Version.
13. Сохранить signals и open questions.
14. Записать token/cost/latency metrics.

### 13.3. Human Checkpoint execution

1. Создать Approval Request.
2. Перевести execution в `WAITING_HUMAN`.
3. Отправить notification event.
4. Ожидать Temporal signal.
5. Проверить RBAC actor.
6. Сохранить immutable decision.
7. В зависимости от decision продолжить, перейти на remediation edge или завершить.

### 13.4. Publication execution

1. Проверить Artifact Version.
2. Проверить pre-publication Controls.
3. Проверить approvals.
4. Разрешить destination provider через Capability Gateway.
5. Использовать idempotency key.
6. Вызвать `publisher.publish`.
7. Сохранить publication record.
8. Добавить external reference в Artifact metadata.

---

## 14. Temporal требования

### Workflow

```text
PlaybookWorkflow
```

### Activities

```text
LoadPlaybookSnapshotActivity
CreatePlaybookRunActivity
ResolveCurrentArtifactActivity
BuildSkillContextActivity
RunSkillActivity
ValidateSkillOutputActivity
ApplyArtifactPatchActivity
EvaluateControlsActivity
CreateApprovalRequestActivity
InvokePublicationActivity
RecordAuditEventActivity
FinalizePlaybookRunActivity
```

### Signals

```text
approval_received
input_provided
pause_requested
resume_requested
cancel_requested
external_event_received
```

### Queries

```text
get_current_node
get_playbook_run_state
get_pending_approval
get_artifact_version
get_execution_path
```

Workflow code не должен напрямую:

- обращаться к БД;
- вызывать LLM;
- вызывать MCP;
- публиковать в Kafka;
- обращаться к HTTP API.

Всё это выполняется Activities.

---

## 15. Kafka events

```text
playbook.created
playbook.draft.created
playbook.validation.started
playbook.validation.completed
playbook.version.published
playbook.version.deprecated
playbook.run.started
playbook.node.started
playbook.node.completed
playbook.node.failed
playbook.run.completed
playbook.run.failed
skill.binding.resolved
control.spine.resolved
approval.requested
approval.resolved
artifact.patch.applied
publication.completed
```

Event envelope должен содержать:

- eventId;
- eventType;
- eventVersion;
- occurredAt;
- workspaceId;
- playbookId;
- playbookVersionId;
- executionId при наличии;
- correlationId;
- causationId;
- actor;
- payload.

---

## 16. Backend архитектура

```text
modules/playbooks/
├── domain/
│   ├── entities/
│   ├── value-objects/
│   ├── graph/
│   ├── validators/
│   ├── policies/
│   └── events/
├── application/
│   ├── commands/
│   ├── queries/
│   ├── services/
│   └── ports/
├── infrastructure/
│   ├── persistence/
│   ├── kafka/
│   ├── temporal/
│   └── cache/
├── api/
│   ├── controllers/
│   ├── dto/
│   └── mappers/
└── tests/
```

### Обязательные domain services

```text
PlaybookGraphValidator
PlaybookVersionService
PlaybookPublisher
ControlSpineResolver
SkillBindingResolver
ContractCompatibilityService
PlaybookSimulationService
PlaybookDiffService
```

Контроллеры не должны содержать бизнес-логику.

---

## 17. Frontend архитектура

```text
pages/
├── playbooks-catalog/
├── playbook-detail/
└── playbook-designer/

features/
├── create-playbook/
├── edit-playbook-metadata/
├── manage-playbook-graph/
├── validate-playbook/
├── publish-playbook/
├── compare-playbook-versions/
├── simulate-playbook/
└── resolve-skill-bindings/

entities/
├── playbook/
├── playbook-version/
├── playbook-node/
├── skill-interface/
├── control-pack/
└── execution/
```

### Frontend state

Server state хранить через query cache. Draft graph допускается держать локально до autosave.

Autosave:

- debounce 1–2 секунды;
- optimistic locking;
- conflict notification;
- offline draft buffer;
- explicit unsaved indicator;
- recovery after refresh.

### Designer technology

Допускается React Flow или аналогичная graph library, но визуальный язык должен быть собственным. Нельзя оставлять стандартный BPMN appearance.

---

## 18. RBAC

### Permissions

```text
playbook.read
playbook.create
playbook.edit
playbook.validate
playbook.simulate
playbook.publish
playbook.deprecate
playbook.archive
playbook.bind-skill
playbook.view-executions
playbook.override-control
```

`playbook.override-control` не даёт права отключить regulatory control. Он применяется только к explicitly overridable policy и требует Audit Event.

### Типовые роли

| Роль | Права |
|---|---|
| Viewer | read |
| ProcessDesigner | create, edit, validate, simulate |
| SkillDeveloper | read, bind-skill |
| ComplianceOfficer | read, validate controls, publish approval |
| WorkspaceAdmin | все workspace operations |
| Auditor | read versions, executions, audit |

---

## 19. Нефункциональные требования

### Надёжность

- immutable published versions;
- idempotent publish;
- optimistic locking;
- transactional outbox;
- Temporal retries;
- no partial Artifact Patch application;
- graph checksum validation.

### Производительность MVP

- catalog p95 < 500 ms;
- detail p95 < 700 ms;
- graph load p95 < 1 s для 200 nodes;
- graph autosave p95 < 800 ms;
- validation p95 < 3 s без внешних health checks;
- simulation start < 2 s.

### Масштаб

- 10 000 Playbooks;
- 100 versions на Playbook;
- 500 nodes на graph;
- 50 concurrent editors на разные drafts;
- 1 000 concurrent Playbook Runs.

### Observability

Метрики:

```text
playbook_validation_duration
playbook_validation_failures_total
playbook_publish_total
playbook_run_duration
playbook_node_duration
playbook_node_failures_total
skill_binding_resolution_duration
control_spine_resolution_duration
playbook_autosave_conflicts_total
```

---

## 20. Тестирование

### Unit tests

- graph validation;
- state transitions;
- semantic version rules;
- binding resolution;
- control spine merge;
- contract compatibility;
- branch evaluation;
- patch conflict detection.

### Integration tests

- PostgreSQL repositories;
- REST API;
- Kafka outbox;
- Temporal activities;
- Skill Registry integration;
- Control Engine integration.

### Frontend tests

- catalog filters;
- open detail;
- tab navigation;
- Designer add/remove nodes;
- locked node protection;
- autosave conflict;
- validation navigation;
- publish permission;
- simulation result.

### End-to-end scenario

```text
Create Playbook
→ add Skill Slot
→ bind Skill
→ receive mandatory Locked Step
→ validate
→ simulate
→ publish
→ use in Flow
→ run Execution
→ wait for approval
→ publish artifact
→ inspect audit
```

---

## 21. Миграция существующего прототипа

ИИ-агент должен сначала изучить текущий репозиторий.

### Шаг 1. Аудит

Создать:

```text
docs/playbooks/CURRENT_STATE.md
docs/playbooks/GAP_ANALYSIS.md
docs/playbooks/MIGRATION_PLAN.md
docs/playbooks/IMPLEMENTATION_STATUS.md
```

### Шаг 2. UI routing

- существующий Playbooks экран превратить в Catalog;
- создать отдельный route Detail;
- создать fullscreen route Designer;
- убрать зависимость от Agents;
- сохранить визуальный стиль прототипа;
- заменить hardcoded navigation.

### Шаг 3. Domain model

- добавить Playbook и PlaybookVersion;
- graph JSON;
- normalized nodes/edges;
- migrations;
- repositories;
- validation service.

### Шаг 4. API

- catalog;
- detail;
- versions;
- graph autosave;
- validate;
- publish;
- simulation stub с реальным resolver.

### Шаг 5. Skills and Controls

- Skill Interface integration;
- binding resolution;
- Control Spine;
- locked nodes.

### Шаг 6. Runtime

- Temporal PlaybookWorkflow;
- node handlers;
- Artifact Patch;
- Human Checkpoint;
- Publication.

Нельзя создавать новый проект вместо миграции, если текущий стек пригоден.

---

## 22. Порядок Pull Requests

### PR-1: Navigation and screens

- Catalog route;
- Detail route;
- Designer route;
- удалить Agents из Playbook dependencies;
- UI tests.

### PR-2: Playbook persistence

- tables;
- migrations;
- CRUD;
- version lifecycle;
- API tests.

### PR-3: Graph editing

- nodes/edges;
- autosave;
- optimistic locking;
- graph validation.

### PR-4: Skill interfaces and bindings

- interface selector;
- resolver;
- compatibility errors.

### PR-5: Controls

- Control Spine resolver;
- Locked Steps;
- publication guards.

### PR-6: Simulation

- resolved snapshot;
- path calculation;
- no-side-effect simulation.

### PR-7: Runtime

- Temporal workflow;
- Skill Slot handler;
- Artifact Patch;
- audit events.

### PR-8: Human and publication

- approvals;
- signals;
- Capability Gateway publication.

---

## 23. Definition of Done

Подсистема Playbooks считается готовой, когда:

1. Пользователь создаёт Playbook.
2. Система автоматически создаёт draft version.
3. Designer позволяет собирать graph.
4. Skill Slot выбирает interface, а не конкретный MCP tool.
5. Binding Resolver показывает выбранный Skill.
6. Mandatory Controls отображаются как locked elements.
7. Locked elements нельзя удалить.
8. Validation показывает ошибки на node и в Problems Panel.
9. Simulation показывает resolved path и bindings.
10. Published version immutable.
11. Новое изменение создаёт draft.
12. Playbook можно включить в Flow.
13. Execution сохраняет frozen Playbook Version.
14. Temporal исполняет nodes по graph.
15. Human Checkpoint приостанавливает execution.
16. Publication выполняется через Capability Gateway.
17. Все действия записываются в Audit.
18. UI не содержит production mock data.
19. RBAC работает.
20. Unit, integration и e2e tests проходят.

---

## 24. Первое задание coding-агенту

1. Просканируй репозиторий.
2. Найди текущие страницы Playbooks и Playbook Designer.
3. Найди модели, API и mock data, связанные с Agents и Playbooks.
4. Создай документы аудита из раздела 21.
5. Сопоставь текущий UI с приложенным UI-прототипом.
6. Не удаляй рабочий код без миграционного обоснования.
7. Реализуй PR-1.
8. Добавь route-level и component tests.
9. Обнови `IMPLEMENTATION_STATUS.md`.
10. После прохождения тестов приступи к PR-2.

---

## 25. Запрещённые решения

- Playbook как один prompt;
- прямой вызов MCP из Playbook или Skill;
- конкретный Skill ID внутри graph вместо interface key;
- изменение published graph;
- удаление mandatory Controls;
- хранение execution state только в frontend;
- произвольный JavaScript в branch conditions;
- вызовы внешних систем из Temporal workflow code;
- публикация draft Artifact;
- использование Agents как владельца поведения Playbook;
- статические mock-ответы в production path.

---

**Конец спецификации.**
