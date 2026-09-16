# KNOWLEDGE_SPACES_SYSTEM_REQUIREMENTS.md
## Governed AI Delivery Platform
### Полное системное ТЗ на реализацию раздела Knowledge Spaces

---

# 0. Простое объяснение назначения

Knowledge Space — это не база знаний и не ещё один каталог документов.

Knowledge Space — это управляемая область контекста, которая отвечает на вопрос:

> Где AI-платформа должна искать информацию для конкретного домена, команды, продукта или процесса?

Пример:

```text
Knowledge Space: Payments

Источники:
- Jira project PAY
- Confluence space PAY
- Slack channels #payments-dev и #payments-ops
- Git repositories payment-api и payment-core
- API Catalog: Payments
- Architecture repository: Payments domain
```

Skill не должен знать:

- в каком Jira проекте искать;
- какой Slack-канал читать;
- какой Confluence space использовать;
- в каком Git-репозитории лежит код.

Skill запрашивает:

```text
context.search
```

Платформа использует Knowledge Space, чтобы определить:

- разрешённые источники;
- область поиска;
- приоритет источников;
- правила доступа;
- freshness;
- ranking;
- ограничения по классификации данных.

Таким образом:

```text
Skill
  ↓
Context Broker
  ↓
Knowledge Space
  ↓
Source Bindings
  ↓
Jira / Confluence / Slack / Git / API Catalog
```

Knowledge Space нужен, чтобы Skills оставались универсальными и не зависели от конкретной инфраструктуры компании.

---

# 1. Когда Knowledge Space полезен

## 1.1. Один Skill используется в разных доменах

Один и тот же Skill:

```text
Generate System Requirements
```

может работать для:

```text
Payments
Lending
Cards
Identity
CRM
```

Для каждого домена меняются источники, но Skill остаётся тем же.

## 1.2. Один и тот же источник содержит разные области

Например, в Confluence есть сотни spaces.

Knowledge Space ограничивает поиск:

```text
Payments → PAY, PAY-ARCH, PAY-OPS
```

## 1.3. Требуется контролировать доступ

Knowledge Space может запретить:

- restricted sources;
- персональные данные;
- production logs;
- закрытые Slack channels;
- репозитории другой команды.

## 1.4. Нужен воспроизводимый контекст

Execution Snapshot должен фиксировать:

- какой Knowledge Space применялся;
- какие source bindings были активны;
- какие версии индексов использовались;
- какие документы попали в Evidence.

---

# 2. Возможно более понятное название

В UI можно оставить техническое имя `Knowledge Spaces`, но добавить пояснение:

```text
Knowledge Spaces
Controlled context sources for AI execution
```

Альтернативные названия:

```text
Context Spaces
Knowledge Domains
Context Domains
Information Spaces
```

Рекомендуемый вариант для бизнеса:

```text
Knowledge Spaces
```

Рекомендуемый subtitle:

```text
Define where AI can search for trusted context.
```

---

# 3. Границы ответственности

Knowledge Space отвечает за:

- grouping источников;
- source scope;
- ranking;
- freshness;
- access policy;
- search policy;
- indexing;
- health;
- source priorities;
- data classification;
- Evidence generation.

Knowledge Space не отвечает за:

- логику Playbook;
- prompt Skill;
- Controls;
- Runtime Profile;
- публикацию;
- Human Approval;
- хранение финального Artifact.

---

# 4. Основная модель

```text
Knowledge Space
  ├── Metadata
  ├── Access Policy
  ├── Search Policy
  ├── Ranking Policy
  ├── Freshness Policy
  ├── Source Bindings
  │     ├── Jira
  │     ├── Confluence
  │     ├── Slack
  │     ├── Git
  │     ├── API Catalog
  │     └── File Storage
  ├── Indexes
  ├── Health Status
  └── Usage
```

---

# 5. Типы Knowledge Spaces

Поддержать:

```text
DOMAIN
PRODUCT
TEAM
PROJECT
SYSTEM
REGULATORY
TEMPORARY
```

Примеры:

