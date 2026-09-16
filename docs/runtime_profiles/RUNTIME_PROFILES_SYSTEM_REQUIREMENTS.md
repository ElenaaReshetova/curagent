# RUNTIME_PROFILES_SYSTEM_REQUIREMENTS.md
## Governed AI Delivery Platform
### Полное системное ТЗ на раздел Runtime Profiles

# 1. Назначение

Runtime Profile — версионируемая управляемая конфигурация технической среды исполнения Skills и Playbooks.

Он отвечает на вопрос: **какой provider, model, sandbox, набор capabilities, лимиты, supervision и fallback использовать при запуске**.

```text
Playbook / Skill
  ↓
Runtime Profile Resolver
  ↓
Provider + Model + Sandbox + Policies
  ↓
Skill Runtime
```

Runtime Profile не содержит бизнес-логику, инструкции Skill, граф Playbook или routing Flow.

# 2. Пример

```yaml
key: qwen-production
provider: QWEN_CODE_CLI
model: qwen3-coder
sandbox: CONTAINER
network: CAPABILITY_GATEWAY_ONLY
supervision: SUPERVISED
limits:
  max_execution_seconds: 1200
  max_output_tokens: 16000
capabilities:
  allow:
    - repository.read
    - repository.search
    - context.search
  approval_required:
    - artifact.publish
secret_ref: vault://ai/qwen-production
```

# 3. Ответственность

Runtime Profile определяет:

- provider и runtime adapter;
- model и model parameters;
- token, time, cost и concurrency limits;
- retry и fallback;
- sandbox и filesystem policy;
- network policy;
- capability allowlist и denylist;
- approvals для рискованных capabilities;
- secret references;
- data residency и retention;
- supervision mode;
- observability и audit policy.

Не определяет:

- порядок этапов;
- Skill instructions;
- Rules;
- Knowledge Sources;
- Controls;
- структуру Artifact.

# 4. Типы профилей

```text
DEVELOPMENT
TEST
PRODUCTION
RESTRICTED
BATCH
INTERACTIVE
HIGH_ACCURACY
LOW_COST
CUSTOM
```

# 5. Lifecycle

```text
DRAFT → VALIDATING → READY → ACTIVE → DEPRECATED → DISABLED → ARCHIVED
```

Требования:

- ACTIVE version immutable;
- изменение создаёт новую version;
- Execution использует frozen snapshot;
- DISABLED и DEPRECATED не выбираются для новых Execution;
- secrets не сохраняются в JSON конфигурации;
- rollback создаёт новую version.

# 6. Provider Registry

Поддержать adapters:

```text
OPENAI_API
AZURE_OPENAI
ANTHROPIC_API
GOOGLE_VERTEX_AI
QWEN_CODE_CLI
LOCAL_OLLAMA
LOCAL_VLLM
CUSTOM_HTTP
CUSTOM_CLI
```

Provider Registry хранит:

- provider type;
- adapter version;
- поддерживаемые модели;
- допустимые параметры;
- регионы;
- health endpoint;
- pricing metadata;
- supported runtime features.

# 7. Model Configuration

```json
{
  "modelId": "qwen3-coder",
  "temperature": 0.2,
  "topP": 0.9,
  "maxInputTokens": 120000,
  "maxOutputTokens": 16000,
  "reasoningMode": "STANDARD",
  "streaming": true
}
```

UI обязан строить provider-specific форму и не показывать неподдерживаемые параметры.

# 8. Runtime Limits

```text
maxInputTokens
maxOutputTokens
maxExecutionSeconds
maxToolCalls
maxCapabilityCalls
maxArtifacts
maxEvidenceItems
maxFilesystemSizeMb
maxNetworkRequests
maxRetries
maxConcurrentRuns
```

Лимиты проверяются до старта и во время Execution.

# 9. Sandbox Policy

Поддержать:

```text
NONE
PROCESS
CONTAINER
MICROVM
REMOTE_RUNNER
```

Production требует минимум `CONTAINER`.

```json
{
  "type": "CONTAINER",
  "image": "registry/runtime/qwen:1.4.0",
  "readOnlyRootFilesystem": true,
  "ephemeral": true,
  "cpuLimit": "4",
  "memoryLimitMb": 8192,
  "filesystemSizeMb": 1024,
  "allowedMounts": ["artifact-workspace", "repository-snapshot"]
}
```

# 10. Filesystem Policy

```text
READ_ONLY
WORKSPACE_WRITE
TEMP_WRITE
FULL_SANDBOX_WRITE
```

Разрешённые зоны:

```text
/input
/workspace
/output
/tmp
```

Запрещены host mounts, shared writable volumes и доступ к secret directories.

# 11. Network Policy

