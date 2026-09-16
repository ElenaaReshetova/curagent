# PLATFORM_DATA_ARCHITECTURE_FOR_CURSOR.md

## Governed AI Delivery Platform
### Полное описание хранения данных, схемы БД, YAML-манифестов, object storage, runtime state и связи с UI

---

# 0. Назначение документа

Этот документ описывает, где и в каком виде должны храниться данные платформы:

- какие данные находятся в реляционной БД;
- какие данные находятся в JSONB;
- какие данные описываются YAML-манифестами;
- что хранится в object storage;
- что хранится в поисковом или vector-хранилище;
- что является runtime state;
- что является immutable snapshot;
- как данные связаны с UI;
- какие API обслуживают каждый UI-модуль;
- как избежать дублирования и рассинхронизации.

Документ предназначен для coding-агента Cursor и является архитектурным ориентиром для реализации backend, migrations, repositories, API и frontend bindings.

---

# 1. Общий принцип хранения

Платформа использует несколько типов хранения, потому что разные классы данных имеют разные требования.

```text
PostgreSQL
  ├── основные бизнес-сущности
  ├── связи
  ├── версии
  ├── состояния
  ├── права
  ├── audit metadata
  └── runtime indexes

JSONB в PostgreSQL
  ├── графы
  ├── schemas
  ├── mappings
  ├── policies
  ├── snapshots
  └── provider-specific config

YAML / Git repository
  ├── portable manifests
  ├── adapter definitions
  ├── capability definitions
  ├── seed data
  ├── environment config
  └── infrastructure-as-code

Object Storage
  ├── artifacts
  ├── evidence files
  ├── large logs
  ├── exported packages
  ├── attachments
  └── source documents

Search / Vector Store
  ├── indexed knowledge chunks
  ├── embeddings
  ├── semantic metadata
  └── retrieval indexes

Kafka / Event Log
  ├── domain events
  ├── integration events
  ├── runtime events
  └── async processing

Redis / Cache
  ├── short-lived locks
  ├── rate limits
  ├── temporary session state
  ├── hot catalog cache
  └── SSE fan-out state
```

---

# 2. Источник истины

Для каждой сущности должен быть ровно один authoritative source.

| Сущность | Источник истины |
|---|---|
| Playbook | PostgreSQL |
| Playbook Version | PostgreSQL |
| Playbook graph draft | PostgreSQL JSONB |
| Active compiled Playbook | PostgreSQL JSONB / normalized runtime tables |
| Skill metadata | PostgreSQL |
| Skill implementation manifest | YAML or package manifest |
| Rule | PostgreSQL |
| Control | PostgreSQL |
| Runtime Profile | PostgreSQL |
| Integration Connection | PostgreSQL |
| Integration Definition | YAML/package registry + PostgreSQL projection |
| Capability Definition | YAML/package registry + PostgreSQL projection |
| Knowledge Space | PostgreSQL |
| Knowledge documents | Object Storage |
| Knowledge chunks and embeddings | Search/Vector Store |
| Execution state | PostgreSQL + Temporal |
| Artifact metadata | PostgreSQL |
| Artifact body/file | Object Storage |
| Evidence metadata | PostgreSQL |
| Evidence body/file | Object Storage |
| Audit | PostgreSQL / append-only audit store |
| Domain events | Kafka |

Нельзя поддерживать два равноправных источника истины.

---

# 3. Что хранить в реляционной БД

Реляционная БД используется для данных, которым нужны:

- транзакции;
- связи;
- foreign keys;
- фильтрация;
- сортировка;
- RBAC;
- lifecycle;
- versioning;
- optimistic locking;
- audit;
- tenant isolation.

Рекомендуемая основная БД:

```text
PostgreSQL
```

---

# 4. Базовые системные таблицы

## workspaces

```text
id UUID PK
key VARCHAR UNIQUE
name VARCHAR
status VARCHAR
region VARCHAR
created_at TIMESTAMP
updated_at TIMESTAMP
```

## users

```text
id UUID PK
external_identity_id VARCHAR
email VARCHAR
display_name VARCHAR
status VARCHAR
created_at TIMESTAMP
```

## teams

```text
id UUID PK
workspace_id UUID FK
key VARCHAR
name VARCHAR
created_at TIMESTAMP
```

## roles

```text
id UUID PK
key VARCHAR
name VARCHAR
scope_type VARCHAR
```

## permissions

```text
id UUID PK
key VARCHAR UNIQUE
description TEXT
```

## role_permissions

```text
role_id UUID FK
permission_id UUID FK
```

## workspace_memberships

