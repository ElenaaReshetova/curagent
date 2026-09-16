# EXECUTIONS_SYSTEM_REQUIREMENTS.md
## Governed AI Delivery Platform
### Полное системное ТЗ на реализацию раздела Executions

---

# 0. Простое назначение Executions

Execution — это конкретный запуск Flow, Playbook или Skill в определённом контексте.

Он отвечает на вопрос:

> Что именно произошло во время выполнения, с какими версиями, данными, решениями, ошибками и результатами?

Пример:

```text
Execution: EXE-2026-004182

Source:
- Jira PAY-123

Flow:
- Feature Delivery v2.4.0

Current stage:
- System Requirements

Status:
- WAITING_FOR_HUMAN

Artifacts:
- Business Requirements v3
- System Requirements Draft v1

Evidence:
- 14 items

Pending:
- Architecture approval
```

Execution — это не шаблон процесса. Это его фактический экземпляр.

---

# 1. Место в архитектуре

```text
Work Request
  ↓
Routing
  ↓
Flow / Playbook / Skill Version
  ↓
Execution Snapshot
  ↓
Execution Runtime
  ↓
Stage Runs
  ↓
Playbook Runs
  ↓
Skill Runs
  ↓
Artifacts + Evidence + Decisions
```

---

# 2. Границы ответственности

Execution отвечает за:

- frozen snapshot;
- runtime state;
- progress;
- stage runs;
- playbook runs;
- skill runs;
- attempts;
- artifacts;
- evidence;
- approvals;
- human checkpoints;
- retries;
- pause/resume;
- cancel;
- failure;
- compensation;
- logs;
- metrics;
- cost;
- audit;
- traceability.

Execution не отвечает за:

- редактирование Flow;
- редактирование Playbook;
- редактирование Skill;
- изменение Rules;
- изменение Controls;
- изменение Runtime Profile;
- изменение Knowledge Space.

---

# 3. Типы Execution

Поддержать:

```text
FLOW
PLAYBOOK
SKILL
SUBFLOW
REPLAY
SIMULATION
```

Основной production type:

```text
FLOW
```

---

# 4. Статусы Execution

```text
CREATED
QUEUED
STARTING
RUNNING
WAITING_FOR_EVENT
WAITING_FOR_HUMAN
PAUSED
CANCELLING
CANCELLED
COMPENSATING
COMPLETED
COMPLETED_WITH_WARNINGS
FAILED
TIMED_OUT
```

Допустимые переходы должны быть формализованы state machine.

Пример:

```text
CREATED
  → QUEUED
  → STARTING
  → RUNNING
      → WAITING_FOR_HUMAN
      → PAUSED
      → COMPLETED
      → FAILED
      → CANCELLING
          → CANCELLED
```

---

# 5. Execution Snapshot

До старта runtime создаётся immutable snapshot.

Snapshot должен включать:

```text
Flow Version
Playbook Versions
Skill Versions
Runtime Profiles
Knowledge Spaces
Rule Bundle
Controls
Capability Bindings
Input Artifact Versions
Routing Decision
User Context
```

Пример:

```json
{
  "executionId": "uuid",
  "flowVersionId": "uuid",
  "playbookVersionIds": ["uuid"],
  "skillVersionIds": ["uuid"],
  "runtimeProfileVersionIds": ["uuid"],
  "knowledgeSpaceSnapshots": [],
  "ruleBundle": {},
  "controlSet": {},
  "capabilityBindings": [],
  "source": {},
  "checksum": "sha256"
}
```

После запуска snapshot нельзя менять.

---

# 6. Основные сущности

```text
Execution
  ├── Execution Snapshot
  ├── Stage Runs
  │     └── Playbook Runs
  │           └── Step Runs
  │                 └── Skill Runs
  ├── Attempts
  ├── Artifacts
  ├── Evidence
  ├── Human Checkpoints
  ├── Events
  ├── Logs
  ├── Metrics
  ├── Costs
  └── Audit
```