```text
DENY_ALL
ALLOW_CAPABILITY_GATEWAY_ONLY
ALLOWLIST
UNRESTRICTED
```

Production default: `ALLOW_CAPABILITY_GATEWAY_ONLY`.

# 12. Capability Policy

Итоговые capabilities:

```text
Skill Request
∩ Runtime Profile Allowlist
∩ User Permissions
∩ Controls
= Effective Capabilities
```

```json
{
  "allowedCapabilities": ["repository.read", "context.search"],
  "deniedCapabilities": ["deployment.execute"],
  "requireApprovalFor": ["artifact.publish", "work_item.update"]
}
```

Deny всегда имеет приоритет.

# 13. Secret References

Хранятся только ссылки:

```text
vault://ai/openai-prod
aws-secrets://runtime/qwen
k8s-secret://runtime/provider-key
```

Skill, prompt, logs и snapshot не должны видеть secret value.

# 14. Cost Policy

```json
{
  "currency": "USD",
  "maxCostPerRun": 3.0,
  "maxDailyCost": 500.0,
  "warningThresholdPercent": 80,
  "onLimitExceeded": "FAIL"
}
```

Поведение: `WARN`, `FAIL`, `FALLBACK`, `ASK_HUMAN`.

# 15. Retry Policy

```json
{
  "maximumAttempts": 3,
  "initialIntervalSeconds": 5,
  "backoffCoefficient": 2,
  "maximumIntervalSeconds": 120,
  "retryableErrors": ["RATE_LIMIT", "PROVIDER_TIMEOUT"],
  "nonRetryableErrors": ["CONTROL_VIOLATION", "AUTHENTICATION_FAILED"]
}
```

# 16. Fallback Policy

```text
Primary Profile → Secondary Profile → Human Checkpoint
```

Требования:

- fallback target должен быть ACTIVE;
- запрещены циклы;
- максимальная глубина задаётся явно;
- fallback фиксируется в Audit и Execution Inspector.

# 17. Data Residency

```json
{
  "allowedRegions": ["EU"],
  "dataProcessingLocation": "EU",
  "retentionMode": "ZERO_RETENTION",
  "trainingAllowed": false
}
```

Controls могут только ужесточать эти параметры.

# 18. Supervision Mode

```text
AUTONOMOUS — разрешённые действия выполняются автоматически
SUPERVISED — рискованные write actions требуют approval
STRICT — каждый write требует approval
MANUAL — runtime только предлагает действия
```

# 19. Observability

```json
{
  "logLevel": "INFO",
  "capturePromptMetadata": true,
  "capturePromptContent": false,
  "captureModelOutput": true,
  "captureCapabilityCalls": true,
  "captureTokenUsage": true,
  "captureCost": true,
  "traceSampling": 1.0
}
```

Restricted profiles могут запрещать сохранение prompt и output content.

# 20. UI: Runtime Profiles Catalog

Поля:

- name, key, type;
- provider и model;
- active version;
- status и health;
- sandbox;
- supervision;
- usage count;
- owner;
- updated at.

Функции:

- поиск и фильтры;
- create, duplicate, disable, archive;
- validate;
- test connection;
- compare versions;
- open usage и executions.

# 21. UI: Profile Detail

Вкладки:

```text
Overview
Provider
Model
Limits
Security
Capabilities
Fallback
Usage
Versions
Validation
Audit
```

# 22. UI: Fullscreen Editor

Секции:

```text
General
Provider
Model
Limits
Sandbox
Filesystem
Network
Capabilities
Secrets
Cost
Retry
Fallback
Residency
Observability
```

Функции:

- autosave draft;
- provider-specific forms;
- effective JSON preview;
- validation;
- test connection;
- dry run;
- compare;
- activate.

# 23. Effective Runtime Preview

Контекст:

```text
Workspace
Flow
Stage
Playbook
Skill
User
Risk classification
Controls
```

Результат:

- selected profile version;
- inheritance trace;
- overrides;
- denied overrides;
- effective model, limits and capabilities;
- approvals;
- fallback chain;
- policy conflicts.

# 24. Resolution Priority

```text
Platform Default
→ Workspace Default
→ Flow Version
→ Flow Stage Override
→ Playbook Version
→ Skill Binding
→ Execution Override
→ Controls
```

Execution override разрешён только для allowlisted полей. Controls имеют финальный приоритет.

# 25. Validation

## Structural

- обязательные поля;
- положительные limits;
- корректный secret URI;
- отсутствие fallback cycles;
- валидный sandbox.

## Provider

- adapter зарегистрирован;
- model существует;
- region доступен;
- parameters поддерживаются;
- secret resolvable;
- provider health успешен.

## Security

- production не использует NONE;
- production network не UNRESTRICTED;
- нет raw secrets;
- mounts разрешены;
- residency соблюдается.