```text
workspace_id UUID FK
user_id UUID FK
role_id UUID FK
status VARCHAR
```

---

# 5. Общий versioning pattern

Все конфигурируемые сущности должны использовать одинаковую модель:

```text
Entity
  └── EntityVersion
```

Entity хранит:

- стабильный identity;
- key;
- name;
- owner;
- current active version;
- lifecycle.

Version хранит:

- immutable definition;
- semantic version;
- status;
- checksum;
- author;
- timestamps.

Пример:

```text
playbooks
playbook_versions

skills
skill_versions

rules
rule_versions

controls
control_versions

runtime_profiles
runtime_profile_versions

integration_connections
integration_connection_versions

capabilities
capability_versions
```

---

# 6. Playbooks

## playbooks

```text
id UUID PK
workspace_id UUID FK
key VARCHAR
name VARCHAR
description TEXT
category VARCHAR
owner_team_id UUID FK NULL
status VARCHAR
current_active_version_id UUID NULL
created_by UUID
created_at TIMESTAMP
updated_at TIMESTAMP
archived_at TIMESTAMP NULL
```

Constraint:

```text
UNIQUE(workspace_id, key)
```

## playbook_versions

```text
id UUID PK
playbook_id UUID FK
version_number INTEGER
semantic_version VARCHAR
status VARCHAR
graph_json JSONB
input_schema_json JSONB
output_schema_json JSONB
artifact_contract_json JSONB
default_runtime_policy_json JSONB
compiled_definition_json JSONB
dependency_snapshot_json JSONB
checksum VARCHAR
revision INTEGER
created_by UUID
created_at TIMESTAMP
validated_at TIMESTAMP NULL
activated_at TIMESTAMP NULL
deprecated_at TIMESTAMP NULL
```

## playbook_nodes

Рекомендуется хранить нормализованную проекцию для runtime, аналитики и dependency queries.

```text
id UUID PK
playbook_version_id UUID FK
node_key VARCHAR
node_type VARCHAR
name VARCHAR
description TEXT
config_json JSONB
input_mapping_json JSONB
output_mapping_json JSONB
retry_policy_json JSONB
timeout_policy_json JSONB
error_policy_json JSONB
position_json JSONB
```

## playbook_transitions

```text
id UUID PK
playbook_version_id UUID FK
source_node_key VARCHAR
source_outcome VARCHAR
target_node_key VARCHAR
priority INTEGER
condition_json JSONB NULL
label VARCHAR NULL
```

---

# 7. Как Playbook связан с UI

## Playbooks Catalog

UI получает:

```http
GET /api/v1/playbooks
```

Источник:

```text
playbooks
+ current active version summary
+ draft version summary
+ usage counters
```

Карточка Playbook отображает:

```text
name              ← playbooks.name
key               ← playbooks.key
status            ← playbooks.status
active version    ← playbook_versions.semantic_version
owner             ← teams.name
last updated      ← playbooks.updated_at
usage             ← aggregate from playbook_runs
```

## Playbook Designer

UI получает:

```http
GET /api/v1/playbooks/{id}/versions/{versionId}/designer
```

Response собирается из:

```text
playbooks
playbook_versions.graph_json
playbook_versions.revision
playbook_versions.status
node type schemas
permissions
validation summary
dependency summary
```

Designer изменяет только Draft Version.

Autosave пишет:

```text
playbook_versions.graph_json
playbook_versions.revision
playbook_nodes
playbook_transitions
```

`position_json` используется только UI.

Runtime не использует координаты.

---

# 8. Skills

## skills

```text
id UUID PK
workspace_id UUID NULL
key VARCHAR
name VARCHAR
description TEXT
category VARCHAR
status VARCHAR
current_active_version_id UUID NULL
owner_team_id UUID NULL
created_at TIMESTAMP
```

## skill_versions

```text
id UUID PK
skill_id UUID FK
semantic_version VARCHAR
status VARCHAR
interface_key VARCHAR
input_schema_json JSONB
output_schema_json JSONB
implementation_type VARCHAR
implementation_ref VARCHAR
runtime_requirements_json JSONB
required_capabilities_json JSONB
default_rules_json JSONB
default_controls_json JSONB
checksum VARCHAR
created_at TIMESTAMP
activated_at TIMESTAMP NULL
```

---

# 9. Что в Skills хранится в YAML

Skill implementation manifest может храниться в Git/package repository.

