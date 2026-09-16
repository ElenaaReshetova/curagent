# INTEGRATIONS_SYSTEM_REQUIREMENTS.md
## Governed AI Delivery Platform
### Полное системное ТЗ на реализацию раздела Integrations

---

# 0. Простое назначение Integrations

Integration — это управляемое подключение платформы к внешней системе.

Он отвечает на вопрос:

> К какой системе подключена платформа, с какими правами, как передаются данные, как отслеживаются ошибки и какие capabilities доступны?

Пример:

```text
Integration: Jira Payments

System:
- Atlassian Jira Cloud

Authentication:
- OAuth 2.0

Scopes:
- issue:read
- issue:write
- project:read

Used by:
- Knowledge Space: Payments
- Capability: work_item.read
- Capability: work_item.update
- Flow triggers: Jira issue created

Health:
- Healthy
```

Integration — это не Capability и не Knowledge Space.

Integration содержит техническое подключение.

Capability описывает разрешённое действие.

Knowledge Space описывает управляемую область получения контекста.

---

# 1. Место в архитектуре

```text
External System
  ↓
Integration Adapter
  ↓
Integration Connection
  ↓
Capability Gateway / Context Broker / Trigger Gateway
  ↓
Skills / Playbooks / Flows / Executions
```

---

# 2. Отличие Integration от Capability

## Integration

Определяет:

- endpoint;
- authentication;
- credentials;
- scopes;
- tenant;
- connection settings;
- rate limits;
- webhooks;
- sync;
- health.

## Capability

Определяет:

- логическое действие;
- входной контракт;
- выходной контракт;
- authorization;
- risk;
- approval;
- audit.

Пример:

```text
Integration:
Jira Payments

Capabilities:
- work_item.read
- work_item.search
- work_item.create
- work_item.update
- work_item.comment
```

Одна Integration может реализовывать несколько Capabilities.

Одна Capability может иметь несколько Integration implementations.

---

# 3. Границы ответственности

Integrations отвечают за:

- connector catalog;
- connection instances;
- authentication;
- credential references;
- scopes;
- endpoint and tenant configuration;
- request mapping;
- response mapping;
- rate limits;
- retries;
- circuit breakers;
- sync jobs;
- webhook subscriptions;
- health checks;
- diagnostics;
- observability;
- secret isolation;
- versioned adapter configuration;
- capability bindings;
- Knowledge Space source bindings;
- trigger bindings;
- audit.

Integrations не отвечают за:

- бизнес-логику Flow;
- prompt generation;
- Rule content;
- Control logic;
- Skill implementation;
- artifact schema;
- human decisions.

---

# 4. Типы Integrations

Поддержать категории:

```text
WORK_MANAGEMENT
KNOWLEDGE
SOURCE_CODE
CI_CD
COMMUNICATION
IDENTITY
STORAGE
DATABASE
OBSERVABILITY
SECURITY
DOCUMENT_MANAGEMENT
CUSTOM_API
CUSTOM_WEBHOOK
CUSTOM_CLI
```

Примеры:

```text
Jira
Confluence
GitHub
GitLab
Bitbucket
Slack
Microsoft Teams
Google Drive
SharePoint
ServiceNow
Azure DevOps
Jenkins
GitHub Actions
PagerDuty
Datadog
Splunk
S3
PostgreSQL
Custom HTTP API
```

---

# 5. Жизненный цикл

```text
DRAFT
CONFIGURING
VALIDATING
READY
ACTIVE
DEGRADED
DISCONNECTED
DISABLED
ARCHIVED
```

Правила:

- только ACTIVE Integration доступна runtime;
- DEGRADED может использоваться по policy;
- DISCONNECTED не принимает новые вызовы;
- credential rotation не должна менять logical integration ID;
- active config version immutable;
- изменения создают новую configuration version;
- execution snapshot фиксирует adapter/config version;
- secrets не входят в snapshot.

---

# 6. Основные сущности