```text
DOMAIN: Payments
PRODUCT: Mobile Banking
TEAM: Payments Platform Team
SYSTEM: Payment Gateway
REGULATORY: PCI DSS
TEMPORARY: PAY-123 Investigation
```

---

# 6. Source Bindings

Source Binding связывает Knowledge Space с конкретным внешним источником.

Пример:

```json
{
  "sourceType": "JIRA",
  "integrationId": "jira-prod",
  "selector": {
    "projectKeys": ["PAY"],
    "issueTypes": ["Epic", "Story", "Bug"]
  },
  "priority": 80,
  "enabled": true
}
```

Поддержать источники:

```text
JIRA
SBERTRACK
CONFLUENCE
SLACK
NOTION
GITHUB
GITLAB
SHAREPOINT
FILE_STORAGE
API_CATALOG
ARCHITECTURE_REPOSITORY
DATABASE_CATALOG
CUSTOM_MCP
```

---

# 7. Разделы UI

# 7.1. Knowledge Spaces Catalog

Назначение — каталог областей контекста.

Отображать:

- name;
- key;
- type;
- source count;
- health;
- classification;
- usage count;
- owner;
- updated at;
- status.

Функции:

- поиск;
- фильтры;
- create;
- duplicate;
- archive;
- test;
- open detail;
- health overview.

API:

```http
GET /api/v1/knowledge-spaces
POST /api/v1/knowledge-spaces
```

---

# 7.2. Knowledge Space Detail

Вкладки:

```text
Overview
Sources
Search Policy
Access
Health
Usage
Executions
Audit
```

## Overview

Показывает:

- purpose;
- type;
- owner;
- source count;
- active bindings;
- health;
- classification;
- search statistics.

## Sources

Показывает Source Bindings.

Функции:

- add source;
- edit selector;
- enable/disable;
- test connection;
- test search;
- set priority;
- set freshness;
- remove draft binding.

## Search Policy

Настройки:

- maximum results;
- hybrid search;
- semantic weight;
- keyword weight;
- recency weight;
- source diversity;
- deduplication;
- language;
- minimum relevance;
- maximum evidence size.

## Access

Настройки:

- allowed roles;
- allowed teams;
- data classification;
- denied sources;
- geographic restrictions;
- purpose restrictions.

## Health

Показывает:

- integration status;
- indexing status;
- last successful sync;
- lag;
- errors;
- stale sources;
- failed permissions.

## Usage

Показывает:

- Flows;
- Playbooks;
- Executions;
- Rules;
- Runtime snapshots.

## Executions

Показывает executions, которые использовали Space.

## Audit

Неизменяемая история.

---

# 7.3. Source Binding Wizard

Шаги:

```text
1. Select source type
2. Select integration
3. Configure selector
4. Configure access
5. Configure indexing
6. Test search
7. Save
```

Для Jira:

```text
project keys
issue types
labels
components
status filters
date range
```

Для Confluence:

```text
space keys
labels
ancestor pages
excluded pages
```

Для Slack:

```text
channels
thread policy
date window
bot permissions
```

Для Git:

```text
repositories
branches
paths
file types
excluded paths
```

---

# 7.4. Search Playground

Пользователь вводит запрос и видит:

- normalized query;
- выбранные sources;
- search strategy;
- raw results;
- ranked results;
- deduplicated results;
- Evidence Bundle;
- relevance score;
- freshness score;
- access filtering;
- excluded documents.

API:

```http
POST /api/v1/knowledge-spaces/{spaceId}/search
POST /api/v1/knowledge-spaces/{spaceId}/search/explain
```

---

# 8. Context Broker

Context Broker — backend-компонент, который использует Knowledge Space.

Responsibilities:

- принять information need;
- определить search intent;
- выбрать bindings;
- вызвать capabilities;
- нормализовать результаты;
- дедуплицировать;
- ранжировать;
- применять access policy;
- сформировать Evidence Bundle;
- записать Evidence Ledger.

---

# 9. Information Need

Skill не передаёт сырой vendor-specific запрос.