```yaml
apiVersion: platform.ai/v1
kind: SkillImplementation

metadata:
  key: requirements-generate-openai
  version: 1.4.0

spec:
  interface: requirements.generate
  runtime:
    type: llm
    entrypoint: src/requirements/generate.py

  inputSchema:
    ref: schemas/input.json

  outputSchema:
    ref: schemas/output.json

  capabilities:
    required:
      - knowledge.search
      - artifact.create

  runtimeRequirements:
    network: restricted
    filesystem: ephemeral
    maxDurationSeconds: 900
```

YAML manifest является package definition.

После регистрации он проецируется в PostgreSQL.

UI не читает YAML напрямую.

---

# 10. Rules

## rules

```text
id UUID PK
workspace_id UUID NULL
key VARCHAR
name VARCHAR
description TEXT
status VARCHAR
current_active_version_id UUID NULL
owner_team_id UUID NULL
```

## rule_versions

```text
id UUID PK
rule_id UUID FK
semantic_version VARCHAR
status VARCHAR
rule_type VARCHAR
content_text TEXT
condition_json JSONB
priority INTEGER
scope_json JSONB
conflict_policy_json JSONB
checksum VARCHAR
created_at TIMESTAMP
activated_at TIMESTAMP NULL
```

Правило может хранить основной текст в `content_text`, а условия и scope — в JSONB.

---

# 11. Controls

## controls

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
```

## control_versions

```text
id UUID PK
control_id UUID FK
semantic_version VARCHAR
status VARCHAR
severity VARCHAR
applicability_json JSONB
evaluation_points_json JSONB
evaluation_type VARCHAR
evaluation_config_json JSONB
enforcement_policy_json JSONB
evidence_requirements_json JSONB
remediation_json JSONB
exception_policy_json JSONB
monitoring_policy_json JSONB
checksum VARCHAR
created_at TIMESTAMP
activated_at TIMESTAMP NULL
```

## control_evaluations

```text
id UUID PK
execution_id UUID NULL
control_version_id UUID FK
evaluation_point VARCHAR
entity_type VARCHAR
entity_id UUID NULL
context_json JSONB
result VARCHAR
severity VARCHAR
blocking BOOLEAN
message TEXT
evidence_json JSONB
remediation_json JSONB
duration_ms INTEGER
evaluated_at TIMESTAMP
```

## control_violations

```text
id UUID PK
control_evaluation_id UUID FK
status VARCHAR
owner_id UUID NULL
first_detected_at TIMESTAMP
last_detected_at TIMESTAMP
resolved_at TIMESTAMP NULL
resolution_json JSONB NULL
```

---

# 12. Runtime Profiles

## runtime_profiles

```text
id UUID PK
workspace_id UUID NULL
key VARCHAR
name VARCHAR
description TEXT
status VARCHAR
current_active_version_id UUID NULL
owner_team_id UUID NULL
```

## runtime_profile_versions

```text
id UUID PK
runtime_profile_id UUID FK
semantic_version VARCHAR
status VARCHAR
provider_config_json JSONB
model_config_json JSONB
sandbox_policy_json JSONB
filesystem_policy_json JSONB
network_policy_json JSONB
capability_policy_json JSONB
secret_references_json JSONB
cost_policy_json JSONB
retry_policy_json JSONB
fallback_policy_json JSONB
supervision_policy_json JSONB
checksum VARCHAR
created_at TIMESTAMP
activated_at TIMESTAMP NULL
```

Raw secrets не хранятся.

Только references:

```text
vault://...
aws-secrets://...
k8s-secret://...
```

---

# 13. Integrations

## integration_definitions

```text
id UUID PK
key VARCHAR UNIQUE
name VARCHAR
category VARCHAR
adapter_type VARCHAR
adapter_version VARCHAR
supported_auth_types_json JSONB
supported_capabilities_json JSONB
configuration_schema_json JSONB
status VARCHAR
```

## integration_connections

```text
id UUID PK
workspace_id UUID FK
definition_id UUID FK
key VARCHAR
name VARCHAR
description TEXT
environment VARCHAR
region VARCHAR NULL
status VARCHAR
health_status VARCHAR
owner_team_id UUID NULL
current_version_id UUID NULL
created_at TIMESTAMP
```

## integration_connection_versions

```text
id UUID PK
connection_id UUID FK
semantic_version VARCHAR
status VARCHAR
adapter_version VARCHAR
endpoint_config_json JSONB
auth_config_json JSONB
scopes_json JSONB
rate_limit_policy_json JSONB
retry_policy_json JSONB
circuit_breaker_policy_json JSONB
mapping_config_json JSONB
checksum VARCHAR
created_at TIMESTAMP
activated_at TIMESTAMP NULL
```

## integration_credential_references

```text
id UUID PK
connection_version_id UUID FK
purpose VARCHAR
secret_reference VARCHAR
provider VARCHAR
```

---

# 14. Что в Integrations хранится в YAML

Connector Definition может быть YAML-манифестом.

```yaml
apiVersion: platform.ai/v1
kind: IntegrationDefinition