```text
Integration Definition
  └── Integration Connection
        ├── Configuration Version
        ├── Authentication
        ├── Credential References
        ├── Scopes
        ├── Capability Bindings
        ├── Source Bindings
        ├── Trigger Bindings
        ├── Sync Jobs
        ├── Webhook Subscriptions
        ├── Health Checks
        └── Audit
```

---

# 7. Integration Definition

Definition описывает connector type и adapter contract.

Пример:

```json
{
  "key": "jira-cloud",
  "name": "Jira Cloud",
  "category": "WORK_MANAGEMENT",
  "adapterVersion": "2.3.0",
  "supportedAuthTypes": [
    "OAUTH2",
    "API_TOKEN"
  ],
  "supportedCapabilities": [
    "work_item.read",
    "work_item.search",
    "work_item.create",
    "work_item.update",
    "work_item.comment"
  ],
  "supportsWebhooks": true,
  "supportsIncrementalSync": true
}
```

Definition поставляется платформой или extension package.

---

# 8. Integration Connection

Connection — конкретное подключение к tenant/system.

Пример:

```text
Definition:
- Jira Cloud

Connection:
- Jira Payments Production

Tenant:
- company.atlassian.net

Environment:
- PRODUCTION

Workspace:
- Payments
```

---

# 9. Authentication Types

Поддержать:

```text
OAUTH2
OAUTH2_CLIENT_CREDENTIALS
API_KEY
API_TOKEN
BASIC
BEARER_TOKEN
SERVICE_ACCOUNT
AWS_IAM
AZURE_MANAGED_IDENTITY
GCP_WORKLOAD_IDENTITY
SSH_KEY
MTLS
NONE
CUSTOM
```

Production default — short-lived credentials, workload identity или OAuth.

---

# 10. Credential References

Integration хранит только references:

```text
vault://integrations/jira-payments
aws-secrets://integrations/github-prod
k8s-secret://integrations/slack-bot
```

Запрещено хранить:

- access token;
- refresh token;
- password;
- API key;
- private key;
- client secret.

Credential Resolver передаёт secret только adapter process.

---

# 11. OAuth Lifecycle

Поддержать:

- authorization start;
- callback;
- token exchange;
- refresh;
- revocation;
- scope upgrade;
- reauthorization;
- connection ownership;
- consent audit.

API:

```http
POST /api/v1/integrations/{connectionId}/oauth/start
GET  /api/v1/integrations/oauth/callback
POST /api/v1/integrations/{connectionId}/oauth/refresh
POST /api/v1/integrations/{connectionId}/oauth/revoke
```

---

# 12. Scopes

Scopes должны отображаться:

```text
Requested
Granted
Missing
Excessive
Deprecated
```

Система должна предупреждать при excessive scopes.

Controls могут запретить:

- write scopes;
- admin scopes;
- user impersonation;
- external sharing;
- unrestricted repository access.

---

# 13. Environment and Workspace Isolation

Connection привязана к:

```text
workspace
environment
region
data classification
owner team
```

Production execution не должна использовать Development connection.

Cross-workspace sharing разрешено только explicit binding и permission.

---

# 14. Endpoint Configuration

Поля:

```text
baseUrl
tenantId
organizationId
projectId
region
apiVersion
proxy
tlsPolicy
customHeaders
```

Custom headers не могут содержать raw secrets.

---

# 15. Integration Adapter Contract

```text
IntegrationAdapter
- validateConfiguration()
- testConnection()
- getHealth()
- getSupportedCapabilities()
- executeCapability()
- listResources()
- fetchResource()
- startSync()
- continueSync()
- createWebhook()
- renewWebhook()
- deleteWebhook()
- normalizeEvent()
- rotateCredentials()
```

---

# 16. Capability Binding

Binding связывает Integration с Capability implementation.

Пример:

```json
{
  "capabilityKey": "work_item.read",
  "integrationConnectionId": "uuid",
  "adapterOperation": "getIssue",
  "inputMapping": {},
  "outputMapping": {},
  "priority": 100,
  "enabled": true
}
```

---

# 17. Capability Routing

