# Техническое задание для Cursor: корпоративная платформа AI Agent Platform

## 0. Назначение

Реализовать MVP корпоративной платформы AI-агентов поверх существующего стека:

- Qwen Code CLI — LLM/runtime;
- Temporal — durable orchestration;
- Kafka — события и интеграционный транспорт;
- MCP — доступ к Jira, Slack и другим системам.

Платформа не является таск-трекером. Задачи создаются во внешних системах. Пользователь заранее настраивает поведение агента в Control Plane. После назначения внешней работы агенту система:

1. получает событие;
2. выбирает playbook;
3. компилирует Execution Contract;
4. запускает Temporal workflow;
5. создаёт и обновляет Artifact State;
6. выполняет разрешённые операторы;
7. обращается к MCP только через Tool Gateway;
8. выполняет обязательные проверки и approvals;
9. публикует результат обратно во внешний источник.

---

# 1. Продуктовая модель

## 1.1 Control Plane

Сущности настройки:

- Artifact Blueprint;
- Operator;
- Playbook;
- Flow;
- Policy Pack;
- Execution Contract Template;
- MCP Integration;
- Capability Mapping;
- Model/Prompt Configuration;
- Role and Permission;
- Flow Fragment.

## 1.2 Runtime Plane

Сущности исполнения:

- External Work Item;
- Execution;
- Execution Contract;
- Artifact;
- Artifact Version;
- Evidence;
- Decision;
- Approval;
- Operator Run;
- Tool Call;
- Audit Event.

Пользователь не создаёт задачи внутри платформы. Runtime показывает исполнения внешних задач.

## 1.3 Ограничения LLM

LLM может предлагать действия, извлекать данные, анализировать и формировать артефакты.

LLM не может:

- отменять регуляторные правила;
- пропускать обязательные проверки;
- повышать собственные права;
- вызывать неизвестные или запрещённые MCP tools;
- менять Execution Contract;
- публиковать без разрешения;
- объявлять результат готовым вопреки формальным критериям.

---

# 2. Архитектура

```text
External Sources
  Jira / SberTrack / Slack / other
          |
          v
Ingress Adapters
          |
          v
Kafka: work-item.received
          |
          v
Execution Bootstrap Service
          |
          v
Execution Contract Compiler
          |
          v
Temporal CaseWorkflow
          |
          +--> Artifact Engine
          +--> Planner Activity --> Qwen Code CLI
          +--> Policy Engine
          +--> Operator Executor
          +--> Human Approval
          +--> Publisher
          |
          v
MCP Gateway
          |
          +--> Jira MCP
          +--> Slack MCP
          +--> other MCP servers

Storage:
- PostgreSQL
- Kafka
- Object Storage
- Audit Store
```

---

# 3. Технологический стек MVP

## Backend

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- Temporal Python SDK
- aiokafka
- PostgreSQL
- httpx
- structlog
- OpenTelemetry

## Frontend

- React 18+
- TypeScript
- Vite
- React Router
- TanStack Query
- React Flow
- Zustand
- Zod
- Tailwind CSS или корпоративная design system

## Infrastructure

- Docker Compose
- Kafka
- Temporal
- PostgreSQL
- MinIO или S3-compatible storage

---

# 4. Структура репозитория

```text
ai-agent-platform/
├── apps/
│   ├── api/
│   │   ├── main.py
│   │   ├── dependencies.py
│   │   ├── routers/
│   │   └── schemas/
│   ├── worker/
│   │   ├── main.py
│   │   ├── workflows/
│   │   └── activities/
│   ├── ingress/
│   │   ├── jira/
│   │   ├── slack/
│   │   └── kafka_consumer.py
│   └── web/
├── core/
│   ├── domain/
│   ├── application/
│   ├── policy/
│   ├── artifact/
│   ├── execution/
│   ├── operators/
│   ├── gateway/
│   ├── planner/
│   ├── publisher/
│   └── audit/
├── integrations/
│   ├── mcp/
│   ├── qwen/
│   ├── temporal/
│   ├── kafka/
│   └── storage/
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── e2e/
├── deploy/
│   ├── docker-compose.yml
│   └── helm/
├── scripts/
├── docs/
└── README.md
```