metadata:
  key: jira-cloud
  version: 2.3.0

spec:
  category: WORK_MANAGEMENT
  adapter:
    type: http
    entrypoint: adapters/jira

  authentication:
    supported:
      - OAUTH2
      - API_TOKEN

  capabilities:
    - work_item.read
    - work_item.search
    - work_item.update

  configurationSchema:
    ref: schemas/jira-config.json

  webhookSupport:
    enabled: true

  syncSupport:
    incremental: true
```

После установки manifest регистрируется в `integration_definitions`.

---

# 15. Capability Registry

## capabilities

```text
id UUID PK
workspace_id UUID NULL
key VARCHAR
name VARCHAR
description TEXT
category VARCHAR
risk_level VARCHAR
status VARCHAR
current_active_version_id UUID NULL
```

## capability_versions

```text
id UUID PK
capability_id UUID FK
semantic_version VARCHAR
status VARCHAR
input_schema_json JSONB
output_schema_json JSONB
authorization_policy_json JSONB
control_requirements_json JSONB
runtime_requirements_json JSONB
audit_policy_json JSONB
checksum VARCHAR
created_at TIMESTAMP
activated_at TIMESTAMP NULL
```

## capability_bindings

```text
id UUID PK
capability_version_id UUID FK
integration_connection_version_id UUID FK
adapter_operation VARCHAR
input_mapping_json JSONB
output_mapping_json JSONB
priority INTEGER
enabled BOOLEAN
```

---

# 16. Что в Capability Registry хранится в YAML

Capability definition удобна как переносимый manifest.

```yaml
apiVersion: platform.ai/v1
kind: Capability

metadata:
  key: work_item.read
  version: 1.0.0

spec:
  category: WORK_MANAGEMENT
  risk: LOW

  inputSchema:
    type: object
    required: [id]

  outputSchema:
    type: object
    required: [id, title, status]

  authorization:
    permission: capability.work_item.read

  audit:
    level: FULL

  controls:
    required: []
```

YAML используется для package distribution и Git review.

PostgreSQL используется для runtime lookup, UI и bindings.

---

# 17. Knowledge Spaces

## knowledge_spaces

```text
id UUID PK
workspace_id UUID FK
key VARCHAR
name VARCHAR
description TEXT
status VARCHAR
classification VARCHAR
region VARCHAR NULL
owner_team_id UUID NULL
current_version_id UUID NULL
```

## knowledge_space_versions

```text
id UUID PK
knowledge_space_id UUID FK
semantic_version VARCHAR
status VARCHAR
retrieval_policy_json JSONB
citation_policy_json JSONB
freshness_policy_json JSONB
classification_policy_json JSONB
source_config_json JSONB
checksum VARCHAR
created_at TIMESTAMP
activated_at TIMESTAMP NULL
```

## knowledge_sources

```text
id UUID PK
knowledge_space_id UUID FK
integration_connection_id UUID NULL
source_type VARCHAR
external_scope_json JSONB
sync_mode VARCHAR
status VARCHAR
last_sync_at TIMESTAMP NULL
```

---

# 18. Knowledge documents and chunks

## PostgreSQL metadata

```text
knowledge_documents
- id
- knowledge_space_id
- source_id
- external_id
- title
- mime_type
- object_storage_key
- checksum
- version
- classification
- created_at
- updated_at
```

## Object Storage

Хранит:

```text
original document
normalized document
extracted text
attachments
```

## Search / Vector Store

Хранит:

```text
chunk id
document id
chunk text
embedding
metadata
source version
classification
```

PostgreSQL связывает chunk index с document version.

---

# 19. Executions

## executions

```text
id UUID PK
workspace_id UUID FK
execution_type VARCHAR
root_playbook_version_id UUID FK
status VARCHAR
priority VARCHAR
input_json JSONB
output_json JSONB NULL
snapshot_json JSONB
progress_json JSONB
failure_json JSONB NULL
created_by UUID
created_at TIMESTAMP
started_at TIMESTAMP NULL
completed_at TIMESTAMP NULL
```

## playbook_runs

```text
id UUID PK
execution_id UUID FK
parent_playbook_run_id UUID NULL
playbook_version_id UUID FK
status VARCHAR
input_json JSONB
output_json JSONB NULL
context_json JSONB
runtime_snapshot_json JSONB
started_at TIMESTAMP NULL
completed_at TIMESTAMP NULL
failure_json JSONB NULL
```

## step_runs

```text
id UUID PK
playbook_run_id UUID FK
node_key VARCHAR
node_type VARCHAR
status VARCHAR
attempt_count INTEGER
input_json JSONB
output_json JSONB NULL
outcome VARCHAR NULL
started_at TIMESTAMP NULL
completed_at TIMESTAMP NULL
failure_json JSONB NULL
```

## skill_runs

```text
id UUID PK
step_run_id UUID FK
skill_version_id UUID FK
runtime_profile_version_id UUID FK
status VARCHAR
input_json JSONB
output_json JSONB NULL
provider_metadata_json JSONB
started_at TIMESTAMP
completed_at TIMESTAMP NULL
failure_json JSONB NULL
```

## execution_events

```text
id UUID PK
execution_id UUID FK
sequence_number BIGINT
event_type VARCHAR
entity_type VARCHAR
entity_id UUID NULL
payload_json JSONB
occurred_at TIMESTAMP
```

---

# 20. Temporal и PostgreSQL

Temporal является orchestration state machine.

PostgreSQL является business source of truth.

```text
Temporal
- workflow state
- timers
- signals
- retries
- durable orchestration