Если есть несколько connections:

```text
Capability Request
  ↓
Workspace
  ↓
Environment
  ↓
Source project
  ↓
Data classification
  ↓
Health
  ↓
Priority
  ↓
Selected Integration Connection
```

Routing должен быть explainable.

---

# 18. Knowledge Space Source Binding

Integration может быть источником Knowledge Space.

Пример:

```json
{
  "knowledgeSpaceId": "uuid",
  "integrationConnectionId": "uuid",
  "sourceType": "CONFLUENCE",
  "scope": {
    "spaces": ["PAY", "ARCH"]
  },
  "syncMode": "INCREMENTAL",
  "freshnessTargetMinutes": 60
}
```

---

# 19. Trigger Binding

Integration может запускать Flow.

Пример:

```text
Jira issue created
  ↓
Event normalized
  ↓
Trigger matching
  ↓
Flow selected
  ↓
Execution created
```

Binding содержит:

- event type;
- filter;
- mapping;
- deduplication;
- routing;
- retry;
- dead-letter policy.

---

# 20. Webhooks

Поддержать:

- subscription creation;
- verification challenge;
- signature validation;
- secret rotation;
- lease renewal;
- event normalization;
- deduplication;
- replay protection;
- dead-letter queue;
- delivery metrics.

Webhook endpoint:

```http
POST /api/v1/integration-webhooks/{connectionKey}/{subscriptionKey}
```

---

# 21. Event Normalization

External events преобразуются в canonical format.

Пример:

```json
{
  "eventId": "external-id",
  "eventType": "work_item.updated",
  "sourceSystem": "JIRA",
  "connectionId": "uuid",
  "occurredAt": "2026-07-17T10:00:00Z",
  "subject": {
    "type": "work_item",
    "id": "PAY-123"
  },
  "payload": {}
}
```

---

# 22. Deduplication

Использовать:

```text
connectionId
externalEventId
eventType
payloadHash
```

Повторное событие не должно создавать duplicate Execution.

---

# 23. Sync Modes

Поддержать:

```text
NONE
FULL
INCREMENTAL
EVENT_DRIVEN
HYBRID
ON_DEMAND
```

---

# 24. Sync Job

Sync Job содержит:

- source binding;
- cursor;
- checkpoint;
- page;
- status;
- started at;
- completed at;
- records read;
- records updated;
- records failed;
- next run;
- error;
- retry.

Статусы:

```text
QUEUED
RUNNING
PAUSED
COMPLETED
COMPLETED_WITH_WARNINGS
FAILED
CANCELLED
```

---

# 25. Mapping

Поддержать:

```text
Input Mapping
Output Mapping
Event Mapping
Identity Mapping
Field Mapping
Classification Mapping
```

Mapping engine должен использовать declarative expressions.

Запрещён arbitrary executable code.

---

# 26. Schema Registry

Для integration payloads хранить schemas:

```text
Capability input schema
Capability output schema
External payload schema
Canonical event schema
Resource schema
```

Schema versioned.

---

# 27. Rate Limits

Настройки:

```text
requestsPerSecond
requestsPerMinute
burst
concurrentRequests
dailyQuota
providerHeaders
```

Runtime должен учитывать provider rate-limit headers.

---

# 28. Retry Policy

```json
{
  "maximumAttempts": 5,
  "initialIntervalSeconds": 2,
  "backoffCoefficient": 2,
  "maximumIntervalSeconds": 120,
  "retryableErrors": [
    "RATE_LIMIT",
    "TIMEOUT",
    "TEMPORARY_UNAVAILABLE"
  ]
}
```

---

# 29. Circuit Breaker

States:

```text
CLOSED
OPEN
HALF_OPEN
```

Настройки:

```text
failureThreshold
successThreshold
openDuration
rollingWindow
```

---

# 30. Health Model

Health statuses:

```text
HEALTHY
DEGRADED
UNHEALTHY
AUTHENTICATION_REQUIRED
RATE_LIMITED
CONFIGURATION_ERROR
UNKNOWN
```