---

# 7. Execution Catalog UI

Показывать:

- execution ID;
- source;
- flow/playbook;
- current stage;
- status;
- progress;
- started at;
- duration;
- owner;
- risk;
- cost;
- warnings;
- pending checkpoint.

Функции:

- поиск;
- фильтры;
- сортировка;
- open detail;
- pause;
- resume;
- cancel;
- retry;
- replay;
- export evidence;
- compare executions.

API:

```http
GET /api/v1/executions
POST /api/v1/executions
```

Фильтры:

```text
status
type
flowId
playbookId
sourceType
sourceReference
ownerId
startedFrom
startedTo
risk
hasWarnings
hasPendingCheckpoint
```

---

# 8. Execution Detail UI

Главная страница должна быть Execution Inspector.

Вкладки:

```text
Overview
Timeline
Graph
Artifacts
Evidence
Checkpoints
Runtime
Logs
Metrics
Snapshot
Audit
```

---

# 9. Overview

Показывает:

- status;
- source;
- selected Flow;
- current stage;
- progress;
- elapsed time;
- owner;
- started by;
- risk;
- cost;
- token usage;
- pending actions;
- blocking issue;
- latest artifact.

Обязательные quick actions:

```text
Pause
Resume
Cancel
Retry Failed Step
Open Human Checkpoint
Download Report
```

---

# 10. Timeline

Timeline — основное представление фактического исполнения.

События:

```text
Execution started
Flow routed
Stage started
Playbook started
Skill started
Capability called
Evidence collected
Artifact created
Control evaluated
Human checkpoint opened
Human decision received
Retry started
Stage completed
Execution completed
```

Каждая запись должна иметь:

- timestamp;
- type;
- actor;
- entity;
- status;
- duration;
- correlation IDs;
- details;
- links.

---

# 11. Graph View

Graph View отображает Flow/Playbook graph с runtime overlay.

Состояния узлов:

```text
NOT_STARTED
QUEUED
RUNNING
WAITING
COMPLETED
COMPLETED_WITH_WARNINGS
FAILED
SKIPPED
CANCELLED
```

Обязательные элементы:

- current node;
- selected path;
- skipped branches;
- failed transitions;
- retry count;
- elapsed time;
- artifacts created;
- checkpoint badge.

---

# 12. Stage Run

Stage Run содержит:

```text
stageKey
stageName
nodeType
status
startedAt
completedAt
duration
playbookRunId
inputMapping
outputMapping
attemptCount
selectedTransition
failure
```

---

# 13. Playbook Run

Playbook Run содержит:

```text
playbookVersionId
status
currentStep
stepRuns
artifacts
evidence
controlResults
humanCheckpoints
```

Один Flow Execution может содержать несколько Playbook Runs.

---

# 14. Step Run

Step Run — выполнение узла Playbook.

Типы:

```text
SKILL
HUMAN_CHECKPOINT
CONTROL_GATE
CONDITION
ADAPTIVE_ZONE
PUBLICATION
WAIT_EVENT
```

---

# 15. Skill Run

Skill Run содержит:

- skill version;
- interface;
- implementation;
- runtime profile;
- input;
- output;
- prompt metadata;
- Rule Bundle;
- Evidence Bundle;
- capability calls;
- model usage;
- cost;
- logs;
- attempts;
- error.

Сырой secret и скрытый provider credential запрещено отображать.

---

# 16. Attempts

Каждый retry создаёт новый Attempt.

```text
Attempt
- number
- status
- startedAt
- completedAt
- errorType
- retryReason
- runtimeProfileVersionId
- providerRequestId
```

Нельзя перезаписывать предыдущую попытку.

---

# 17. Human Checkpoints

Checkpoint показывает:

- title;
- question;
- requested action;
- due date;
- assignees;
- status;
- decision;
- comment;
- evidence;
- artifact diff;
- timeout policy;
- escalation.