PostgreSQL
- Execution
- Playbook Run
- Step Run
- Attempts
- Artifacts
- Evidence
- Audit
```

Нельзя использовать Temporal visibility store как основной UI backend.

UI читает runtime state через application API, которое использует PostgreSQL и при необходимости Temporal queries.

---

# 21. Execution Snapshot

`snapshot_json` содержит immutable references:

```json
{
  "playbookVersionId": "uuid",
  "playbookChecksum": "sha256",
  "skillVersions": [],
  "ruleVersions": [],
  "controlVersions": [],
  "runtimeProfileVersions": [],
  "knowledgeSpaceVersions": [],
  "integrationConnectionVersions": [],
  "capabilityVersions": []
}
```

Secrets и full artifact bodies в snapshot не входят.

---

# 22. Human Checkpoints

## human_checkpoints

```text
id UUID PK
execution_id UUID FK
playbook_run_id UUID FK
step_run_id UUID FK
checkpoint_type VARCHAR
status VARCHAR
title VARCHAR
question TEXT
assignment_policy_json JSONB
sla_policy_json JSONB
review_context_json JSONB
created_at TIMESTAMP
due_at TIMESTAMP NULL
completed_at TIMESTAMP NULL
```

## checkpoint_assignments

```text
id UUID PK
checkpoint_id UUID FK
assignee_type VARCHAR
assignee_id UUID
status VARCHAR
assigned_at TIMESTAMP
```

## checkpoint_decisions

```text
id UUID PK
checkpoint_id UUID FK
decision_key VARCHAR
comment TEXT NULL
decided_by UUID
decision_payload_json JSONB
created_at TIMESTAMP
```

Decision immutable.

---

# 23. Artifacts

## artifacts

```text
id UUID PK
workspace_id UUID FK
artifact_type VARCHAR
name VARCHAR
status VARCHAR
current_version_id UUID NULL
created_by UUID
created_at TIMESTAMP
```

## artifact_versions

```text
id UUID PK
artifact_id UUID FK
version_number INTEGER
mime_type VARCHAR
object_storage_key VARCHAR
content_hash VARCHAR
metadata_json JSONB
source_execution_id UUID NULL
source_step_run_id UUID NULL
created_at TIMESTAMP
published_at TIMESTAMP NULL
```

Large content не хранить в PostgreSQL.

Для небольших JSON artifacts допустим `content_json`, но нужен размеровой лимит.

---

# 24. Evidence

## evidence_bundles

```text
id UUID PK
execution_id UUID FK
step_run_id UUID NULL
skill_run_id UUID NULL
status VARCHAR
summary_json JSONB
created_at TIMESTAMP
```

## evidence_items

```text
id UUID PK
evidence_bundle_id UUID FK
evidence_type VARCHAR
source_type VARCHAR
source_id VARCHAR
object_storage_key VARCHAR NULL
content_hash VARCHAR
metadata_json JSONB
created_at TIMESTAMP
```

Evidence item может ссылаться на:

- Knowledge document;
- external URL;
- integration response;
- artifact section;
- human decision;
- control result.

---

# 25. Audit

## audit_events

```text
id UUID PK
workspace_id UUID FK
actor_type VARCHAR
actor_id UUID NULL
event_type VARCHAR
entity_type VARCHAR
entity_id UUID NULL
correlation_id VARCHAR
payload_json JSONB
occurred_at TIMESTAMP
```

Audit должен быть append-only.

Изменение audit record запрещено.

---

# 26. YAML: где использовать

YAML следует использовать для переносимых и reviewable definitions.

Подходящие данные:

```text
Skill implementation manifests
Integration definitions
Capability definitions
Seed Controls
Seed Rules
Default Runtime Profiles
Environment bootstrap
Package metadata
Deployment configuration
```

YAML не подходит как runtime source для:

```text
Execution state
Checkpoint state
Artifact metadata
Live Integration Connection
User-created Draft Playbook
Audit
Violations
Runtime Profile secrets
```

---

# 27. GitOps lifecycle YAML

```text
YAML committed
  ↓