## Compatibility

- Skill requirements совместимы;
- capabilities существуют в Registry;
- token limits достаточны;
- Controls не конфликтуют;
- fallback ACTIVE.

# 26. Data Model

## RuntimeProfile

```text
id UUID PK
workspace_id UUID NULL
key VARCHAR
name VARCHAR
description TEXT
type VARCHAR
status VARCHAR
owner_team_id UUID NULL
current_active_version_id UUID NULL
created_by UUID
created_at TIMESTAMP
updated_at TIMESTAMP
archived_at TIMESTAMP NULL
```

`UNIQUE(workspace_id, key)`.

## RuntimeProfileVersion

```text
id UUID PK
runtime_profile_id UUID FK
version_number INTEGER
semantic_version VARCHAR
status VARCHAR
provider_config_json JSONB
model_config_json JSONB
limits_json JSONB
retry_policy_json JSONB
sandbox_policy_json JSONB
filesystem_policy_json JSONB
network_policy_json JSONB
capability_policy_json JSONB
cost_policy_json JSONB
fallback_policy_json JSONB
data_residency_json JSONB
observability_policy_json JSONB
supervision_mode VARCHAR
checksum VARCHAR
created_by UUID
created_at TIMESTAMP
activated_by UUID NULL
activated_at TIMESTAMP NULL
deprecated_at TIMESTAMP NULL
```

Дополнительные таблицы:

```text
runtime_profile_secret_references
runtime_profile_validation_runs
runtime_profile_health_checks
runtime_profile_usage
runtime_resolution_traces
```

# 27. REST API

```http
GET    /api/v1/runtime-profiles
POST   /api/v1/runtime-profiles
GET    /api/v1/runtime-profiles/{id}
PATCH  /api/v1/runtime-profiles/{id}
POST   /api/v1/runtime-profiles/{id}/duplicate
POST   /api/v1/runtime-profiles/{id}/disable
POST   /api/v1/runtime-profiles/{id}/archive

GET    /api/v1/runtime-profiles/{id}/versions
POST   /api/v1/runtime-profiles/{id}/versions
GET    /api/v1/runtime-profiles/{id}/versions/{versionId}
PATCH  /api/v1/runtime-profiles/{id}/versions/{versionId}
POST   /api/v1/runtime-profiles/{id}/versions/{versionId}/validate
POST   /api/v1/runtime-profiles/{id}/versions/{versionId}/activate
POST   /api/v1/runtime-profiles/{id}/versions/{versionId}/deprecate
POST   /api/v1/runtime-profiles/{id}/versions/{versionId}/clone

POST   /api/v1/runtime-profiles/{id}/versions/{versionId}/test-connection
POST   /api/v1/runtime-profiles/{id}/versions/{versionId}/dry-run
GET    /api/v1/runtime-profiles/{id}/versions/{versionId}/health

POST   /api/v1/runtime-profiles/resolve
POST   /api/v1/runtime-profiles/resolve/preview
GET    /api/v1/runtime-profiles/resolution-traces/{traceId}
```

# 28. Runtime Adapter Contract

```text
validateConfiguration()
testConnection()
prepareExecution()
executeSkill()
cancelExecution()
collectUsage()
collectLogs()
cleanupExecution()
```

Typed errors:

```text
PROVIDER_TIMEOUT
RATE_LIMIT
MODEL_UNAVAILABLE
AUTHENTICATION_FAILED
SANDBOX_FAILED
CAPABILITY_DENIED
COST_LIMIT_EXCEEDED
CONTROL_VIOLATION
```

# 29. Snapshot

Execution Snapshot хранит resolved configuration и checksum, но не secret values.

```json
{
  "profileVersionId": "uuid",
  "providerConfig": {},
  "modelConfig": {},
  "limits": {},
  "sandboxPolicy": {},
  "networkPolicy": {},
  "capabilityPolicy": {},
  "checksum": "sha256"
}
```

# 30. Integrations

## Skills

Skill объявляет minimum context, supported providers, required capabilities и sandbox requirement.

## Playbooks

Playbook задаёт default profile, allowed profiles, supervision minimum и cost maximum.

## Flows

Flow задаёт default profile и stage overrides, например restricted profile для чувствительного этапа.

## Controls

Controls могут запретить provider, потребовать EU, STRICT, ZERO_RETENTION или конкретный sandbox.

# 31. Temporal

Activities:

```text
ResolveRuntimeProfileActivity
PrepareSandboxActivity
ResolveSecretsActivity
StartRuntimeActivity
ExecuteSkillActivity
CollectUsageActivity
CleanupSandboxActivity
RunFallbackActivity
```

# 32. Kafka and Audit