Health checks:

- DNS;
- TLS;
- authentication;
- API availability;
- permission check;
- scope check;
- webhook status;
- sync lag;
- latency;
- error rate.

---

# 31. Diagnostics

Diagnostics UI должна показывать:

- last successful request;
- last failed request;
- auth status;
- scopes;
- webhook status;
- sync cursor;
- latency;
- rate limit;
- recent errors;
- adapter logs;
- correlation IDs.

Sensitive fields маскируются.

---

# 32. Integration Catalog UI

Показывать:

- name;
- connector;
- category;
- environment;
- workspace;
- status;
- health;
- auth type;
- capabilities;
- source bindings;
- webhook count;
- sync lag;
- owner;
- last checked.

Функции:

- search;
- filter;
- create;
- connect;
- disconnect;
- test;
- disable;
- archive;
- duplicate;
- rotate credentials;
- view usage.

---

# 33. Integration Detail UI

Вкладки:

```text
Overview
Configuration
Authentication
Scopes
Capabilities
Sources
Triggers
Webhooks
Sync
Health
Diagnostics
Usage
Versions
Audit
```

---

# 34. Integration Setup Wizard

Steps:

```text
1. Select Connector
2. General
3. Environment
4. Authentication
5. Scopes
6. Configuration
7. Test Connection
8. Bind Capabilities
9. Configure Sources / Triggers
10. Activate
```

---

# 35. Test Connection

Проверки:

- endpoint reachable;
- TLS valid;
- credentials resolvable;
- authentication valid;
- required scopes granted;
- tenant accessible;
- minimal read operation;
- optional write test;
- webhook capability;
- rate-limit headers.

---

# 36. Dry Run

Dry Run позволяет:

- выполнить capability с test payload;
- проверить mapping;
- увидеть normalized result;
- не сохранять production changes;
- скрыть secrets;
- получить correlation ID.

---

# 37. Usage

Integration Detail показывает usage:

- Capability bindings;
- Knowledge Spaces;
- Flow triggers;
- Playbooks;
- Skills;
- Executions;
- webhook subscriptions;
- sync jobs.

---

# 38. Versioning

Versioned fields:

- endpoint config;
- auth config metadata;
- scopes;
- mapping;
- retry;
- rate limits;
- circuit breaker;
- adapter version;
- bindings.

Secret values versioning управляется Secret Manager, не Integration DB.

---

# 39. Configuration Snapshot

Execution Snapshot содержит:

```json
{
  "integration": {
    "connectionId": "uuid",
    "configurationVersionId": "uuid",
    "adapterDefinitionVersion": "2.3.0",
    "capabilityBindingId": "uuid",
    "checksum": "sha256"
  }
}
```

---

# 40. Data Model

## IntegrationDefinition

```text
IntegrationDefinition
- id UUID PK
- key VARCHAR UNIQUE
- name VARCHAR
- category VARCHAR
- adapter_type VARCHAR
- adapter_version VARCHAR
- supported_auth_types_json JSONB
- supported_capabilities_json JSONB
- configuration_schema_json JSONB
- status VARCHAR
- created_at TIMESTAMP
```

## IntegrationConnection

```text
IntegrationConnection
- id UUID PK
- workspace_id UUID FK
- definition_id UUID FK
- key VARCHAR
- name VARCHAR
- description TEXT
- environment VARCHAR
- region VARCHAR NULL
- status VARCHAR
- health_status VARCHAR
- owner_team_id UUID NULL
- current_version_id UUID NULL
- created_by UUID
- created_at TIMESTAMP
- updated_at TIMESTAMP
- archived_at TIMESTAMP NULL
```

Constraint:

```text
UNIQUE(workspace_id, key)
```

## IntegrationConnectionVersion