Статусы:

```text
OPEN
ASSIGNED
IN_REVIEW
APPROVED
REJECTED
CHANGES_REQUESTED
EXPIRED
CANCELLED
```

---

# 18. Artifacts

Execution должен показывать:

- artifact type;
- name;
- version;
- producer;
- stage;
- created at;
- status;
- classification;
- lineage;
- checksum;
- publication target.

Функции:

- preview;
- compare versions;
- download;
- open lineage;
- approve;
- publish;
- mark superseded.

---

# 19. Evidence

Evidence Inspector показывает:

- source type;
- title;
- source reference;
- excerpt;
- relevance;
- freshness;
- classification;
- used by Skill;
- retrieved at;
- content hash.

Функции:

- filter by source;
- filter by Skill;
- trace evidence to artifact section;
- export;
- report stale evidence;
- report inaccessible source.

---

# 20. Runtime

Runtime tab показывает:

- effective Runtime Profile;
- provider;
- model;
- sandbox;
- network policy;
- capabilities;
- fallback;
- region;
- supervision;
- token usage;
- cost;
- provider request IDs.

---

# 21. Logs

Logs должны поддерживать:

```text
Execution logs
Runtime logs
Skill logs
Capability logs
Control logs
System logs
```

Функции:

- search;
- level filter;
- entity filter;
- correlation filter;
- live tail;
- download;
- sensitive-data masking.

Log levels:

```text
TRACE
DEBUG
INFO
WARN
ERROR
```

---

# 22. Metrics

Показывать:

```text
Duration
Queue time
Stage duration
Skill duration
Retries
Token usage
Cost
Capability calls
Evidence count
Artifact count
Human wait time
Provider latency
```

---

# 23. Pause / Resume

Pause должен быть cooperative.

Поведение:

1. принять pause request;
2. дождаться safe point;
3. остановить запуск новых nodes;
4. сохранить state;
5. перейти в PAUSED.

Нельзя прерывать transaction in progress без compensation policy.

Resume продолжает с frozen snapshot.

---

# 24. Cancel

Cancel policy:

```text
GRACEFUL
IMMEDIATE
COMPENSATE
```

GRACEFUL:

- не запускать новые stages;
- дождаться текущего safe point;
- завершить cleanup.

IMMEDIATE:

- запросить cancellation child workflows;
- cleanup sandbox;
- отметить незавершённые steps.

COMPENSATE:

- выполнить compensation path.

---

# 25. Retry

Поддержать:

```text
Retry Skill Attempt
Retry Step
Retry Stage
Retry Execution from Stage
Replay Entire Execution
```

Retry должен:

- сохранять историю;
- использовать тот же snapshot по умолчанию;
- не менять уже опубликованные artifacts;
- создавать новые artifact versions;
- быть разрешён RBAC и Controls.

---

# 26. Replay

Replay создаёт новый Execution.

Modes:

```text
SAME_SNAPSHOT
LATEST_ALLOWED_VERSIONS
CUSTOM_SNAPSHOT
```

Production default:

```text
SAME_SNAPSHOT
```

---

# 27. Failure model

Типы ошибок:

```text
VALIDATION_ERROR
CONTROL_VIOLATION
CAPABILITY_DENIED
PROVIDER_TIMEOUT
RATE_LIMIT
MODEL_UNAVAILABLE
SANDBOX_FAILED
HUMAN_REJECTED
EVENT_TIMEOUT
MAPPING_FAILED
PUBLICATION_FAILED
INTERNAL_ERROR
```

Ошибка содержит:

- type;
- code;
- message;
- retryable;
- source entity;
- attempt;
- stack trace reference;
- remediation hints.

---

# 28. Warnings

Warnings не всегда завершают Execution.

Примеры:

- stale evidence;
- partial Knowledge Space result;
- fallback model used;
- cost threshold exceeded;
- non-blocking Rule conflict;
- optional source unavailable.

