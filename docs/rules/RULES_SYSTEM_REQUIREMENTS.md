# RULES_SYSTEM_REQUIREMENTS.md
## Governed AI Delivery Platform
### Полное системное ТЗ на реализацию раздела Rules

---

# 0. Назначение документа

Этот документ является техническим заданием для coding-агента, который должен реализовать раздел **Rules** в существующем прототипе платформы.

Нельзя создавать отдельный продукт с нуля. Необходимо:

1. проанализировать существующий репозиторий;
2. найти текущие страницы Rules и связанные модели;
3. сохранить визуальный стиль прототипа;
4. заменить mock-данные реальными API;
5. внедрить versioning, scope resolution, conflict detection и audit;
6. интегрировать Rules с Playbooks, Skills, Flows, Knowledge Spaces и Executions.

Раздел Rules отвечает за изменяемые инструкции и соглашения, которые уточняют поведение Skills, но не меняют обязательный процесс и не могут ослаблять Controls.

---

# 1. Концепция Rules

Rule — это версионируемая инструкция, применяемая в определённом scope и передаваемая Skill Runtime как часть контекста исполнения.

Примеры:

- стиль системных требований;
- терминология платёжного домена;
- формат тест-кейсов;
- Java coding conventions;
- правила именования API;
- структура архитектурного решения;
- требования к детализации;
- правила оформления Jira-описаний.

Rule не является:

- Playbook;
- Skill;
- Control;
- Prompt целиком;
- MCP tool;
- Knowledge Source;
- Runtime Profile.

Главная формула:

```text
Execution Context
  + Effective Rules
  + Applicable Controls
  + Evidence
  + Artifact Snapshot
  = Skill Run Context
```

---

# 2. Границы ответственности

## 2.1. Rules могут

- задавать формат;
- задавать терминологию;
- устанавливать naming conventions;
- уточнять стиль;
- задавать обязательные секции документа;
- определять уровень детализации;
- задавать допустимые шаблоны;
- добавлять доменные инструкции;
- уточнять ожидаемый output.

## 2.2. Rules не могут

- удалять Control Gate;
- отключать Human Checkpoint;
- изменять граф Playbook;
- разрешать запрещённые capabilities;
- расширять доступ к данным;
- менять retention policy;
- менять model restrictions;
- отменять approval;
- публиковать результат;
- напрямую вызывать MCP tools.

---

# 3. Типы Rules

Поддержать категории:

```text
STYLE
TERMINOLOGY
FORMAT
NAMING
DOMAIN
QUALITY
CODING_STANDARD
DOCUMENT_TEMPLATE
OUTPUT_CONSTRAINT
LANGUAGE
```

Допускается расширяемый enum через справочник, но системные категории должны быть предустановлены.

---

# 4. Scope и наследование

Rule применяется в scope.

Поддержать уровни:

```text
PLATFORM
ORGANIZATION
WORKSPACE
DOMAIN
TEAM
KNOWLEDGE_SPACE
FLOW
PLAYBOOK
SKILL_INTERFACE
SKILL
EXECUTION
```

Рекомендуемый приоритет:

```text
PLATFORM = 100
ORGANIZATION = 200
WORKSPACE = 300
DOMAIN = 400
TEAM = 500
KNOWLEDGE_SPACE = 600
FLOW = 700
PLAYBOOK = 800
SKILL_INTERFACE = 850
SKILL = 900
EXECUTION = 1000
```

Более локальный scope имеет больший приоритет.

Rule также содержит ручной `priority` внутри одного уровня.

Итоговая сортировка:

```text
scope_weight ASC
priority ASC
created_at ASC
```

Runtime применяет Rules в этом порядке, чтобы локальные инструкции могли уточнять глобальные.

---

# 5. Стратегии конфликтов

Поддержать:

```text
MERGE
OVERRIDE
APPEND
REJECT_ON_CONFLICT
```

## MERGE

Используется для совместимых инструкций.

## OVERRIDE

Локальная Rule заменяет одноимённую глобальную Rule.

Требуется `conflict_key`.

## APPEND

Контент добавляется без попытки объединения.

## REJECT_ON_CONFLICT

Execution или публикация Playbook должна быть остановлена, если обнаружено несовместимое правило.

---

# 6. Жизненный цикл Rule