```text
IntegrationConnectionVersion
- id UUID PK
- connection_id UUID FK
- version_number INTEGER
- semantic_version VARCHAR
- status VARCHAR
- adapter_version VARCHAR
- endpoint_config_json JSONB
- auth_config_json JSONB
- scopes_json JSONB
- rate_limit_policy_json JSONB
- retry_policy_json JSONB
- circuit_breaker_policy_json JSONB
- mapping_config_json JSONB
- checksum VARCHAR
- created_by UUID
- created_at TIMESTAMP
- activated_at TIMESTAMP NULL
- deprecated_at TIMESTAMP NULL
```

## IntegrationCredentialReference

```text
IntegrationCredentialReference
- id UUID PK
- connection_version_id UUID FK
- purpose VARCHAR
- secret_reference VARCHAR
- provider VARCHAR
- created_at TIMESTAMP
```

## IntegrationCapabilityBinding

```text
IntegrationCapabilityBinding
- id UUID PK
- connection_version_id UUID FK
- capability_key VARCHAR
- adapter_operation VARCHAR
- input_mapping_json JSONB
- output_mapping_json JSONB
- priority INTEGER
- enabled BOOLEAN
- created_at TIMESTAMP
```

## IntegrationSourceBinding

```text
IntegrationSourceBinding
- id UUID PK
- connection_id UUID FK
- knowledge_space_id UUID FK
- source_type VARCHAR
- scope_json JSONB
- sync_mode VARCHAR
- freshness_target_minutes INTEGER NULL
- enabled BOOLEAN
- created_at TIMESTAMP
```

## IntegrationTriggerBinding

```text
IntegrationTriggerBinding
- id UUID PK
- connection_id UUID FK
- event_type VARCHAR
- filter_json JSONB
- mapping_json JSONB
- flow_version_id UUID FK
- deduplication_policy_json JSONB
- enabled BOOLEAN
- created_at TIMESTAMP
```

## IntegrationWebhookSubscription

```text
IntegrationWebhookSubscription
- id UUID PK
- connection_id UUID FK
- external_subscription_id VARCHAR NULL
- subscription_key VARCHAR
- event_types_json JSONB
- status VARCHAR
- secret_reference VARCHAR NULL
- expires_at TIMESTAMP NULL
- last_event_at TIMESTAMP NULL
- created_at TIMESTAMP
```

## IntegrationSyncJob

```text
IntegrationSyncJob
- id UUID PK
- source_binding_id UUID FK
- status VARCHAR
- cursor_json JSONB
- records_read BIGINT
- records_updated BIGINT
- records_failed BIGINT
- started_at TIMESTAMP
- completed_at TIMESTAMP NULL
- error_json JSONB NULL
```

## IntegrationHealthCheck

```text
IntegrationHealthCheck
- id UUID PK
- connection_id UUID FK
- status VARCHAR
- latency_ms INTEGER NULL
- auth_status VARCHAR
- scope_status VARCHAR
- webhook_status VARCHAR
- sync_lag_seconds INTEGER NULL
- result_json JSONB
- checked_at TIMESTAMP
```

## IntegrationRequestLog

```text
IntegrationRequestLog
- id UUID PK
- connection_id UUID FK
- capability_key VARCHAR NULL
- operation VARCHAR
- correlation_id VARCHAR
- status VARCHAR
- request_metadata_json JSONB
- response_metadata_json JSONB
- duration_ms INTEGER
- occurred_at TIMESTAMP
```

---

# 41. REST API

## Definitions

```http
GET /api/v1/integration-definitions
GET /api/v1/integration-definitions/{definitionId}
```

## Connections

```http
GET    /api/v1/integrations
POST   /api/v1/integrations
GET    /api/v1/integrations/{connectionId}
PATCH  /api/v1/integrations/{connectionId}
POST   /api/v1/integrations/{connectionId}/disable
POST   /api/v1/integrations/{connectionId}/enable
POST   /api/v1/integrations/{connectionId}/disconnect
POST   /api/v1/integrations/{connectionId}/archive
POST   /api/v1/integrations/{connectionId}/duplicate
```

## Versions