---

# 29. Execution State Machine

State transitions должны быть централизованы.

Пример:

```text
RUNNING → WAITING_FOR_HUMAN
RUNNING → WAITING_FOR_EVENT
RUNNING → PAUSED
RUNNING → COMPLETED
RUNNING → FAILED
RUNNING → CANCELLING
WAITING_FOR_HUMAN → RUNNING
PAUSED → RUNNING
CANCELLING → CANCELLED
CANCELLING → COMPENSATING
COMPENSATING → CANCELLED
```

Недопустимые переходы возвращают:

```text
409 INVALID_EXECUTION_TRANSITION
```

---

# 30. Модель данных

## Execution

```text
Execution
- id UUID PK
- workspace_id UUID FK
- execution_number VARCHAR
- type VARCHAR
- status VARCHAR
- source_type VARCHAR NULL
- source_reference VARCHAR NULL
- source_payload_json JSONB
- flow_version_id UUID NULL
- playbook_version_id UUID NULL
- skill_version_id UUID NULL
- current_stage_key VARCHAR NULL
- progress_percent NUMERIC
- risk_level VARCHAR
- owner_id UUID NULL
- started_by UUID
- created_at TIMESTAMP
- queued_at TIMESTAMP NULL
- started_at TIMESTAMP NULL
- completed_at TIMESTAMP NULL
- cancelled_at TIMESTAMP NULL
- failure_code VARCHAR NULL
- failure_message TEXT NULL
- snapshot_id UUID NULL
- parent_execution_id UUID NULL
- root_execution_id UUID
```

## ExecutionSnapshot

```text
ExecutionSnapshot
- id UUID PK
- execution_id UUID FK
- snapshot_json JSONB
- checksum VARCHAR
- created_at TIMESTAMP
```

## StageRun

```text
StageRun
- id UUID PK
- execution_id UUID FK
- stage_key VARCHAR
- stage_name VARCHAR
- node_type VARCHAR
- status VARCHAR
- playbook_run_id UUID NULL
- attempt_count INTEGER
- input_json JSONB
- output_json JSONB
- selected_transition_json JSONB NULL
- started_at TIMESTAMP NULL
- completed_at TIMESTAMP NULL
- failure_json JSONB NULL
```

## PlaybookRun

```text
PlaybookRun
- id UUID PK
- execution_id UUID FK
- stage_run_id UUID NULL
- playbook_version_id UUID FK
- status VARCHAR
- current_step_key VARCHAR NULL
- started_at TIMESTAMP
- completed_at TIMESTAMP NULL
- output_artifact_id UUID NULL
```

## StepRun

```text
StepRun
- id UUID PK
- playbook_run_id UUID FK
- step_key VARCHAR
- step_name VARCHAR
- step_type VARCHAR
- status VARCHAR
- attempt_count INTEGER
- started_at TIMESTAMP NULL
- completed_at TIMESTAMP NULL
- input_json JSONB
- output_json JSONB
- failure_json JSONB NULL
```

## SkillRun

```text
SkillRun
- id UUID PK
- execution_id UUID FK
- step_run_id UUID FK
- skill_version_id UUID FK
- skill_interface_key VARCHAR
- implementation_id UUID NULL
- runtime_profile_version_id UUID FK
- status VARCHAR
- input_json JSONB
- output_json JSONB
- rule_bundle_json JSONB
- evidence_bundle_id UUID NULL
- usage_json JSONB
- cost_json JSONB
- started_at TIMESTAMP
- completed_at TIMESTAMP NULL
- failure_json JSONB NULL
```

## RunAttempt

```text
RunAttempt
- id UUID PK
- entity_type VARCHAR
- entity_id UUID
- attempt_number INTEGER
- status VARCHAR
- runtime_profile_version_id UUID NULL
- provider_request_id VARCHAR NULL
- started_at TIMESTAMP
- completed_at TIMESTAMP NULL
- failure_json JSONB NULL
```