```text
DRAFT
VALIDATING
READY
PUBLISHED
DEPRECATED
ARCHIVED
```

Требования:

- опубликованную версию нельзя менять in-place;
- изменения создают новую версию;
- draft может редактироваться;
- archived Rule не участвует в resolution;
- deprecated Rule может участвовать только в уже замороженных Execution Snapshot;
- удаление опубликованной Rule запрещено;
- допустима архивация логической сущности.

---

# 7. Разделы UI

# 7.1. Rules Catalog

Назначение — каталог всех Rules.

Отображать:

- name;
- key;
- category;
- scope;
- scope target;
- current version;
- status;
- priority;
- conflict strategy;
- usage count;
- owner;
- updated at.

Функции:

- поиск;
- фильтр по category;
- фильтр по scope;
- фильтр по status;
- фильтр по owner;
- сортировка;
- create;
- duplicate;
- archive;
- compare versions;
- open details;
- bulk export.

API:

```http
GET /api/v1/rules
POST /api/v1/rules
```

Query parameters:

```text
search
category
scopeType
scopeTargetId
status
ownerId
limit
cursor
sort
```

---

# 7.2. Rule Detail

Вкладки:

```text
Overview
Content
Scope
Usage
Versions
Validation
Audit
```

## Overview

Показывает:

- metadata;
- category;
- scope;
- conflict key;
- strategy;
- owner;
- latest version;
- publication status;
- usage summary.

## Content

Редактор Markdown с preview.

## Scope

Конструктор scope selector:

```json
{
  "scopeType": "PLAYBOOK",
  "selector": {
    "playbookIds": ["..."],
    "families": ["ANALYSIS"],
    "tags": ["payments"]
  }
}
```

## Usage

Показывает:

- Playbooks;
- Flows;
- Skills;
- Knowledge Spaces;
- Executions;
- Runtime snapshots.

## Versions

- history;
- compare;
- clone;
- publish;
- deprecate;
- rollback by creating new version.

## Validation

- syntax;
- metadata;
- conflicts;
- forbidden instructions;
- unresolved placeholders;
- compatibility.

## Audit

Неизменяемая история действий.

---

# 7.3. Rule Editor

Полноэкранный редактор.

Области:

```text
File/Metadata panel
Markdown Editor
Rendered Preview
Inspector
Problems panel
Effective Rules Preview
```

Функции:

- autosave draft;
- syntax highlighting;
- preview;
- validation;
- placeholders;
- variable autocomplete;
- scope preview;
- conflict simulation;
- compare version;
- publish.

---

# 7.4. Effective Rules Preview

Пользователь задаёт контекст:

```text
Workspace
Domain
Team
Knowledge Space
Flow
Playbook
Skill Interface
Skill
Execution overrides
```

Система показывает:

- найденные Rules;
- порядок применения;
- overridden Rules;
- conflicts;
- final merged bundle;
- Controls that constrain Rules;
- explanation trace.

API:

```http
POST /api/v1/rules/resolve
POST /api/v1/rules/resolve/preview
```

---

# 8. Формат Rule

Минимальная структура:

```yaml
key: payments-requirements-style
name: Payments Requirements Style
category: STYLE
scope:
  type: DOMAIN
  selector:
    domainKeys:
      - payments
priority: 50
conflict_strategy: MERGE
conflict_key: requirements.style
language: ru
```

Контент:

```markdown
# Payments Requirements Style

## Mandatory structure

1. Business goal
2. Actors
3. Preconditions
4. Main flow
5. Alternative flows
6. Error cases
7. Non-functional requirements

## Terminology

Use "платёжная операция", not "транзакция", unless referring to database transaction.
```

---

# 9. Variables и placeholders

Поддержать read-only placeholders:

```text
{{workspace.name}}
{{flow.name}}
{{playbook.name}}
{{skill.name}}
{{knowledge_space.name}}
{{execution.source_type}}
{{artifact.type}}
{{locale}}
```

Запрещено:

- выполнение произвольного кода;
- shell expressions;
- сетевые вызовы;
- доступ к секретам;
- динамический SQL.

Resolver должен валидировать доступность переменных до публикации.

---

# 10. Rule Bundle

Runtime получает нормализованный bundle:

```json
{
  "bundleId": "uuid",
  "resolvedAt": "2026-07-17T10:00:00Z",
  "contextHash": "sha256",
  "rules": [
    {
      "ruleId": "uuid",
      "versionId": "uuid",
      "key": "requirements-style",
      "category": "STYLE",
      "scopeType": "PLAYBOOK",
      "priority": 40,
      "content": "...",
      "source": "PUBLISHED"
    }
  ],
  "overrides": [],
  "conflicts": [],
  "checksum": "sha256"
}
```

Bundle сохраняется в Execution Snapshot.

---

# 11. Алгоритм Rule Resolution

1. Получить execution context.
2. Найти опубликованные Rules.
3. Отфильтровать по workspace.
4. Проверить scope selectors.
5. Исключить archived/deprecated для новых Execution.
6. Проверить дату действия.
7. Применить RBAC и data classification.
8. Сгруппировать по `conflict_key`.
9. Отсортировать по scope weight и priority.
10. Применить conflict strategy.
11. Проверить Control constraints.
12. Разрешить placeholders.
13. Сформировать final bundle.
14. Рассчитать checksum.
15. Сохранить trace.
16. Добавить bundle в Execution Snapshot.

Pseudo-code:

```text
candidates = repository.findPublished(context)
matched = candidates.filter(matchesScope)
ordered = sort(matched, scopeWeight, priority, createdAt)
resolved = conflictResolver.apply(ordered)
controlled = controlEngine.validateRules(resolved)
rendered = placeholderEngine.render(controlled, context)
return RuleBundle(rendered)
```

---

# 12. Conflict Detection

Конфликт возникает, если:

- две Rules имеют один `conflict_key`;
- обе используют `REJECT_ON_CONFLICT`;
- одна Rule запрещает действие, другая требует его;
- два шаблона требуют несовместимую структуру;
- Rule пытается нарушить Control;
- локальная Rule пытается расширить capability permissions;
- язык output несовместим с обязательным policy.

Conflict record:

```json
{
  "id": "uuid",
  "severity": "ERROR",
  "conflictKey": "requirements.language",
  "ruleVersionIds": ["...", "..."],
  "reason": "Two mandatory output languages are configured",
  "resolution": null
}
```

---

# 13. Валидация

## 13.1. Structural validation

- key задан;
- name задан;
- category валидна;
- scopeType валиден;
- selector соответствует scopeType;
- priority в допустимом диапазоне;
- strategy валидна;
- content не пустой.

## 13.2. Content validation

- Markdown корректен;
- placeholders известны;
- отсутствуют секреты;
- отсутствуют shell/code injection patterns;
- отсутствуют прямые MCP tool names, если policy запрещает;
- отсутствуют инструкции об обходе Controls;
- нет prompt injection команд типа ignore previous instructions.

## 13.3. Semantic validation

- Rule не меняет процесс;
- Rule не противоречит Control;
- Rule соответствует категории;
- scope не слишком широк для restricted content;
- conflict key корректен.

## 13.4. Publication validation

Публикация запрещена при ERROR.

WARNING требует подтверждения пользователя с правом `rule.publish_with_warnings`.

---

# 14. Модель данных

## Rule

```text
Rule
- id UUID PK
- workspace_id UUID FK
- key VARCHAR
- name VARCHAR
- description TEXT
- category VARCHAR
- owner_team_id UUID NULL
- status VARCHAR
- current_published_version_id UUID NULL
- created_by UUID
- created_at TIMESTAMP
- updated_at TIMESTAMP
- archived_at TIMESTAMP NULL
```

Constraints:

```text
UNIQUE(workspace_id, key)
```

## RuleVersion

```text
RuleVersion
- id UUID PK
- rule_id UUID FK
- semantic_version VARCHAR
- version_number INTEGER
- status VARCHAR
- content_markdown TEXT
- metadata_json JSONB
- scope_type VARCHAR
- scope_selector JSONB
- scope_weight INTEGER
- priority INTEGER
- conflict_strategy VARCHAR
- conflict_key VARCHAR NULL
- language VARCHAR NULL
- valid_from TIMESTAMP NULL
- valid_to TIMESTAMP NULL
- checksum VARCHAR
- created_by UUID
- created_at TIMESTAMP
- published_by UUID NULL
- published_at TIMESTAMP NULL
- deprecated_at TIMESTAMP NULL
```

## RuleDependency