```http
GET  /api/v1/integrations/{connectionId}/versions
POST /api/v1/integrations/{connectionId}/versions
GET  /api/v1/integrations/{connectionId}/versions/{versionId}
PATCH /api/v1/integrations/{connectionId}/versions/{versionId}
POST /api/v1/integrations/{connectionId}/versions/{versionId}/validate
POST /api/v1/integrations/{connectionId}/versions/{versionId}/activate
POST /api/v1/integrations/{connectionId}/versions/{versionId}/deprecate
```

## Testing

```http
POST /api/v1/integrations/{connectionId}/test-connection
POST /api/v1/integrations/{connectionId}/dry-run
GET  /api/v1/integrations/{connectionId}/health
GET  /api/v1/integrations/{connectionId}/diagnostics
```

## Bindings

```http
GET  /api/v1/integrations/{connectionId}/capability-bindings
POST /api/v1/integrations/{connectionId}/capability-bindings
GET  /api/v1/integrations/{connectionId}/source-bindings
POST /api/v1/integrations/{connectionId}/source-bindings
GET  /api/v1/integrations/{connectionId}/trigger-bindings
POST /api/v1/integrations/{connectionId}/trigger-bindings
```

## Webhooks and Sync

```http
GET  /api/v1/integrations/{connectionId}/webhooks
POST /api/v1/integrations/{connectionId}/webhooks
POST /api/v1/integrations/{connectionId}/webhooks/{subscriptionId}/renew
DELETE /api/v1/integrations/{connectionId}/webhooks/{subscriptionId}

GET  /api/v1/integrations/{connectionId}/sync-jobs
POST /api/v1/integrations/{connectionId}/sync-jobs
POST /api/v1/integrations/{connectionId}/sync-jobs/{jobId}/cancel
POST /api/v1/integrations/{connectionId}/sync-jobs/{jobId}/retry
```

## Usage and Audit

```http
GET /api/v1/integrations/{connectionId}/usage
GET /api/v1/integrations/{connectionId}/request-logs
GET /api/v1/integrations/{connectionId}/audit
```

---

# 42. API Examples

## Create Connection

```json
{
  "definitionKey": "jira-cloud",
  "key": "jira-payments-prod",
  "name": "Jira Payments Production",
  "environment": "PRODUCTION",
  "region": "EU",
  "ownerTeamId": "uuid"
}
```

## Test Connection Response

```json
{
  "status": "HEALTHY",
  "latencyMs": 284,
  "authentication": "VALID",
  "scopes": {
    "required": 3,
    "granted": 3,
    "missing": []
  },
  "checks": [
    {
      "name": "Tenant access",
      "status": "PASSED"
    }
  ]
}
```

---

# 43. Capability Gateway Integration

```text
Skill Runtime
  ↓
Capability Request
  ↓
Capability Gateway
  ↓
Integration Routing
  ↓
Integration Adapter
  ↓
External System
```

Gateway отвечает за:

- authorization;
- Control evaluation;
- routing;
- idempotency;
- audit;
- masking;
- retries;
- response normalization.

---

# 44. Context Broker Integration

```text
Knowledge Space
  ↓
Source Binding
  ↓
Integration Connection
  ↓
External Search / Fetch
  ↓
Normalized Evidence
```

---

# 45. Flow Trigger Integration

```text
External Webhook
  ↓
Signature Validation
  ↓
Event Normalization
  ↓
Trigger Binding
  ↓
Flow Resolution
  ↓
Execution Creation
```

---

# 46. Controls Integration

Controls могут:

- запретить connector type;
- требовать OAuth;
- ограничить scopes;
- запретить write;
- потребовать EU region;
- запретить basic auth;
- потребовать mTLS;
- ограничить retention;
- требовать health threshold;
- запретить DEGRADED connection.

---

# 47. Runtime Profiles Integration

Runtime Profile задаёт allowed capabilities.

Integration не может обойти capability allowlist.

Network policy может разрешать только Capability Gateway, а не прямой endpoint.

---

# 48. Executions Integration

Execution хранит:

- selected connection;
- config version;
- capability binding;
- request correlation;
- provider request IDs;
- integration errors;
- normalized result.