CI validates schema
  ↓
Package built
  ↓
Registry install
  ↓
Definition imported into PostgreSQL
  ↓
UI displays imported entity
  ↓
Runtime resolves PostgreSQL projection
```

YAML нельзя читать с файловой системы на каждый runtime call.

---

# 28. JSONB: где использовать

JSONB подходит для:

- schemas;
- graph definitions;
- mappings;
- provider-specific config;
- policies;
- applicability;
- runtime snapshots;
- diagnostic payloads;
- context fragments.

Не следует помещать в JSONB данные, по которым постоянно нужны:

- joins;
- unique constraints;
- access control;
- high-volume filtering;
- lifecycle queries.

Такие поля следует нормализовать.

---

# 29. Object Storage

Рекомендуется S3-compatible storage.

Bucket layout:

```text
artifacts/{workspaceId}/{artifactId}/{versionId}
evidence/{workspaceId}/{bundleId}/{itemId}
knowledge/{workspaceId}/{documentId}/{version}
attachments/{workspaceId}/{entityType}/{entityId}
exports/{workspaceId}/{exportId}
logs/{workspaceId}/{executionId}
```

PostgreSQL хранит только:

```text
object_storage_key
mime_type
size
checksum
encryption metadata
```

---

# 30. Search and Vector Store

Knowledge retrieval pipeline:

```text
Knowledge Source
  ↓
Document metadata in PostgreSQL
  ↓
Raw file in Object Storage
  ↓
Extraction
  ↓
Chunking
  ↓
Embeddings
  ↓
Vector/Search Store
```

Chunk metadata:

```text
workspaceId
knowledgeSpaceId
documentId
documentVersion
chunkId
classification
source
freshness
checksum
```

Tenant and classification filters обязательны при retrieval.

---

# 31. Redis

Redis используется только для transient data.

Подходящие use cases:

```text
distributed locks
autosave debounce coordination
rate limit counters
short-lived OAuth state
SSE subscriptions
hot cache
idempotency keys
temporary wizard state
```

Redis не является authoritative storage.

---

# 32. Kafka

Kafka хранит поток событий, а не UI state.

Topics:

```text
playbook-events
skill-events
control-events
integration-events
execution-events
checkpoint-events
artifact-events
audit-events
```

Consumers:

```text
analytics
notifications
search indexing
audit projection
metrics
continuous controls
```

UI не должен напрямую читать Kafka.

---

# 33. UI-to-data mapping

## Dashboard

Reads:

```text
aggregated executions
violations
checkpoints
artifact counts
integration health
```

Sources:

```text
PostgreSQL materialized views
analytics projections
```

## Playbooks

Reads:

```text
playbooks
playbook_versions
playbook_runs aggregates
```

Writes:

```text
playbooks
playbook_versions
graph_json
nodes
transitions
```

## Skills

Reads:

```text
skills
skill_versions
implementation registry projection
```

Writes:

```text
metadata and version bindings
```

Implementation package usually comes from YAML/package registry.

## Rules

Reads/Writes:

```text
rules
rule_versions
```

## Controls

Reads/Writes:

```text
controls
control_versions
bindings
evaluations
violations
exceptions
```

## Knowledge Spaces

Reads/Writes:

```text
knowledge_spaces
versions
sources
sync state
document metadata
```

Files go to object storage.

## Runtime Profiles

Reads/Writes:

```text
runtime_profiles
runtime_profile_versions
```

Secrets remain in Secret Manager.

## Executions

Reads:

```text
executions
playbook_runs
step_runs
skill_runs
events
artifacts
evidence
checkpoints
```

Writes occur through runtime services, not directly from UI.

## Human Checkpoints

Reads/Writes:

```text
human_checkpoints
assignments
decisions
comments
attachments
```

## Integrations

Reads/Writes:

```text
integration_connections
versions
credential references
bindings
health
sync
webhooks
```

## Capability Registry

Reads/Writes:

```text
capabilities
versions
integration bindings
usage analytics
```

## Audit

Read-only UI over:

```text
audit_events
```

---

# 34. API boundary

Frontend никогда не обращается напрямую к базе.

```text
UI
  ↓