```text
RuleDependency
- id UUID PK
- rule_version_id UUID FK
- dependency_rule_key VARCHAR
- dependency_type VARCHAR
- required_version_range VARCHAR NULL
```

Dependency types:

```text
REQUIRES
EXTENDS
CONFLICTS_WITH
```

## RuleUsage

Материализованный индекс использования:

```text
RuleUsage
- id UUID PK
- rule_version_id UUID FK
- entity_type VARCHAR
- entity_id UUID
- usage_type VARCHAR
- discovered_at TIMESTAMP
```

## RuleValidationRun

```text
RuleValidationRun
- id UUID PK
- rule_version_id UUID FK
- status VARCHAR
- result_json JSONB
- started_at TIMESTAMP
- completed_at TIMESTAMP
```

## RuleResolutionTrace

```text
RuleResolutionTrace
- id UUID PK
- execution_id UUID NULL
- context_json JSONB
- candidate_rule_versions JSONB
- matched_rule_versions JSONB
- excluded_rules JSONB
- conflicts_json JSONB
- final_bundle_json JSONB
- checksum VARCHAR
- created_at TIMESTAMP
```

## RuleBundleSnapshot

```text
RuleBundleSnapshot
- id UUID PK
- execution_id UUID FK
- bundle_json JSONB
- checksum VARCHAR
- created_at TIMESTAMP
```

---

# 15. REST API

## Rules

```http
GET    /api/v1/rules
POST   /api/v1/rules
GET    /api/v1/rules/{ruleId}
PATCH  /api/v1/rules/{ruleId}
DELETE /api/v1/rules/{ruleId}
POST   /api/v1/rules/{ruleId}/archive
POST   /api/v1/rules/{ruleId}/restore
POST   /api/v1/rules/{ruleId}/duplicate
```

## Versions

```http
GET  /api/v1/rules/{ruleId}/versions
POST /api/v1/rules/{ruleId}/versions
GET  /api/v1/rules/{ruleId}/versions/{versionId}
PATCH /api/v1/rules/{ruleId}/versions/{versionId}
POST /api/v1/rules/{ruleId}/versions/{versionId}/validate
POST /api/v1/rules/{ruleId}/versions/{versionId}/publish
POST /api/v1/rules/{ruleId}/versions/{versionId}/deprecate
POST /api/v1/rules/{ruleId}/versions/{versionId}/clone
```

## Resolution

```http
POST /api/v1/rules/resolve
POST /api/v1/rules/resolve/preview
GET  /api/v1/rules/resolution-traces/{traceId}
```

## Usage

```http
GET /api/v1/rules/{ruleId}/usage
GET /api/v1/rules/{ruleId}/versions/{versionId}/usage
```

## Compare and export

```http
GET  /api/v1/rules/{ruleId}/compare?from={versionId}&to={versionId}
GET  /api/v1/rules/export
POST /api/v1/rules/import
```

---

# 16. API examples

## Create Rule

```json
{
  "key": "payments-terminology",
  "name": "Payments Terminology",
  "description": "Corporate terminology for payment domain",
  "category": "TERMINOLOGY",
  "ownerTeamId": "uuid"
}
```

## Create Version

```json
{
  "semanticVersion": "1.0.0",
  "contentMarkdown": "# Terminology\nUse ...",
  "scopeType": "DOMAIN",
  "scopeSelector": {
    "domainKeys": ["payments"]
  },
  "priority": 100,
  "conflictStrategy": "MERGE",
  "conflictKey": "payments.terminology",
  "language": "ru"
}
```

## Resolve

```json
{
  "workspaceId": "uuid",
  "domainKeys": ["payments"],
  "teamId": "uuid",
  "knowledgeSpaceId": "uuid",
  "flowVersionId": "uuid",
  "playbookVersionId": "uuid",
  "skillInterfaceKey": "analysis.system_requirements.generate@1",
  "skillVersionId": "uuid",
  "executionOverrides": []
}
```

---

# 17. Интеграция с Playbooks

Playbook может:

- ссылаться на required Rule categories;
- добавлять Playbook-scoped Rules;
- задавать minimum required rule keys;
- запрещать execution при unresolved conflict.

Playbook Version snapshot должен включать ссылки на Rule requirements, но не копировать mutable draft content.

При старте Execution Rule Resolver фиксирует конкретные Rule Versions.