---

# 49. Audit Integration

Аудировать:

- connection created;
- auth initiated;
- auth completed;
- scopes changed;
- credential rotated;
- config activated;
- connection tested;
- capability executed;
- webhook received;
- sync started;
- sync failed;
- connection disabled;
- connection archived.

---

# 50. Temporal Integration

Activities:

```text
ResolveIntegrationConnectionActivity
ExecuteIntegrationCapabilityActivity
TestIntegrationConnectionActivity
RunIntegrationSyncActivity
RenewWebhookActivity
RotateCredentialReferenceActivity
```

Retry and timeout должны быть activity-specific.

---

# 51. Kafka Events

Topic:

```text
integration-events
```

Events:

```text
integration.created
integration.version.created
integration.version.activated
integration.connected
integration.disconnected
integration.health.changed
integration.authentication.required
integration.scope.changed
integration.capability.executed
integration.webhook.received
integration.webhook.failed
integration.sync.started
integration.sync.completed
integration.sync.failed
integration.credential.rotated
```

---

# 52. RBAC

Permissions:

```text
integration.read
integration.create
integration.edit
integration.activate
integration.disable
integration.archive
integration.connect
integration.disconnect
integration.test
integration.diagnostics.read
integration.credentials.manage
integration.scopes.manage
integration.capabilities.bind
integration.sources.bind
integration.triggers.bind
integration.webhooks.manage
integration.sync.manage
integration.audit.read
```

---

# 53. Backend Architecture

```text
modules/integrations/
├── domain/
│   ├── IntegrationDefinition
│   ├── IntegrationConnection
│   ├── IntegrationConnectionVersion
│   ├── CapabilityBinding
│   ├── SourceBinding
│   ├── TriggerBinding
│   ├── WebhookSubscription
│   └── SyncJob
├── application/
│   ├── CreateIntegration
│   ├── ValidateIntegration
│   ├── ActivateIntegration
│   ├── TestConnection
│   ├── ExecuteCapability
│   ├── RunSync
│   └── ProcessWebhook
├── infrastructure/
│   ├── IntegrationRepository
│   ├── AdapterRegistry
│   ├── SecretResolver
│   ├── OAuthClient
│   └── WebhookGateway
├── api/
└── tests/
```

Services:

```text
IntegrationDefinitionRegistry
IntegrationConnectionResolver
IntegrationAdapterFactory
IntegrationHealthService
IntegrationScopeValidator
IntegrationRoutingService
IntegrationSyncService
IntegrationWebhookService
IntegrationDiagnosticsService
```

---

# 54. Frontend Architecture

```text
pages/integrations/
├── IntegrationsCatalogPage
├── IntegrationDetailPage
├── IntegrationSetupWizardPage
├── IntegrationDiagnosticsPage
└── IntegrationSyncPage

features/integrations/
├── create-integration
├── connect-integration
├── test-integration
├── rotate-credentials
├── bind-capability
├── configure-source
├── configure-trigger
└── run-sync
```

Components:

```text
IntegrationCard
ConnectorBadge
HealthBadge
AuthBadge
ScopeList
CapabilityBindingTable
SourceBindingTable
TriggerBindingTable
WebhookTable
SyncJobTable
HealthPanel
DiagnosticsConsole
SetupWizard
DryRunPanel
```

---

# 55. NFR

- catalog p95 < 500 ms;
- routing p95 < 100 ms;
- health p95 < 2 s;
- test connection p95 < 10 s;
- webhook acceptance p95 < 300 ms;
- minimum 10 000 connections;
- minimum 10 млн capability calls/day;
- idempotent webhook processing;
- secret isolation;
- TLS 1.2+;
- mTLS support;
- request/response size limits;
- rate limiting;
- circuit breakers;
- masking;
- full trace correlation;
- configurable retention.

---

# 56. Testing

## Unit

- routing;
- scope validation;
- mapping;
- deduplication;
- retry;
- circuit breaker;
- health status;
- credential references;
- environment isolation.