Skill формирует абстрактную потребность:

```json
{
  "type": "ARCHITECTURE_CONTEXT",
  "query": "Как реализована отмена платежа",
  "entities": ["payment", "cancellation"],
  "timeSensitivity": "CURRENT",
  "requiredEvidenceTypes": [
    "ARCHITECTURE_DOCUMENT",
    "SOURCE_CODE",
    "WORK_ITEM"
  ],
  "maxResults": 20
}
```

---

# 10. Search Pipeline

```text
Information Need
  ↓
Query Normalization
  ↓
Source Selection
  ↓
Policy Check
  ↓
Parallel Search
  ↓
Normalization
  ↓
Deduplication
  ↓
Ranking
  ↓
Freshness Check
  ↓
Evidence Extraction
  ↓
Evidence Bundle
```

Алгоритм:

1. Проверить Knowledge Space.
2. Проверить actor и Execution permissions.
3. Определить подходящие bindings.
4. Исключить unhealthy и forbidden bindings.
5. Нормализовать query.
6. Выполнить поиск параллельно.
7. Привести результаты к общей модели.
8. Удалить дубликаты по canonical URI и content hash.
9. Рассчитать relevance.
10. Рассчитать freshness.
11. Применить source priority.
12. Применить diversity.
13. Отфильтровать по classification.
14. Извлечь evidence snippets.
15. Сохранить Evidence.
16. Вернуть Evidence Bundle.

---

# 11. Ranking

Итоговый score:

```text
final_score =
  semantic_score * semantic_weight
  + keyword_score * keyword_weight
  + freshness_score * freshness_weight
  + source_priority_score
  + authority_score
  - duplication_penalty
```

Рекомендуемые defaults:

```text
semantic_weight = 0.45
keyword_weight = 0.20
freshness_weight = 0.15
source_priority = 0.10
authority = 0.10
```

---

# 12. Freshness Policy

Поддержать:

```text
REAL_TIME
HOURLY
DAILY
WEEKLY
ON_DEMAND
STATIC
```

Также:

```json
{
  "maxAgeHours": 24,
  "staleBehavior": "WARN",
  "preferRecent": true
}
```

Stale behavior:

```text
ALLOW
WARN
REJECT
REFRESH
```

---

# 13. Access Policy

Пример:

```json
{
  "allowedRoles": ["ProcessDesigner", "Operator"],
  "allowedTeams": ["payments"],
  "maximumClassification": "CONFIDENTIAL",
  "deniedTags": ["pii", "secrets"],
  "allowedPurposes": [
    "REQUIREMENTS_ANALYSIS",
    "CODE_REVIEW"
  ],
  "regions": ["EU"]
}
```

Проверка доступа выполняется:

- при preview;
- перед каждым search;
- перед document read;
- перед Evidence persistence;
- перед отображением Evidence в UI.

---

# 14. Evidence Bundle

```json
{
  "bundleId": "uuid",
  "knowledgeSpaceId": "uuid",
  "query": "payment cancellation architecture",
  "items": [
    {
      "evidenceId": "uuid",
      "sourceType": "CONFLUENCE",
      "sourceReference": "PAY-ARCH-102",
      "title": "Payment Cancellation Architecture",
      "excerpt": "...",
      "relevanceScore": 0.93,
      "freshnessScore": 0.82,
      "classification": "INTERNAL",
      "retrievedAt": "2026-07-17T10:00:00Z"
    }
  ],
  "excludedCount": 4,
  "checksum": "sha256"
}
```

---

# 15. Жизненный цикл

Knowledge Space:

```text
DRAFT
VALIDATING
ACTIVE
DEGRADED
DISABLED
ARCHIVED
```

Source Binding:

```text
DRAFT
TESTING
ACTIVE
DEGRADED
DISABLED
ERROR
```

---

# 16. Модель данных

## KnowledgeSpace