---

# 18. Интеграция со Skills

Skill manifest может объявлять:

```yaml
rule_requirements:
  required_categories:
    - TERMINOLOGY
    - FORMAT
  optional_categories:
    - STYLE
  supported_languages:
    - ru
    - en
```

Skill не должен самостоятельно искать Rules.

Skill Runtime получает Rule Bundle от платформы.

---

# 19. Интеграция с Controls

Control имеет более высокий приоритет.

Control Engine проверяет Rule Bundle перед использованием.

Примеры:

- Control требует русский язык;
- Rule требует английский язык;
- итог: conflict ERROR.

- Control запрещает публикацию персональных данных;
- Rule требует включить полные ФИО;
- итог: Rule rejected.

---

# 20. Интеграция с Execution Snapshot

Snapshot содержит:

```json
{
  "ruleBundle": {
    "bundleId": "uuid",
    "ruleVersionIds": ["uuid"],
    "checksum": "..."
  }
}
```

Текущий Execution не должен видеть Rules, опубликованные после его старта.

Retry использует тот же bundle, если пользователь явно не создаёт новый Execution.

---

# 21. Backend architecture

```text
modules/rules/
├── domain/
│   ├── Rule.ts
│   ├── RuleVersion.ts
│   ├── Scope.ts
│   ├── Conflict.ts
│   └── RuleBundle.ts
├── application/
│   ├── CreateRuleUseCase.ts
│   ├── CreateRuleVersionUseCase.ts
│   ├── PublishRuleVersionUseCase.ts
│   ├── ResolveRulesUseCase.ts
│   ├── ValidateRuleUseCase.ts
│   └── CompareRuleVersionsUseCase.ts
├── infrastructure/
│   ├── RuleRepository.ts
│   ├── RuleResolutionRepository.ts
│   └── MarkdownSanitizer.ts
├── api/
│   ├── RulesController.ts
│   └── RulesSchemas.ts
└── tests/
```

Компоненты:

```text
RuleRepository
RuleResolver
ScopeMatcher
ConflictResolver
PlaceholderEngine
RuleValidator
RuleBundleBuilder
RuleUsageIndexer
RuleAuditPublisher
```

---

# 22. Frontend architecture

```text
pages/rules/
├── RulesCatalogPage
├── RuleDetailPage
├── RuleEditorPage
└── EffectiveRulesPreviewPage

features/rules/
├── create-rule
├── edit-rule
├── publish-rule
├── validate-rule
├── resolve-rules
├── compare-versions
└── archive-rule

entities/rule/
├── model
├── api
└── ui
```

Обязательные reusable components:

```text
RuleCard
RuleTable
RuleStatusBadge
ScopeBadge
RuleMarkdownEditor
ScopeSelectorBuilder
ConflictStrategySelect
ValidationProblemsPanel
VersionDiffViewer
EffectiveRulesTrace
RuleUsageList
```

---

# 23. RBAC

Permissions:

```text
rule.read
rule.create
rule.edit
rule.validate
rule.publish
rule.publish_with_warnings
rule.archive
rule.resolve_preview
rule.import
rule.export
rule.audit.read
```

Роли:

```text
PlatformAdmin
WorkspaceAdmin
ProcessDesigner
SkillDeveloper
ComplianceOfficer
Viewer
Auditor
```

ComplianceOfficer должен видеть conflicts и Control violations.

---

# 24. Audit Events

```text
rule.created
rule.updated
rule.archived
rule.restored
rule.version.created
rule.version.updated
rule.version.validated
rule.version.published
rule.version.deprecated
rule.resolution.previewed
rule.resolution.completed
rule.conflict.detected
```

---

# 25. Kafka Events

Topic:

```text
rule-events
```

Envelope должен соответствовать общей event schema платформы.

Payload не должен содержать секреты и полный restricted content, если это запрещено policy.

---

# 26. Кэширование

Rule resolution может кэшироваться по ключу:

```text
workspaceId
domainKeys
teamId
knowledgeSpaceId
flowVersionId
playbookVersionId
skillInterfaceKey
skillVersionId
rulesRevision
controlsRevision
```

Cache invalidation:

- публикация Rule Version;
- архивация Rule;
- изменение Control;
- изменение scope binding;
- изменение workspace policy.

---

# 27. Нефункциональные требования