---

# 5. Доменная модель

## 5.1 ArtifactBlueprint

```python
class ArtifactBlueprint:
    id: UUID
    key: str
    name: str
    version: str
    status: Literal["draft", "active", "deprecated"]
    schema_json: dict
    facets: list[FacetDefinition]
    completion_rules: list[RuleDefinition]
    allowed_operator_keys: list[str]
    created_at: datetime
    updated_at: datetime
```

Пример facets для System Requirements:

- stakeholders;
- stakeholder_requirements;
- functional_requirements;
- constraints;
- adjacent_systems;
- data_model;
- integrations;
- security;
- non_functional_requirements;
- open_questions;
- traceability.

## 5.2 Artifact и ArtifactVersion

```python
class Artifact:
    id: UUID
    execution_id: UUID
    blueprint_key: str
    blueprint_version: str
    current_version: int
    status: Literal[
        "initializing",
        "in_progress",
        "blocked",
        "ready_for_review",
        "approved",
        "published",
    ]
```

```python
class ArtifactVersion:
    id: UUID
    artifact_id: UUID
    version: int
    state_json: dict
    created_by: str
    operator_run_id: UUID | None
    created_at: datetime
```

Artifact хранится версионно. Не обновлять state in-place.

Разрешённые статусы facet:

- unknown;
- partial;
- supported;
- confirmed;
- conflicting;
- stale;
- not_applicable.

## 5.3 Evidence

```python
class Evidence:
    id: UUID
    execution_id: UUID
    artifact_id: UUID | None
    source_type: str
    source_ref: str
    source_url: str | None
    trust_class: Literal["A", "B", "C", "D", "E"]
    content_json: dict
    content_hash: str
    retrieved_at: datetime
    valid_until: datetime | None
    tool_call_id: UUID | None
```

Классы доверия:

- A — нормативная или утверждённая системная запись;
- B — утверждённый корпоративный документ;
- C — код, API-контракт, конфигурация, телеметрия;
- D — неутверждённый рабочий документ;
- E — вывод модели или гипотеза.

LLM не может повышать trust_class.

## 5.4 Operator

```python
class OperatorDefinition:
    id: UUID
    key: str
    version: str
    name: str
    kind: Literal[
        "analysis",
        "evidence_acquisition",
        "transformation",
        "validation",
        "publication",
        "approval",
    ]
    input_schema: dict
    output_schema: dict
    readiness_rule: dict
    completion_rule: dict
    allowed_capabilities: list[str]
    risk_level: Literal["read", "low", "medium", "high", "critical"]
    side_effects: Literal["none", "draft", "write", "publish", "destructive"]
    prompt_template: str | None
    command_template: str | None
    enabled: bool
```

Оператор возвращает ArtifactPatch:

```python
class ArtifactPatch:
    base_artifact_version: int
    additions: dict
    replacements: dict
    unknowns: list[dict]
    conflicts: list[dict]
    signals: list[dict]
    evidence_ids: list[UUID]
    summary: str
```

Patch применяется только через Artifact Commit Service.

## 5.5 Playbook

Playbook — пользовательская декларация ожидаемого поведения, а не raw workflow.

```python
class Playbook:
    id: UUID
    key: str
    version: str
    name: str
    artifact_blueprint_key: str
    artifact_blueprint_version: str
    status: Literal["draft", "active", "deprecated"]
    required_outcomes: list[str]
    pinned_actions: list[dict]
    conditional_actions: list[dict]
    ordering_constraints: list[dict]
    approvals: list[dict]
    adaptive_zones: list[dict]
    publication_rules: dict
```

## 5.6 AdaptiveZone