## Integration

- OAuth;
- test connection;
- capability call;
- webhook;
- sync;
- retry;
- health;
- audit;
- snapshot.

## UI

- catalog;
- setup wizard;
- auth flow;
- scope warnings;
- bindings;
- health;
- diagnostics;
- sync jobs.

## E2E

```text
Create Jira Integration
→ Complete OAuth
→ Validate scopes
→ Test connection
→ Bind work_item.read
→ Bind Jira source to Knowledge Space
→ Create Jira webhook trigger
→ Activate
→ Receive issue-created event
→ Start Flow
→ Read issue via Capability Gateway
→ Inspect Execution and Audit
```

---

# 57. Migration

1. Найти существующие connectors и hardcoded clients.
2. Создать inventory external systems.
3. Разделить Integration и Capability.
4. Ввести IntegrationDefinition и IntegrationConnection.
5. Добавить routes:
   - `/integrations`;
   - `/integrations/new`;
   - `/integrations/:id`;
   - `/integrations/:id/diagnostics`;
   - `/integrations/:id/sync`.
6. Перенести credentials в Secret Manager.
7. Ввести Adapter Registry.
8. Подключить Capability Gateway.
9. Подключить Context Broker.
10. Подключить Trigger Gateway.
11. Добавить health and diagnostics.

---

# 58. Pull Request Sequence

## PR-1

- catalog;
- detail shell;
- connector definitions;
- API types.

## PR-2

- DB schema;
- CRUD;
- versioning;
- secret references.

## PR-3

- setup wizard;
- auth;
- test connection;
- scopes.

## PR-4

- capability bindings;
- routing;
- dry run.

## PR-5

- source bindings;
- sync;
- webhooks;
- triggers.

## PR-6

- diagnostics;
- health;
- Audit/Kafka;
- migration of hardcoded clients.

---

# 59. Vertical Slice

```text
Jira Payments Integration
  ↓
OAuth connected
  ↓
Scopes validated
  ↓
Capability work_item.read bound
  ↓
Knowledge Space source bound
  ↓
Webhook trigger created
  ↓
Issue PAY-123 created
  ↓
Event normalized
  ↓
Feature Delivery Flow started
  ↓
Execution reads Jira issue through Capability Gateway
  ↓
Audit and diagnostics available
```

---

# 60. Definition of Done

Раздел завершён, если:

- connector definitions работают;
- connection создаётся;
- auth работает;
- secret values не хранятся в DB;
- scopes валидируются;
- test connection работает;
- versioning работает;
- active config immutable;
- capability binding работает;
- routing объясним;
- Knowledge Space source binding работает;
- webhook работает;
- deduplication работает;
- sync работает;
- health and diagnostics работают;
- Controls применяются;
- Execution snapshot фиксирует version;
- RBAC работает;
- Audit/Kafka работают;
- tests проходят;
- production hardcoded clients мигрированы.

---

# 61. Первое задание coding-агенту

1. Просканируй репозиторий.
2. Найди external API clients, connectors и credentials.
3. Создай `docs/integrations/CURRENT_STATE.md`.
4. Составь inventory integrations и capabilities.
5. Создай schema `integration_definitions`, `integration_connections`, `integration_connection_versions`.
6. Реализуй read-only catalog API.
7. Подключи UI к API.
8. Добавь Integration Detail shell.
9. Добавь Adapter Registry skeleton.
10. Добавь secret reference validation.
11. Добавь tests.
12. Обнови `docs/IMPLEMENTATION_STATUS.md`.
13. Не мигрируй production credentials до прохождения connection/version tests.

---

# 62. Итоговая модель

```text
External System
  ↓
Integration Definition
  ↓
Integration Connection
  ├── Authentication
  ├── Scopes
  ├── Configuration
  ├── Mappings
  ├── Rate Limits
  ├── Webhooks
  ├── Sync
  └── Health
        ↓
Capability Gateway / Context Broker / Trigger Gateway
        ↓
Governed Execution
```

Конец документа.