- catalog API p95 < 500 ms;
- resolution p95 < 300 ms при cache hit;
- resolution p95 < 1 s при cache miss;
- preview p95 < 2 s;
- поддержка 100 000 Rules;
- поддержка bundle до 2 MB;
- checksum для каждого bundle;
- immutable published versions;
- autosave draft не реже 5 секунд;
- Markdown preview без XSS;
- все действия трассируются.

---

# 28. Тестирование

## Unit tests

- scope matching;
- sorting;
- conflict strategies;
- placeholder rendering;
- Control conflict detection;
- checksum;
- lifecycle transitions.

## Integration tests

- create/publish;
- resolve;
- snapshot;
- usage index;
- audit;
- RBAC.

## UI tests

- catalog filters;
- editor autosave;
- validation;
- compare versions;
- preview effective rules;
- conflict display.

## End-to-end

```text
Create Rule
→ Create Version
→ Validate
→ Publish
→ Attach through scope
→ Resolve for Playbook
→ Start Execution
→ Freeze Bundle
→ Run Skill
→ Inspect Rule Bundle
```

---

# 29. Миграция текущего прототипа

1. Найти текущую страницу Rules.
2. Сохранить визуальные компоненты.
3. Удалить жёстко заданные mock rules.
4. Добавить реальные routes:
   - `/rules`;
   - `/rules/:id`;
   - `/rules/:id/versions/:versionId/edit`;
   - `/rules/preview`.
5. Создать API client.
6. Добавить модели Rule и RuleVersion.
7. Добавить миграции БД.
8. Добавить resolution service.
9. Интегрировать snapshot.
10. Добавить tests.

---

# 30. Последовательность Pull Requests

## PR-1

- navigation;
- catalog route;
- detail route;
- static UI migration;
- tests.

## PR-2

- Rule/RuleVersion schema;
- CRUD API;
- migrations;
- catalog integration.

## PR-3

- editor;
- autosave;
- Markdown preview;
- validation.

## PR-4

- scope selector;
- conflict strategies;
- resolver.

## PR-5

- effective rules preview;
- trace;
- version compare.

## PR-6

- Playbook/Skill integration;
- Execution Snapshot;
- Audit/Kafka.

---

# 31. Vertical Slice

Реализовать:

```text
Payments Workspace
  ↓
Corporate Requirements Style Rule
  ↓
Payments Terminology Rule
  ↓
System Requirements Playbook Rule
  ↓
Resolve Effective Rules
  ↓
Detect no conflicts
  ↓
Freeze Rule Bundle
  ↓
Run Generate Requirements Skill
  ↓
Inspect applied Rules in Execution Inspector
```

---

# 32. Definition of Done

Раздел Rules считается завершённым, если:

- каталог работает с реальным API;
- Rule создаётся;
- версии создаются;
- draft редактируется;
- validation работает;
- published version immutable;
- scope matching работает;
- conflict resolution работает;
- effective rules preview объясняет результат;
- Rule Bundle сохраняется в snapshot;
- Skill Runtime получает bundle;
- Controls имеют приоритет;
- RBAC работает;
- Audit создаётся;
- Kafka events публикуются;
- tests проходят;
- UI не использует production mocks.

---

# 33. Первое задание coding-агенту

1. Просканируй репозиторий.
2. Найди текущую реализацию Rules.
3. Создай `docs/rules/CURRENT_STATE.md`.
4. Сравни текущую модель с этим ТЗ.
5. Создай миграцию `rules` и `rule_versions`.
6. Реализуй read-only catalog API.
7. Подключи существующий UI к API.
8. Сохрани текущий визуальный стиль.
9. Добавь фильтры.
10. Добавь tests.
11. Обнови `docs/IMPLEMENTATION_STATUS.md`.
12. Не начинай resolver до прохождения CRUD tests.

---

# 34. Итоговая продуктовая модель

```text
Rule
  └── Rule Version
        ├── Category
        ├── Scope
        ├── Priority
        ├── Conflict Strategy
        ├── Content
        └── Validation

Execution Context
  ↓
Rule Resolver
  ↓
Conflict Resolver
  ↓
Control Validation
  ↓
Placeholder Rendering
  ↓
Rule Bundle
  ↓
Execution Snapshot
  ↓
Skill Runtime
```

Конец документа.