```python
class AdaptiveZone:
    id: str
    name: str
    allowed_operator_kinds: list[str]
    allowed_operator_keys: list[str] | None
    allowed_capabilities: list[str]
    forbidden_capabilities: list[str]
    maximum_tool_calls: int
    maximum_operator_runs: int
    maximum_plan_revisions: int
    maximum_llm_tokens: int | None
    side_effect_limit: Literal["none", "draft", "write"]
    require_confirmation_for_new_operator: bool
```

## 5.7 PolicyPack

```python
class PolicyPack:
    id: UUID
    key: str
    version: str
    authority: Literal["regulatory", "corporate", "domain", "team"]
    enforcement: Literal["hard", "controlled", "customizable"]
    status: Literal["draft", "active", "deprecated"]
    applicability_rule: dict
    rules: list[dict]
```

Для MVP использовать JSON DSL и интерфейс PolicyEvaluator.

Поддержать операции:

- eq;
- neq;
- in;
- contains;
- exists;
- all;
- any;
- not;
- gt/gte/lt/lte.

## 5.8 ExecutionContract

```python
class ExecutionContract:
    id: UUID
    execution_id: UUID
    version: int
    status: Literal["compiled", "active", "superseded", "invalid"]
    contract_json: dict
    contract_hash: str
    source_versions_json: dict
    compiled_at: datetime
```

Контракт включает:

- task metadata;
- playbook и version;
- blueprint и version;
- применённые policies;
- mandatory outcomes;
- mandatory operators;
- allowed/forbidden operators;
- adaptive zones;
- required approvals;
- capability permissions;
- budgets;
- stop conditions;
- publication permissions.

После запуска контракт immutable. Изменение создаёт новую версию.

## 5.9 Execution

```python
class Execution:
    id: UUID
    external_source: str
    external_work_item_id: str
    external_work_item_url: str | None
    source_payload_json: dict
    playbook_key: str
    playbook_version: str
    status: Literal[
        "received",
        "compiling",
        "running",
        "waiting_approval",
        "blocked",
        "failed",
        "completed",
        "cancelled",
    ]
    temporal_workflow_id: str | None
    current_operator_key: str | None
    created_at: datetime
    updated_at: datetime
```

---

# 6. Ingress и назначение работы

Canonical event:

```json
{
  "event_type": "work-item.received",
  "event_id": "uuid",
  "occurred_at": "ISO-8601",
  "source": "jira",
  "external_id": "PAY-123",
  "external_url": "...",
  "assignment": {"agent_key": "requirements-agent"},
  "project": {"key": "PAY"},
  "author": {},
  "title": "...",
  "description": "...",
  "labels": [],
  "raw_payload": {}
}
```

Интерфейс:

```python
class WorkItemIngressAdapter(Protocol):
    async def parse_event(self, raw_event: dict) -> CanonicalWorkItemEvent:
        ...
```

Порядок выбора playbook:

1. явный playbook в metadata;
2. assignment rule;
3. mapping по agent_key;
4. правило по source/project/labels;
5. default playbook;
6. иначе blocked: playbook_not_resolved.

---

# 7. Execution Contract Compiler

```python
class ExecutionContractCompiler:
    async def compile(
        self,
        work_item: CanonicalWorkItem,
        playbook: Playbook,
    ) -> ExecutionContract:
        ...
```

Алгоритм:

1. загрузить blueprint;
2. найти active policies;
3. вычислить applicable policies;
4. отсортировать по authority/enforcement;
5. объединить mandatory outcomes;
6. объединить mandatory operators;
7. применить playbook;
8. запретить ослабление hard/controlled rules;
9. проверить operator versions;
10. проверить capabilities и approvals;
11. выявить conflicts;
12. сформировать contract;
13. посчитать SHA-256 hash;
14. сохранить contract и audit decision.

При конфликте hard policy workflow не запускается.

---

# 8. Temporal

## 8.1 CaseWorkflow