## ExecutionEvent

```text
ExecutionEvent
- id UUID PK
- execution_id UUID FK
- sequence_number BIGINT
- event_type VARCHAR
- entity_type VARCHAR NULL
- entity_id UUID NULL
- actor_type VARCHAR
- actor_id VARCHAR NULL
- payload_json JSONB
- occurred_at TIMESTAMP
```

Constraint:

```text
UNIQUE(execution_id, sequence_number)
```

## ExecutionMetric

```text
ExecutionMetric
- id UUID PK
- execution_id UUID FK
- metric_name VARCHAR
- metric_value NUMERIC
- unit VARCHAR
- dimensions_json JSONB
- recorded_at TIMESTAMP
```

## ExecutionLog

```text
ExecutionLog
- id UUID PK
- execution_id UUID FK
- level VARCHAR
- source VARCHAR
- entity_type VARCHAR NULL
- entity_id UUID NULL
- correlation_id VARCHAR NULL
- message TEXT
- metadata_json JSONB
- occurred_at TIMESTAMP
```

---

# 31. REST API

## Executions

```http
GET  /api/v1/executions
POST /api/v1/executions
GET  /api/v1/executions/{executionId}
POST /api/v1/executions/{executionId}/pause
POST /api/v1/executions/{executionId}/resume
POST /api/v1/executions/{executionId}/cancel
POST /api/v1/executions/{executionId}/retry
POST /api/v1/executions/{executionId}/replay
```

## Runtime detail

```http
GET /api/v1/executions/{executionId}/timeline
GET /api/v1/executions/{executionId}/graph
GET /api/v1/executions/{executionId}/stages
GET /api/v1/executions/{executionId}/playbook-runs
GET /api/v1/executions/{executionId}/skill-runs
GET /api/v1/executions/{executionId}/attempts
```

## Outputs

```http
GET /api/v1/executions/{executionId}/artifacts
GET /api/v1/executions/{executionId}/evidence
GET /api/v1/executions/{executionId}/checkpoints
GET /api/v1/executions/{executionId}/metrics
GET /api/v1/executions/{executionId}/logs
GET /api/v1/executions/{executionId}/snapshot
GET /api/v1/executions/{executionId}/audit
```

## Reports

```http
GET /api/v1/executions/{executionId}/report
GET /api/v1/executions/{executionId}/evidence/export
GET /api/v1/executions/{executionId}/compare?otherExecutionId={id}
```

---

# 32. API examples

## Start Execution

```json
{
  "type": "FLOW",
  "flowVersionId": "uuid",
  "source": {
    "type": "JIRA",
    "reference": "PAY-123"
  },
  "input": {
    "title": "Payment cancellation",
    "description": "..."
  }
}
```

## Cancel

```json
{
  "mode": "GRACEFUL",
  "reason": "Work item cancelled"
}
```

## Retry step

```json
{
  "scope": "STEP",
  "entityId": "uuid",
  "reason": "Provider timeout"
}
```

---

# 33. Temporal Integration

Основной workflow:

```text
ExecutionWorkflow
  └── FlowRuntimeWorkflow
        └── PlaybookWorkflow
              └── SkillWorkflow
```

Signals:

```text
pause_requested
resume_requested
cancel_requested
human_decision_received
external_event_received
retry_requested
```

Queries:

```text
get_execution_state
get_current_stage
get_progress
get_pending_checkpoints
get_selected_path
get_cost
```

Activities:

```text
CreateExecutionActivity
CreateSnapshotActivity
UpdateExecutionStatusActivity
AppendExecutionEventActivity
CreateStageRunActivity
CreatePlaybookRunActivity
CreateStepRunActivity
CreateSkillRunActivity
PersistArtifactActivity
PersistEvidenceActivity
RecordMetricActivity
FinalizeExecutionActivity
```