```text
KnowledgeSpace
- id UUID PK
- workspace_id UUID FK
- key VARCHAR
- name VARCHAR
- description TEXT
- type VARCHAR
- status VARCHAR
- owner_team_id UUID NULL
- classification VARCHAR
- access_policy_json JSONB
- search_policy_json JSONB
- ranking_policy_json JSONB
- freshness_policy_json JSONB
- created_by UUID
- created_at TIMESTAMP
- updated_at TIMESTAMP
- archived_at TIMESTAMP NULL
```

Constraint:

```text
UNIQUE(workspace_id, key)
```

## KnowledgeSourceBinding

```text
KnowledgeSourceBinding
- id UUID PK
- knowledge_space_id UUID FK
- integration_id UUID FK
- source_type VARCHAR
- name VARCHAR
- selector_json JSONB
- priority INTEGER
- access_policy_json JSONB
- indexing_policy_json JSONB
- freshness_policy_json JSONB
- status VARCHAR
- enabled BOOLEAN
- created_at TIMESTAMP
- updated_at TIMESTAMP
```

## KnowledgeIndex

```text
KnowledgeIndex
- id UUID PK
- source_binding_id UUID FK
- index_type VARCHAR
- provider VARCHAR
- index_reference VARCHAR
- status VARCHAR
- document_count BIGINT
- last_indexed_at TIMESTAMP NULL
- lag_seconds BIGINT NULL
- metadata_json JSONB
```

## KnowledgeDocument

Опциональная нормализованная metadata-модель:

```text
KnowledgeDocument
- id UUID PK
- source_binding_id UUID FK
- external_id VARCHAR
- canonical_uri TEXT
- title TEXT
- classification VARCHAR
- content_hash VARCHAR
- metadata_json JSONB
- source_updated_at TIMESTAMP NULL
- indexed_at TIMESTAMP
```

Полный контент необязательно хранить в платформе.

## SearchRequest

```text
SearchRequest
- id UUID PK
- execution_id UUID NULL
- knowledge_space_id UUID FK
- actor_id UUID
- information_need_json JSONB
- status VARCHAR
- started_at TIMESTAMP
- completed_at TIMESTAMP NULL
```

## SearchResult

```text
SearchResult
- id UUID PK
- search_request_id UUID FK
- source_binding_id UUID FK
- external_reference VARCHAR
- canonical_uri TEXT
- title TEXT
- excerpt TEXT
- raw_score NUMERIC
- relevance_score NUMERIC
- freshness_score NUMERIC
- final_score NUMERIC
- classification VARCHAR
- excluded_reason VARCHAR NULL
- metadata_json JSONB
```

## Evidence

```text
Evidence
- id UUID PK
- execution_id UUID FK
- search_request_id UUID FK
- knowledge_space_id UUID FK
- source_binding_id UUID FK
- source_type VARCHAR
- source_reference VARCHAR
- canonical_uri TEXT
- title TEXT
- excerpt TEXT
- content_hash VARCHAR
- relevance_score NUMERIC
- freshness_score NUMERIC
- classification VARCHAR
- metadata_json JSONB
- retrieved_at TIMESTAMP
```

## KnowledgeSpaceHealthCheck

```text
KnowledgeSpaceHealthCheck
- id UUID PK
- knowledge_space_id UUID FK
- source_binding_id UUID NULL
- status VARCHAR
- check_type VARCHAR
- result_json JSONB
- checked_at TIMESTAMP
```

---

# 17. REST API

## Knowledge Spaces

```http
GET    /api/v1/knowledge-spaces
POST   /api/v1/knowledge-spaces
GET    /api/v1/knowledge-spaces/{spaceId}
PATCH  /api/v1/knowledge-spaces/{spaceId}
DELETE /api/v1/knowledge-spaces/{spaceId}
POST   /api/v1/knowledge-spaces/{spaceId}/archive
POST   /api/v1/knowledge-spaces/{spaceId}/activate
POST   /api/v1/knowledge-spaces/{spaceId}/disable
POST   /api/v1/knowledge-spaces/{spaceId}/duplicate
```

## Sources