```python
@workflow.defn
class CaseWorkflow:
    @workflow.run
    async def run(self, execution_id: str) -> dict:
        ...
```

Состояния:

```text
RECEIVED
COMPILED
INITIALIZED
PLANNING
EXECUTING
WAITING_APPROVAL
VALIDATING
READY_TO_PUBLISH
PUBLISHING
COMPLETED
BLOCKED
FAILED
CANCELLED
```

## 8.2 Workflow loop

```python
while True:
    execution = await load_execution()
    contract = await load_active_contract()
    artifact = await load_artifact()

    evaluation = await evaluate_artifact(contract, artifact)

    if evaluation.blocking_conflict:
        await set_blocked(...)
        await wait_for_human_action()
        continue

    if evaluation.required_approval:
        await request_approval(...)
        await wait_for_approval()
        continue

    if evaluation.ready_for_publication:
        await run_publication_gate()
        await publish()
        return completed_result

    proposals = await plan_next_operators(...)
    authorized = await authorize_operator_proposals(proposals)

    if not authorized:
        await set_blocked("no_authorized_progress")
        await wait_for_human_action()
        continue

    for proposal in authorized:
        result = await execute_operator(proposal)
        await commit_artifact_patch(result.patch)
        await publish_execution_event(...)
```

## 8.3 Activities

- load_execution_activity;
- load_contract_activity;
- initialize_artifact_activity;
- evaluate_artifact_activity;
- plan_operators_activity;
- authorize_operator_activity;
- execute_operator_activity;
- commit_artifact_patch_activity;
- request_approval_activity;
- validate_completion_activity;
- render_artifact_activity;
- publish_result_activity;
- emit_kafka_event_activity;
- update_external_status_activity.

## 8.4 Signals

- pause;
- resume;
- cancel;
- approve;
- reject;
- answer_question;
- add_constraint;
- increase_budget;
- reduce_scope;
- request_replan;
- replace_contract.

## 8.5 Queries

- get_status;
- get_current_plan;
- get_pending_approvals;
- get_artifact_summary;
- get_budget_usage;
- get_execution_contract_version.

## 8.6 Temporal rules

- Workflow code deterministic.
- DB, Kafka, MCP, Qwen, clock, random и HTTP — только Activities.
- Activities idempotent.
- External writes используют idempotency key.
- Continue-As-New для длинных executions.
- Policy deny и invalid patch не retry автоматически.

---

# 9. Planner и Qwen Code CLI

## 9.1 PlannerClient

```python
class PlannerClient(Protocol):
    async def propose_operators(
        self,
        request: PlannerRequest,
    ) -> PlannerResponse:
        ...
```

Planner получает только:

- краткое описание work item;
- Execution Contract;
- Artifact Summary;
- unmet outcomes;
- unresolved conflicts;
- разрешённый каталог operators;
- budget state;
- последние operator runs;
- no-progress history.

Не передавать полный каталог платформы.

## 9.2 Planner output

Строгий JSON:

```json
{
  "proposals": [
    {
      "operator_key": "collect_api_contracts",
      "operator_version": "1.1",
      "targets": ["adjacent_systems", "integrations"],
      "reason": "API version is unknown",
      "expected_delta": {
        "facet": "integrations",
        "from": "unknown",
        "to": "partial"
      },
      "input": {"system": "antifraud"}
    }
  ]
}
```

## 9.3 Qwen adapter

```python
class QwenCodeClient:
    async def run_json(
        self,
        prompt: str,
        output_schema: dict,
        workspace: Path | None = None,
        timeout_seconds: int = 300,
    ) -> dict:
        ...
```

Требования:

- subprocess без shell=True;
- timeout;
- отдельная рабочая директория;
- очищенный environment;
- без секретов;
- stdout/stderr в audit store;
- только JSON output;
- ограничение output size;
- Qwen не имеет прямого доступа к MCP.

---

# 10. Operator Executor

Алгоритм:

1. загрузить operator definition;
2. проверить version;
3. проверить DoR;
4. проверить Execution Contract;
5. проверить Policy Engine;
6. собрать минимальный context package;
7. вызвать Qwen или deterministic handler;
8. валидировать output schema;
9. проверить evidence ids;
10. сформировать ArtifactPatch;
11. сохранить OperatorRun;
12. вернуть patch в workflow.

No-progress fingerprint:

```text
SHA256(
  operator_key
  + operator_version
  + normalized_input
  + artifact_base_version
  + relevant_evidence_hashes
)
```

Повтор одинакового fingerprint запрещён.

No-progress, если оператор не:

- добавил evidence;
- изменил facet;
- создал новый вопрос;
- разрешил конфликт;
- выдал новый проверяемый signal.

После двух no-progress — blocked + human decision.

---

# 11. MCP Gateway

Gateway — детерминированный сервис, не AI-агент.

Обязанности:

- discovery MCP tools;
- registry;
- fingerprint;
- capability mapping;
- policy enforcement;
- normalization;
- access control;
- budgets;
- idempotency;
- audit;
- health checks;
- quarantine.

## 11.1 Registry

```python
class MCPServer:
    id: UUID
    key: str
    name: str
    transport: str
    endpoint: str
    status: str
    auth_config_ref: str
```

```python
class MCPTool:
    id: UUID
    server_id: UUID
    name: str
    description: str
    input_schema_json: dict
    output_schema_json: dict | None
    fingerprint: str
    status: Literal[
        "discovered", "pending", "approved", "quarantined", "disabled"
    ]
    risk_level: str
```

Fingerprint:

```text
SHA256(server_key + tool_name + canonical_input_schema + description)
```

Изменение fingerprint переводит tool в pending.

## 11.2 Capabilities

Примеры:

- tracker.read;
- tracker.search;
- tracker.comment;
- chat.read_thread;
- chat.post_message;
- docs.search;
- docs.read;
- repo.search;
- repo.read_file;
- architecture.search;
- api_contract.read;
- publisher.publish.

## 11.3 Gateway request

```json
{
  "capability": "tracker.read",
  "arguments": {"id": "PAY-123"},
  "execution_context": {
    "execution_id": "...",
    "execution_contract_id": "...",
    "operator_run_id": "...",
    "operator_key": "analyze_external_work_item",
    "project": "PAY",
    "external_source": "jira",
    "adaptive_zone": "initial_context"
  }
}
```

## 11.4 Resolver

Фильтрация:

1. approved;
2. health=online;
3. selector matches context;
4. allowed contract;
5. allowed operator;
6. allowed policy;
7. within budget;
8. lowest risk;
9. highest priority;
10. deterministic tie-break.

## 11.5 Adapters

```python
class CapabilityAdapter(Protocol):
    def to_mcp_args(self, canonical_args: dict, context: dict) -> dict:
        ...

    def from_mcp_result(self, raw_result: dict) -> dict:
        ...
```

MVP adapters:

- Jira read issue;
- Jira comment issue;
- Slack read thread;
- Slack post thread reply.

## 11.6 Security

- Не передавать raw MCP tools в LLM.
- Новые tools — quarantine.
- Write/publish tools проходят отдельную проверку.
- MCP content считается недоверенным.
- Инструкции внутри документов не меняют policy или permissions.
- Каждый tool call аудируется.
- Секреты и PII маскируются.

---

# 12. Kafka

Topics:

```text
work-item.received
execution.created
execution.status-changed
execution.operator-started
execution.operator-completed
execution.operator-failed
execution.approval-requested
execution.approval-resolved
artifact.version-created
artifact.conflict-detected
tool.call-started
tool.call-completed
tool.call-failed
audit.decision
publication.completed
dead-letter
```

Event envelope:

```json
{
  "event_id": "uuid",
  "event_type": "artifact.version-created",
  "schema_version": "1",
  "occurred_at": "ISO-8601",
  "producer": "artifact-service",
  "correlation_id": "execution-id",
  "causation_id": "operator-run-id",
  "payload": {}
}
```

Требования:

- idempotent consumers;
- event_id deduplication;
- Outbox Pattern;
- retries;
- dead-letter;
- schema versioning;
- Kafka не является единственным хранилищем business state.

---

# 13. Approval

```python
class Approval:
    id: UUID
    execution_id: UUID
    type: str
    requested_role: str | None
    requested_user_id: str | None
    status: Literal["pending", "approved", "rejected", "expired", "cancelled"]
    subject_json: dict
    decision_comment: str | None
    requested_at: datetime
    resolved_at: datetime | None
```

Процесс:

1. сохранить Approval;
2. отправить Kafka event;
3. уведомить Slack/Jira;
4. Temporal ждёт Signal;
5. API resolve approval отправляет Signal;
6. сохранить immutable decision record.

---

# 14. Publication

```python
class Publisher(Protocol):
    async def publish(
        self,
        execution: Execution,
        rendered_artifact: RenderedArtifact,
        contract: ExecutionContract,
    ) -> PublicationResult:
        ...
```

MVP:

- Jira: комментарий с summary и ссылкой на Artifact;
- Slack: ответ в thread;
- status внешней задачи не менять без отдельного разрешения;
- publication idempotent;
- formats: Markdown, JSON, HTML preview.

---

# 15. API

Base path: `/api/v1`

## Control Plane

```text
GET/POST /blueprints
GET/PUT /blueprints/{id}
POST /blueprints/{id}/activate

GET/POST /operators
GET/PUT /operators/{id}
POST /operators/{id}/validate
POST /operators/{id}/activate

GET/POST /playbooks
GET/PUT /playbooks/{id}
POST /playbooks/{id}/validate
POST /playbooks/{id}/activate
POST /playbooks/{id}/simulate

GET/POST /policies
GET/PUT /policies/{id}
POST /policies/{id}/validate
POST /policies/{id}/activate

GET/POST /mcp/servers
POST /mcp/servers/{id}/discover
GET /mcp/tools
POST /mcp/tools/{id}/approve
POST /mcp/tools/{id}/quarantine

GET/POST /capabilities
POST /capabilities/{key}/implementations
```

## Runtime

```text
GET /executions
GET /executions/{id}
POST /executions/{id}/pause
POST /executions/{id}/resume
POST /executions/{id}/cancel
POST /executions/{id}/replan
GET /executions/{id}/contract
GET /executions/{id}/artifact
GET /executions/{id}/events
GET /executions/{id}/operator-runs
GET /executions/{id}/tool-calls

GET /approvals
POST /approvals/{id}/approve
POST /approvals/{id}/reject

POST /ingress/jira
POST /ingress/slack
```

---

# 16. UI

## 16.1 Navigation

```text
Control Plane
- Обзор
- Playbooks
- Flow Studio
- Операторы
- Артефакты (Blueprints)
- Политики
- Execution Contracts
- MCP Реестр
- Интеграции
- Модели и промпты
- Пользователи и роли
- Аудит

Runtime Plane
- Executions
- Активность
- Очередь работ
- События
```

## 16.2 Dashboard

- быстрые действия;
- схема Execution Design;
- таблица playbooks;
- operator registry;
- MCP integrations;
- contract templates;
- recent executions;
- system health;
- resource usage.

## 16.3 Flow Studio

Использовать React Flow.

Node types:

- Start;
- Required Action;
- Required Outcome;
- Conditional;
- Adaptive Zone;
- Approval;
- Fixed Sequence Group;
- Publish;
- End.

Properties panel:

- name;
- operator;
- condition;
- allowed capabilities;
- side effects;
- budgets;
- approvals;
- retry;
- timeout;
- mandatory/optional;
- source: user/corporate/regulatory.

Regulatory nodes:

- нельзя удалять;
- lock icon;
- показывать policy source;
- разрешён только просмотр details.

Действия:

- Validate;
- Simulate;
- Save Draft;
- Publish Version;
- Compare Versions.

## 16.4 Execution page

Это не страница задачи.

Header:

- execution id;
- external source;
- external work item id + link;
- playbook;
- status;
- contract version;
- started time.

Tabs:

- Overview;
- Artifact;
- Plan;
- Operator Runs;
- Evidence;
- Approvals;
- Contract;
- Audit.

Показывать:

- текущий operator;
- fixed/adaptive/regulatory actions;
- artifact facet statuses;
- conflicts;
- open questions;
- next proposed action;
- reason;
- budget usage;
- все external writes.

---

# 17. RBAC

Роли MVP:

- PlatformAdmin;
- ProcessDesigner;
- PolicyAuthor;
- ComplianceApprover;
- OperatorAuthor;
- IntegrationAdmin;
- ExecutionViewer;
- ExecutionController;
- Approver.

Permissions:

```text
playbook.read
playbook.write
playbook.publish
policy.read
policy.write
policy.activate
operator.write
operator.activate
mcp.approve_tool
execution.pause
execution.cancel
approval.resolve
audit.read
```

Для regulatory policy — four-eyes activation.

---

# 18. Audit

Логировать:

- изменения Control Plane;
- version diffs;
- contract compilation;
- policy decisions;
- planner proposals;
- authorization decisions;
- operator input/output hashes;
- tool calls;
- approvals;
- artifact versions;
- publication;
- errors;
- manual interventions.

Audit append-only.

---

# 19. Безопасность

Обязательно:

- fail closed для policy engine;
- secret references вместо секретов в DB;
- encryption at rest для sensitive evidence;
- masking logs;
- execution-level authorization;
- input size limits;
- JSON schema validation;
- subprocess sandbox для Qwen;
- tool allowlist;
- egress restrictions;
- prompt injection defense;
- immutable contract hash;
- CSP/CSRF/rate limiting;
- malware scanning interface для вложений.

---

# 20. Наблюдаемость

Metrics:

- executions_total;
- executions_active;
- execution_duration;
- execution_failures;
- operator_duration;
- operator_no_progress;
- llm_tokens;
- llm_failures;
- mcp_tool_calls;
- mcp_tool_failures;
- approvals_waiting;
- policy_denies;
- artifact_versions;
- kafka_consumer_lag;
- temporal_activity_failures.

Correlation IDs:

```text
execution_id
temporal_workflow_id
operator_run_id
tool_call_id
event_id
```

---

# 21. Тестирование

## Unit

- policy DSL evaluator;
- contract merge;
- hard policy conflict;
- resolver;
- adapters;
- ArtifactPatch validation;
- no-progress detector;
- playbook selector;
- capability permissions.

## Contract

- Jira MCP adapter;
- Slack MCP adapter;
- Qwen JSON output;
- Kafka event schemas;
- API schemas.

## Temporal

Проверить:

- happy path;
- activity retry;
- signal approval;
- pause/resume;
- contract replacement;
- no authorized proposal;
- no-progress block;
- Continue-As-New;
- publication idempotency.

## E2E vertical slice

```text
Jira canonical event
  -> Execution
  -> Contract Compiler
  -> Temporal CaseWorkflow
  -> analyze_external_work_item
  -> Jira MCP read
  -> ArtifactVersion
  -> approval
  -> Jira comment publication
```

---

# 22. Этапы реализации

## Phase 1 — Foundation

- repository structure;
- FastAPI;
- PostgreSQL models;
- Alembic;
- Kafka envelope;
- Temporal worker;
- health checks;
- audit base.

## Phase 2 — Control Plane Core

- Blueprint CRUD/versioning;
- Operator CRUD/versioning;
- Playbook CRUD/versioning;
- Policy CRUD/versioning;
- JSON rule evaluator;
- Contract Compiler;
- contract preview.