REST / GraphQL API
  ↓
Application Services
  ↓
Repositories
  ↓
PostgreSQL / Object Storage / Vector Store
```

Application Services отвечают за:

- authorization;
- workspace filtering;
- version rules;
- transactions;
- validation;
- event publishing;
- audit;
- object storage operations.

---

# 35. UI Object IDs

Frontend должен использовать стабильные IDs:

```text
playbookId
versionId
nodeId
nodeKey
executionId
runId
stepRunId
artifactId
artifactVersionId
checkpointId
controlId
integrationId
capabilityId
```

Нельзя использовать UI array index как identity.

---

# 36. UI state vs server state

## Server state

```text
catalog data
versions
graph
validation
executions
artifacts
checkpoints
health
audit
```

Хранить через:

```text
TanStack Query or equivalent
```

## Local UI state

```text
selected node
panel size
zoom
temporary unsaved field edits
undo stack
open tabs
filters
```

Local UI state не является business source of truth.

---

# 37. Draft graph persistence

Рекомендуемый flow:

```text
User edits graph
  ↓
Local designer state changes
  ↓
Debounced save
  ↓
PATCH with revision
  ↓
Backend transaction
  ↓
Update graph_json
  ↓
Update normalized nodes/transitions
  ↓
Increment revision
  ↓
Return canonical graph
```

Backend transaction должна быть atomic.

---

# 38. Why graph_json and normalized tables both exist

`graph_json` нужен для:

- exact designer document;
- easy load/save;
- version diff;
- export/import.

Normalized tables нужны для:

- runtime lookup;
- dependency analysis;
- node analytics;
- validation queries;
- impact analysis.

Нельзя обновлять их независимо.

Они обновляются одной transaction.

---

# 39. Import/export

Export package:

```text
manifest.yaml
playbook.yaml or playbook.json
schemas/
dependencies.yaml
README.md
```

Database IDs не должны быть обязательными в portable package.

Использовать stable keys и semantic versions.

Import:

```text
Validate package
Resolve keys
Create Draft
Map dependencies
Show unresolved references
```

---

# 40. Secret Manager

Secrets хранятся только во внешнем Secret Manager.

Supported reference format:

```text
vault://path
aws-secrets://path
azure-keyvault://path
gcp-secret://path
k8s-secret://namespace/name/key
```

PostgreSQL хранит:

```text
reference
purpose
provider
metadata
```

UI показывает masked reference.

---

# 41. Data classification

Каждая чувствительная сущность должна иметь classification.

```text
PUBLIC
INTERNAL
CONFIDENTIAL
RESTRICTED
```

Classification влияет на:

- Runtime Profile;
- region;
- logging;
- retention;
- export;
- capability access;
- Knowledge retrieval;
- UI masking.

---

# 42. Retention

Retention policies:

```text
Execution logs
Artifacts
Evidence
Audit
Checkpoints
Integration request logs
Knowledge versions
```

Retention policy хранится в PostgreSQL JSONB.

Deletion executes asynchronously.

Audit deletion может быть запрещён policy.

---

# 43. Soft delete

Использовать для design-time сущностей:

```text
archived_at
status = ARCHIVED
```

Hard delete допустим только для:

```text
never-activated Draft
temporary simulation data
expired cache
```

Runtime records не удалять напрямую.

---

# 44. Optimistic locking

Versioned editable entities должны иметь:

```text
revision INTEGER
```

UI sends:

```http
If-Match: revision
```

Conflict:

```http
409 CONFLICT
```

Применяется к:

```text
Playbook Draft
Rule Draft
Control Draft
Runtime Profile Draft
Integration config Draft
Capability Draft
```

---

# 45. Checksums

Immutable Versions имеют checksum.

```text
SHA-256 of canonical definition
```

Checksum используется для:

- snapshot integrity;
- audit;
- export verification;
- runtime validation;
- cache key.

---

# 46. Materialized views and projections

Для catalog/dashboard нужны projections.

Примеры:

```text
playbook_catalog_view
execution_summary_view
control_health_view
integration_health_view
capability_usage_view
checkpoint_inbox_view
```

UI не должен выполнять тяжёлые aggregate joins на каждый запрос.

---

# 47. Recommended schemas in PostgreSQL

```text
core
iam
playbooks
skills
rules
controls
knowledge
runtime
integrations
capabilities
executions
checkpoints
artifacts
audit
analytics
```

Если проект использует одну schema, сохранить module prefixes в table names.

---

# 48. Transaction boundaries

## Create Playbook

```text
insert playbook
insert initial Draft Version
insert START/END defaults if policy
audit
outbox event
```

## Save Playbook Draft

```text
check revision
update graph_json
replace normalized nodes
replace normalized transitions
increment revision
audit summary
```

## Activate Version

```text
validate
compile
checksum
dependency snapshot
mark active
update parent current_active_version_id
deprecate previous
audit
outbox
```

## Human Decision

```text
validate reviewer
insert immutable decision
update checkpoint
append execution event
outbox signal/event
```

---

# 49. Outbox pattern

Domain events должны публиковаться через transactional outbox.

## outbox_events

```text
id UUID PK
aggregate_type VARCHAR
aggregate_id UUID
event_type VARCHAR
payload_json JSONB
status VARCHAR
created_at TIMESTAMP
published_at TIMESTAMP NULL
```

Flow:

```text
Business transaction
  ↓