---

# 34. Kafka Events

Topic:

```text
execution-events
```

Events:

```text
execution.created
execution.queued
execution.started
execution.paused
execution.resumed
execution.cancel_requested
execution.cancelled
execution.completed
execution.failed
execution.warning
execution.stage.started
execution.stage.completed
execution.playbook.started
execution.playbook.completed
execution.skill.started
execution.skill.completed
execution.retry.started
execution.checkpoint.opened
execution.checkpoint.resolved
execution.artifact.created
execution.evidence.created
```

---

# 35. WebSocket / SSE

Для live UI поддержать:

```text
GET /api/v1/executions/{executionId}/stream
```

События:

- status changes;
- timeline events;
- log lines;
- progress;
- checkpoints;
- metrics.

SSE предпочтительнее для одностороннего streaming.

---

# 36. RBAC

Permissions:

```text
execution.read
execution.start
execution.pause
execution.resume
execution.cancel
execution.retry
execution.replay
execution.logs.read
execution.snapshot.read
execution.evidence.read
execution.artifacts.read
execution.metrics.read
execution.audit.read
execution.report.export
```

Restricted evidence требует дополнительных permissions.

---

# 37. Audit Events

```text
execution.created
execution.started
execution.paused
execution.resumed
execution.cancelled
execution.retry.requested
execution.replay.created
execution.checkpoint.opened
execution.checkpoint.resolved
execution.artifact.downloaded
execution.evidence.exported
execution.snapshot.viewed
```

---

# 38. Backend architecture

```text
modules/executions/
├── domain/
│   ├── Execution
│   ├── ExecutionSnapshot
│   ├── StageRun
│   ├── PlaybookRun
│   ├── StepRun
│   ├── SkillRun
│   ├── Attempt
│   └── ExecutionEvent
├── application/
│   ├── StartExecution
│   ├── PauseExecution
│   ├── ResumeExecution
│   ├── CancelExecution
│   ├── RetryExecution
│   ├── ReplayExecution
│   ├── BuildExecutionReport
│   └── CompareExecutions
├── infrastructure/
│   ├── ExecutionRepository
│   ├── EventStore
│   ├── LogStore
│   ├── MetricStore
│   └── TemporalClient
├── api/
└── tests/
```

Services:

```text
ExecutionStateMachine
ExecutionSnapshotBuilder
ExecutionEventAppender
ExecutionTimelineBuilder
ExecutionGraphProjector
ExecutionReportBuilder
ExecutionRetryService
ExecutionReplayService
ExecutionAccessEvaluator
```

---

# 39. Frontend architecture

```text
pages/executions/
├── ExecutionsCatalogPage
├── ExecutionDetailPage
├── ExecutionTimelinePage
├── ExecutionGraphPage
└── ExecutionComparePage

features/executions/
├── start-execution
├── pause-execution
├── resume-execution
├── cancel-execution
├── retry-execution
├── replay-execution
└── export-report
```

Components:

```text
ExecutionStatusBadge
ExecutionProgress
ExecutionTimeline
RuntimeGraphOverlay
StageRunPanel
SkillRunInspector
AttemptHistory
ArtifactList
EvidenceInspector
CheckpointCard
LogViewer
MetricCards
SnapshotViewer
ExecutionActions
```

---

# 40. Нефункциональные требования

- catalog API p95 < 500 ms;
- execution detail p95 < 700 ms;
- timeline first page p95 < 500 ms;
- live event latency < 2 s;
- поддержка минимум 1 млн executions;
- минимум 10 000 concurrent executions;
- append-only event history;
- immutable snapshot;
- pagination для logs и timeline;
- masking secrets;
- trace correlation;
- retention policies;
- downloadable report;
- full audit.

---

# 41. Тестирование

## Unit

- state transitions;
- snapshot checksum;
- progress calculation;
- retry rules;
- cancellation;
- replay;
- timeline ordering;
- access filtering.