## Phase 3 — Ingress and Execution

- Jira/Slack canonical ingress;
- assignment rules;
- Execution creation;
- CaseWorkflow;
- runtime API;
- Kafka execution events.

## Phase 4 — Artifact Engine

- Artifact/ArtifactVersion;
- Evidence;
- ArtifactPatch;
- Commit Service;
- completion evaluation;
- conflict/unknown tracking.

## Phase 5 — Qwen and Operators

- Qwen adapter;
- planner prompt;
- operator executor;
- JSON validation;
- no-progress protection;
- token/tool budgets.

## Phase 6 — MCP Gateway

- server registry;
- discovery;
- fingerprint;
- quarantine;
- capabilities;
- Jira adapter;
- Slack adapter;
- policy checks;
- audit.

## Phase 7 — Approval and Publication

- Approval API;
- Temporal signals;
- notifications;
- Markdown rendering;
- Jira/Slack publisher;
- idempotency.

## Phase 8 — UI

- dashboard;
- playbook editor;
- Flow Studio;
- operator registry;
- policies;
- MCP registry;
- executions;
- approvals;
- audit.

---

# 23. MVP scope

Обязательно:

- System Requirements Blueprint;
- 8–12 operators;
- Jira и Slack ingress;
- Jira и Slack MCP adapters;
- один adaptive zone;
- hard/corporate/customizable policy levels;
- contract compilation;
- Temporal execution;
- Artifact State;
- approval;
- publication;
- audit;
- базовый Flow Studio.

Не включать:

- BPMN engine;
- arbitrary code nodes;
- raw MCP calls от пользователя;
- автоматическое создание operators LLM;
- multi-agent swarm;
- абсолютную автономность;
- marketplace operators.

---

# 24. Начальный каталог операторов

```text
analyze_external_work_item
identify_stakeholders
extract_requirements
identify_constraints
identify_adjacent_systems
collect_api_contracts
analyze_data_impact
collect_security_context
validate_requirements
render_system_requirements
request_human_approval
publish_result
```

Каждый operator:

- Pydantic input/output;
- fixture;
- unit tests;
- example prompt;
- allowed capabilities;
- risk;
- DoR;
- DoD.

---

# 25. Seed data

Создать:

- System Requirements Blueprint v1;
- System Requirements Standard Playbook v1;
- System Requirements with Architecture Review v1;
- Corporate Security Policy v1;
- Default Execution Contract Template;
- Jira MCP server stub;
- Slack MCP server stub;
- базовые capabilities;
- каталог операторов;
- admin user.

---

# 26. Инструкции Cursor

Реализовывать итеративно.

Для каждого этапа:

1. прочитать этот документ;
2. создать ADR для существенных решений;
3. сначала создать protocols/interfaces;
4. затем persistence;
5. затем application services;
6. затем API;
7. затем tests;
8. затем UI;
9. обновить README.

Не создавать mock-only архитектуру без рабочего vertical slice.

После этапа запускать:

```bash
ruff check .
mypy .
pytest
```

Frontend:

```bash
npm run lint
npm run typecheck
npm run test
npm run build
```

---

# 27. Definition of Done MVP

MVP готов, если:

- задача назначается агенту в Jira или Slack;
- событие попадает в платформу;
- автоматически выбирается playbook;
- создаётся immutable Execution Contract;
- hard policies нельзя обойти;
- Temporal workflow переживает рестарт worker;
- Qwen получает только разрешённый контекст;
- Qwen не имеет прямого доступа к MCP;
- MCP Gateway вызывает только approved tools;
- Artifact State обновляется версионно;
- evidence трассируется до источника;
- adaptive action объясняется пользователю;
- approval останавливает и продолжает workflow;
- результат публикуется обратно;
- повторная publication не создаёт дубль;
- все решения доступны в Audit;
- UI разделяет Control Plane и Runtime Plane;
- пользователь может собрать flow, но не удалить regulatory gate.