Topic: `runtime-profile-events`.

События:

```text
runtime_profile.created
runtime_profile.version.validated
runtime_profile.version.activated
runtime_profile.health.degraded
runtime_profile.resolved
runtime_execution.started
runtime_execution.completed
runtime_execution.failed
runtime_fallback.started
```

# 33. Backend Structure

```text
modules/runtime-profiles/
├── domain
├── application
├── infrastructure
│   ├── provider-registry
│   ├── runtime-adapters
│   ├── sandbox-manager
│   └── secret-resolver
├── api
└── tests
```

Основные сервисы:

```text
RuntimeProfileResolver
RuntimeProfileValidator
ProviderRegistry
ModelRegistry
RuntimeAdapterFactory
SandboxManager
SecretResolver
CostGuard
FallbackResolver
RuntimeHealthService
```

# 34. Frontend Structure

```text
pages/runtime-profiles/
├── RuntimeProfilesCatalogPage
├── RuntimeProfileDetailPage
├── RuntimeProfileEditorPage
├── EffectiveRuntimePreviewPage
└── RuntimeProfileHealthPage
```

Reusable components:

```text
RuntimeProfileCard
ProviderBadge
ModelBadge
SandboxBadge
HealthBadge
ProviderConfigForm
ModelConfigForm
LimitsForm
CapabilityPolicyEditor
FallbackChainEditor
EffectiveRuntimePreview
ValidationProblemsPanel
VersionDiffViewer
```

# 35. RBAC

```text
runtime_profile.read
runtime_profile.create
runtime_profile.edit
runtime_profile.validate
runtime_profile.activate
runtime_profile.disable
runtime_profile.archive
runtime_profile.test
runtime_profile.resolve_preview
runtime_profile.audit.read
runtime_secret_reference.manage
```

# 36. NFR

- catalog p95 < 500 ms;
- resolution p95 < 300 ms;
- validation p95 < 2 s;
- connection test timeout 10 s;
- immutable ACTIVE versions;
- no secret persistence;
- health monitoring and circuit breakers;
- autosave 5 s;
- optimistic locking;
- full tracing;
- configuration checksum.

# 37. Tests

Unit:

- priority resolution;
- capability intersection;
- fallback cycles;
- limits;
- secret references;
- Control tightening.

Integration:

- create/activate;
- provider test;
- sandbox;
- secrets;
- fallback;
- snapshot;
- audit.

E2E:

```text
Create Profile
→ Configure Provider and Model
→ Configure Sandbox and Capabilities
→ Validate
→ Test Connection
→ Activate
→ Bind to Playbook
→ Start Execution
→ Freeze Snapshot
→ Execute Skill
→ Collect Tokens, Cost and Logs
```

# 38. Migration Plan

1. Найти Agent/model configuration в текущем проекте.
2. Удалить Agent-oriented naming.
3. Ввести RuntimeProfile и RuntimeProfileVersion.
4. Реализовать catalog и detail.
5. Добавить Provider Registry.
6. Добавить validation и health.
7. Добавить resolver.
8. Добавить Runtime Adapter interface.
9. Интегрировать Snapshot и Execution Inspector.
10. Удалить production mocks.

# 39. Pull Request Plan

```text
PR-1 Catalog and detail shell
PR-2 Schema, CRUD and versioning
PR-3 Editor and provider-specific validation
PR-4 Sandbox, network, capabilities and secrets
PR-5 Effective preview, health and fallback
PR-6 Runtime adapters, Temporal, Snapshot and Kafka
```

# 40. Definition of Done

Раздел завершён, если profile версионируется, валидируется, активируется, безопасно разрешает secrets, ограничивает capabilities, запускает sandboxed runtime, поддерживает fallback, фиксируется в snapshot и полностью виден в Execution Inspector.

# 41. Первое задание coding-агенту

1. Просканировать репозиторий.
2. Найти текущие Agent/provider/model settings.
3. Создать `docs/runtime-profiles/CURRENT_STATE.md`.
4. Добавить schema `runtime_profiles` и `runtime_profile_versions`.
5. Реализовать read-only catalog API.
6. Подключить текущий UI к API.
7. Добавить detail shell и validation skeleton.
8. Добавить tests.
9. Не реализовывать реальный provider execution до прохождения CRUD и validation tests.

# 42. Итоговая модель

```text
Skill Requirements
+ Flow / Playbook Binding
+ Workspace Defaults
+ Controls
  ↓
Runtime Profile Resolver
  ↓
Effective Runtime Configuration
  ├── Provider
  ├── Model
  ├── Limits
  ├── Sandbox
  ├── Network
  ├── Capabilities
  ├── Secrets
  ├── Cost
  └── Fallback
  ↓
Skill Runtime
```