## Integration

- start execution;
- Temporal state sync;
- event append;
- pause/resume;
- cancel;
- retry;
- artifact persistence;
- evidence persistence;
- checkpoint;
- live stream.

## UI

- catalog;
- filters;
- timeline;
- graph overlay;
- logs;
- artifact preview;
- checkpoint actions;
- retry/cancel dialogs.

## E2E

```text
Create Work Request
→ Route Flow
→ Start Execution
→ Freeze Snapshot
→ Run Stage
→ Collect Evidence
→ Run Skill
→ Create Artifact
→ Open Human Checkpoint
→ Approve
→ Continue
→ Complete
→ Inspect Timeline
→ Download Report
```

---

# 42. Миграция текущего прототипа

1. Найти текущий раздел Executions.
2. Найти mock execution list.
3. Сохранить визуальный стиль.
4. Ввести Execution и ExecutionSnapshot.
5. Добавить routes:
   - `/executions`;
   - `/executions/:id`;
   - `/executions/:id/timeline`;
   - `/executions/:id/graph`;
   - `/executions/:id/compare`.
6. Подключить реальные API.
7. Добавить SSE.
8. Добавить Timeline.
9. Добавить Graph runtime overlay.
10. Интегрировать Temporal.

---

# 43. Последовательность Pull Requests

## PR-1

- catalog;
- detail shell;
- status badges;
- API types.

## PR-2

- DB schema;
- execution CRUD/read;
- snapshot.

## PR-3

- timeline;
- event store;
- SSE.

## PR-4

- stage/playbook/skill inspectors;
- attempts;
- logs.

## PR-5

- pause/resume/cancel/retry/replay;
- checkpoints.

## PR-6

- graph overlay;
- artifacts/evidence;
- reports;
- Audit/Kafka.

---

# 44. Vertical Slice

```text
Jira PAY-123
  ↓
Start Feature Delivery Execution
  ↓
Freeze Snapshot
  ↓
Business Requirements Stage
  ↓
System Requirements Stage
  ↓
Skill Run
  ↓
Evidence collected
  ↓
Artifact generated
  ↓
Human Checkpoint
  ↓
Approval
  ↓
Execution completed
  ↓
Timeline + report available
```

---

# 45. Definition of Done

Раздел завершён, если:

- Execution создаётся;
- snapshot immutable;
- runtime statuses синхронизируются;
- catalog работает;
- Timeline работает;
- Graph overlay работает;
- stage/playbook/skill runs отображаются;
- attempts сохраняются;
- pause/resume работают;
- cancel работает;
- retry работает;
- replay создаёт новый Execution;
- artifacts отображаются;
- evidence отображается;
- checkpoints работают;
- logs и metrics доступны;
- SSE обновляет UI;
- RBAC работает;
- Audit/Kafka работают;
- tests проходят;
- production mocks отсутствуют.

---

# 46. Первое задание coding-агенту

1. Просканируй репозиторий.
2. Найди текущий раздел Executions.
3. Создай `docs/executions/CURRENT_STATE.md`.
4. Сравни текущую реализацию с этим ТЗ.
5. Создай schema `executions` и `execution_snapshots`.
6. Реализуй read-only catalog API.
7. Подключи текущий UI к API.
8. Добавь Execution Detail shell.
9. Добавь status state machine tests.
10. Обнови `docs/IMPLEMENTATION_STATUS.md`.
11. Не реализуй retry/cancel до прохождения state transition tests.

---

# 47. Итоговая модель

```text
Execution
  ├── Immutable Snapshot
  ├── Runtime State
  ├── Timeline
  ├── Stage Runs
  ├── Playbook Runs
  ├── Step Runs
  ├── Skill Runs
  ├── Attempts
  ├── Artifacts
  ├── Evidence
  ├── Checkpoints
  ├── Logs
  ├── Metrics
  └── Audit
```

Конец документа.