Write entity + outbox event
  ↓ commit
Publisher reads outbox
  ↓
Kafka
```

Это предотвращает рассинхронизацию БД и Kafka.

---

# 50. Idempotency

Для write APIs:

```text
Idempotency-Key
```

Использовать для:

- start Execution;
- publish Artifact;
- create webhook;
- capability write;
- Human Decision submission;
- retry action.

## idempotency_keys

```text
key VARCHAR
workspace_id UUID
operation VARCHAR
response_json JSONB
created_at TIMESTAMP
expires_at TIMESTAMP
```

---

# 51. Migration strategy

1. Inventory current mock data.
2. Identify current frontend object shape.
3. Create canonical backend entities.
4. Add migrations.
5. Add repositories.
6. Add APIs.
7. Create adapters from old mock shape to new API response if temporarily needed.
8. Connect UI.
9. Remove production mocks.
10. Add data migration scripts.
11. Add reconciliation tests.
12. Add observability.

---

# 52. Cursor repository task

Cursor должен сначала создать:

```text
docs/data/CURRENT_DATA_ARCHITECTURE.md
```

Документ должен перечислить:

- current database;
- ORM;
- migrations;
- current tables;
- JSON files;
- YAML files;
- localStorage usage;
- mock fixtures;
- object storage;
- Temporal;
- Kafka;
- Redis;
- search/vector store;
- secrets;
- missing components.

---

# 53. Exact Cursor prompt

```text
Use PLATFORM_DATA_ARCHITECTURE_FOR_CURSOR.md as the target architecture.

First inspect the repository and create docs/data/CURRENT_DATA_ARCHITECTURE.md.

Document:
- database technology and ORM;
- current tables and migrations;
- all YAML manifests;
- JSON fixtures;
- mock data;
- localStorage usage;
- object storage integration;
- Kafka/outbox implementation;
- Temporal persistence integration;
- Redis/cache usage;
- vector/search storage;
- Secret Manager integration;
- frontend API clients;
- current UI object shapes.

Then create a gap analysis mapping current structures to the target architecture.

For every major UI module, provide:
- source tables;
- API endpoints;
- read model;
- write model;
- local UI state;
- object storage usage;
- YAML/package source if applicable.

Do not immediately rewrite the entire database.

Implement changes incrementally, beginning with the module currently being developed.

Mandatory rules:
- PostgreSQL is the business source of truth.
- YAML is for portable manifests and package definitions.
- Object Storage stores large binary/text artifacts.
- Search/Vector Store stores retrieval indexes, not authoritative documents.
- Redis is transient only.
- UI never accesses storage directly.
- Active Versions are immutable.
- Draft edits use optimistic locking.
- Secrets are references only.
- Domain events use transactional outbox.
- graph_json and normalized graph tables update in one transaction.
```

---

# 54. Definition of Done

Data architecture считается реализованной, если:

- для каждой сущности определён source of truth;
- реляционные связи имеют foreign keys;
- Draft и Active Version разделены;
- YAML manifests валидируются и импортируются;
- UI читает через API;
- large data находится в Object Storage;
- Knowledge retrieval использует Search/Vector Store;
- secrets не находятся в DB;
- Redis не используется как permanent storage;
- Kafka events публикуются через outbox;
- Execution snapshot immutable;
- audit append-only;
- optimistic locking работает;
- production mocks удалены;
- migrations и tests проходят.

Конец документа.