```http
GET    /api/v1/knowledge-spaces/{spaceId}/sources
POST   /api/v1/knowledge-spaces/{spaceId}/sources
GET    /api/v1/knowledge-spaces/{spaceId}/sources/{sourceId}
PATCH  /api/v1/knowledge-spaces/{spaceId}/sources/{sourceId}
DELETE /api/v1/knowledge-spaces/{spaceId}/sources/{sourceId}
POST   /api/v1/knowledge-spaces/{spaceId}/sources/{sourceId}/test
POST   /api/v1/knowledge-spaces/{spaceId}/sources/{sourceId}/enable
POST   /api/v1/knowledge-spaces/{spaceId}/sources/{sourceId}/disable
POST   /api/v1/knowledge-spaces/{spaceId}/sources/{sourceId}/reindex
```

## Search

```http
POST /api/v1/knowledge-spaces/{spaceId}/search
POST /api/v1/knowledge-spaces/{spaceId}/search/explain
GET  /api/v1/knowledge-spaces/{spaceId}/search-requests
GET  /api/v1/knowledge-spaces/{spaceId}/search-requests/{requestId}
```

## Health

```http
GET  /api/v1/knowledge-spaces/{spaceId}/health
POST /api/v1/knowledge-spaces/{spaceId}/health/check
GET  /api/v1/knowledge-spaces/{spaceId}/health/history
```

## Usage

```http
GET /api/v1/knowledge-spaces/{spaceId}/usage
GET /api/v1/knowledge-spaces/{spaceId}/executions
GET /api/v1/knowledge-spaces/{spaceId}/audit
```

---

# 18. API examples

## Create Knowledge Space

```json
{
  "key": "payments",
  "name": "Payments",
  "description": "Trusted context for payment domain",
  "type": "DOMAIN",
  "classification": "CONFIDENTIAL",
  "ownerTeamId": "uuid"
}
```

## Add Jira Source

```json
{
  "integrationId": "uuid",
  "sourceType": "JIRA",
  "name": "Payments Jira",
  "selector": {
    "projectKeys": ["PAY"],
    "issueTypes": ["Epic", "Story", "Bug"]
  },
  "priority": 80,
  "freshnessPolicy": {
    "mode": "REAL_TIME",
    "maxAgeHours": 1
  }
}
```

## Search

```json
{
  "informationNeed": {
    "type": "REQUIREMENTS_CONTEXT",
    "query": "payment cancellation restrictions",
    "requiredEvidenceTypes": [
      "WORK_ITEM",
      "ARCHITECTURE_DOCUMENT"
    ],
    "maxResults": 20
  },
  "executionId": "uuid"
}
```

---

# 19. Интеграция с Skills

Skill manifest может объявить:

```yaml
context_requirements:
  required_evidence_types:
    - ARCHITECTURE_DOCUMENT
    - WORK_ITEM
  minimum_evidence_count: 3
  freshness: CURRENT
```

Skill не выбирает конкретные источники.

Skill Runtime обращается к Context Broker.

---

# 20. Интеграция с Playbooks

Playbook может задавать:

- required Knowledge Space type;
- default Knowledge Space;
- minimum evidence requirements;
- evidence checkpoint;
- behavior when context is insufficient.

Пример:

```yaml
context_policy:
  required_space_type: DOMAIN
  minimum_evidence_count: 5
  insufficient_context_behavior: HUMAN_CHECKPOINT
```

---

# 21. Интеграция с Flows

Flow может:

- выбрать Knowledge Space по routing;
- переключать Space между stages;
- использовать основной Space и дополнительные;
- создать temporary Space для investigation.

---

# 22. Интеграция с Controls

Controls могут:

- запретить определённые sources;
- ограничить classification;
- потребовать authoritative source;
- потребовать minimum evidence;
- ограничить region;
- запретить stale context;
- требовать Evidence retention.

Controls всегда имеют приоритет над Search Policy.

---

# 23. Execution Snapshot

Snapshot должен содержать:

```json
{
  "knowledgeSpace": {
    "id": "uuid",
    "sourceBindings": [
      {
        "id": "uuid",
        "integrationId": "uuid",
        "selectorHash": "sha256",
        "status": "ACTIVE"
      }
    ],
    "searchPolicy": {},
    "rankingPolicy": {},
    "accessPolicy": {},
    "checksum": "sha256"
  }
}
```

Execution не должен автоматически использовать новые bindings, добавленные после старта.

---

# 24. Capability Gateway

Context Broker не вызывает Jira или Confluence напрямую.

Он использует:

```text
context.search
context.read
repository.search
repository.read
work_item.search
work_item.read
```

Capability Gateway выбирает конкретный provider.

---

# 25. Backend architecture

```text
modules/knowledge-spaces/
├── domain/
│   ├── KnowledgeSpace
│   ├── SourceBinding
│   ├── SearchPolicy
│   ├── RankingPolicy
│   ├── AccessPolicy
│   └── EvidenceBundle
├── application/
│   ├── CreateKnowledgeSpace
│   ├── AddSourceBinding
│   ├── SearchKnowledgeSpace
│   ├── ExplainSearch
│   ├── RunHealthCheck
│   └── BuildEvidenceBundle
├── infrastructure/
│   ├── Repositories
│   ├── IndexProviders
│   └── CapabilityClients
├── api/
└── tests/
```

Основные сервисы:

```text
ContextBroker
SourceSelector
QueryNormalizer
ResultNormalizer
Deduplicator
RankingEngine
FreshnessEvaluator
AccessPolicyEvaluator
EvidenceExtractor
KnowledgeHealthService
```

---

# 26. Frontend architecture

```text
pages/knowledge-spaces/
├── KnowledgeSpacesCatalogPage
├── KnowledgeSpaceDetailPage
├── SourceBindingWizardPage
└── SearchPlaygroundPage

features/knowledge-spaces/
├── create-space
├── add-source
├── test-source
├── search-preview
├── health-check
└── reindex-source
```

Reusable components:

```text
KnowledgeSpaceCard
SourceBindingTable
SourceTypeBadge
HealthBadge
SearchPolicyForm
AccessPolicyEditor
SourceSelectorBuilder
SearchResultList
RankingExplanation
EvidenceBundlePreview
HealthTimeline
```

---

# 27. RBAC

Permissions:

```text
knowledge_space.read
knowledge_space.create
knowledge_space.edit
knowledge_space.archive
knowledge_space.search
knowledge_space.search_explain
knowledge_source.add
knowledge_source.edit
knowledge_source.test
knowledge_source.reindex
knowledge_health.read
knowledge_audit.read
```

---

# 28. Audit Events

```text
knowledge_space.created
knowledge_space.updated
knowledge_space.activated
knowledge_space.disabled
knowledge_space.archived
knowledge_source.added
knowledge_source.updated
knowledge_source.tested
knowledge_source.enabled
knowledge_source.disabled
knowledge_source.reindexed
knowledge_search.started
knowledge_search.completed
knowledge_search.denied
knowledge_evidence.created
knowledge_health.degraded
```

---

# 29. Kafka Events

Topic:

```text
knowledge-space-events
```

Отдельно search telemetry может публиковаться в:

```text
context-search-events
```

---

# 30. Нефункциональные требования

- catalog API p95 < 500 ms;
- cached search p95 < 1 s;
- federated search p95 < 5 s;
- health page p95 < 1 s;
- минимум 1000 spaces;
- до 100 bindings на Space;
- до 1 млн indexed metadata records;
- parallel source search;
- circuit breakers;
- per-source timeout;
- partial result support;
- XSS-safe excerpts;
- classification enforcement;
- full tracing.

---

# 31. Поведение при ошибках

Если один source недоступен:

- не падать целиком;
- отметить partial result;
- продолжить по другим sources;
- записать degraded health;
- показать предупреждение.

Если все sources недоступны:

- вернуть `CONTEXT_UNAVAILABLE`;
- применить Playbook policy;
- либо Human Checkpoint;
- либо fail execution.

Если evidence недостаточно:

```text
CONTINUE_WITH_WARNING
ASK_HUMAN
RETRY_SEARCH
FAIL_STEP
```

---

# 32. Тестирование

## Unit

- source selection;
- scope filters;
- ranking;
- freshness;
- deduplication;
- access policies;
- classification;
- bundle checksum.

## Integration

- source add/test;
- federated search;
- partial failure;
- Evidence persistence;
- snapshot;
- audit;
- RBAC.

## UI

- catalog;
- source wizard;
- policy editing;
- health;
- search playground;
- result explanation.

## E2E

```text
Create Payments Space
→ Add Jira
→ Add Confluence
→ Add Git
→ Test sources
→ Run search
→ Generate Evidence Bundle
→ Start Playbook
→ Freeze Space Snapshot
→ Use Evidence in Skill
→ Inspect Evidence Ledger
```

---

# 33. Миграция текущего прототипа

1. Найти текущую страницу Knowledge Spaces.
2. Проверить, не является ли она просто списком connectors.
3. Сохранить визуальные компоненты.
4. Ввести сущности KnowledgeSpace и SourceBinding.
5. Добавить реальные routes:
   - `/knowledge-spaces`;
   - `/knowledge-spaces/:id`;
   - `/knowledge-spaces/:id/sources/new`;
   - `/knowledge-spaces/:id/playground`.
6. Подключить API.
7. Удалить production mocks.
8. Добавить Context Broker.
9. Интегрировать Capability Gateway.
10. Интегрировать Execution Snapshot.

---

# 34. Последовательность Pull Requests

## PR-1

- catalog;
- detail shell;
- navigation;
- API types.

## PR-2

- DB schema;
- CRUD;
- source bindings.

## PR-3

- source wizard;
- integration test;
- health.

## PR-4

- search playground;
- Context Broker;
- normalization.

## PR-5

- ranking;
- deduplication;
- Evidence Bundle.

## PR-6

- Playbook/Skill integration;
- Snapshot;
- Audit/Kafka.

---

# 35. Vertical Slice

```text
Knowledge Space: Payments
  ├── Jira PAY
  ├── Confluence PAY
  └── Git payment-api

System Requirements Playbook
  ↓
Skill requests architecture context
  ↓
Context Broker selects Payments Space
  ↓
Searches 3 sources
  ↓
Ranks and deduplicates
  ↓
Creates Evidence Bundle
  ↓
Skill generates requirements
  ↓
Execution Inspector shows evidence
```

---

# 36. Definition of Done

Раздел завершён, если:

- Space создаётся;
- source bindings добавляются;
- selectors работают;
- source test работает;
- health отображается;
- search playground работает;
- federated search работает;
- partial failures поддерживаются;
- access policy применяется;
- ranking объясним;
- Evidence Bundle создаётся;
- snapshot фиксируется;
- Skill получает evidence через Context Broker;
- нет прямых vendor calls из Skill;
- Audit и Kafka работают;
- tests проходят;
- UI не использует production mocks.

---

# 37. Первое задание coding-агенту

1. Просканируй репозиторий.
2. Найди текущий раздел Knowledge Spaces.
3. Создай `docs/knowledge-spaces/CURRENT_STATE.md`.
4. Опиши, чем текущая реализация отличается от этого ТЗ.
5. Создай schema для `knowledge_spaces` и `knowledge_source_bindings`.
6. Реализуй read-only catalog API.
7. Подключи существующий UI к API.
8. Добавь detail page shell.
9. Добавь tests.
10. Обнови `docs/IMPLEMENTATION_STATUS.md`.
11. Не реализуй federated search до прохождения CRUD tests.

---

# 38. Итоговая модель

```text
Knowledge Space
  ├── Source Bindings
  ├── Search Policy
  ├── Ranking Policy
  ├── Freshness Policy
  ├── Access Policy
  └── Health

Skill
  ↓
Context Broker
  ↓
Knowledge Space
  ↓
Capability Gateway
  ↓
External Sources
  ↓
Evidence Bundle
  ↓
Execution Snapshot
```

Конец документа.
