# CONTROLS_SYSTEM_REQUIREMENTS.md
## Governed AI Delivery Platform
### Полное системное ТЗ на реализацию раздела Controls

---

# 0. Простое назначение Controls

Control — это проверяемое и исполнимое требование управления, которое ограничивает или направляет поведение платформы.

Он отвечает на вопрос:

> Что система обязана проверить или запретить до, во время или после выполнения?

Пример:

```text
Control: Human approval before publication

Applies to:
- Production workspace
- Artifact type: System Requirements

Enforcement:
- BLOCK

Evaluation:
- Before artifact publication

Requirement:
- Approved Human Checkpoint must exist

Evidence:
- Decision Record
- Artifact Version
- Execution Snapshot
```

Control — это не текстовая рекомендация. Он должен иметь формализованное условие, точку применения, результат и действие enforcement.

---

# 1. Место в архитектуре

```text
Flow / Playbook / Skill / Runtime / Execution
        ↓
Control Applicability Resolver
        ↓
Control Evaluation Engine
        ↓
PASSED / WARNING / FAILED / OVERRIDDEN
        ↓
Allow / Block / Require Approval / Escalate
```

---

# 2. Отличие Controls от Rules

Rules определяют:

> Как AI должен вести себя и какие инструкции учитывать.

Controls определяют:

> Что система должна проверить, ограничить или заблокировать.

Пример:

```text
Rule:
"В требованиях должны быть failure scenarios."

Control:
"Публикация запрещена, если раздел Failure Scenarios отсутствует."
```

Rule может влиять на генерацию.

Control должен уметь независимо проверить результат и применить enforcement.

---

# 3. Границы ответственности

Controls отвечают за:

- governance requirements;
- compliance checks;
- applicability;
- evaluation;
- enforcement;
- blocking;
- warnings;
- approvals;
- exceptions;
- overrides;
- evidence requirements;
- remediation;
- continuous monitoring;
- audit.

Controls не отвечают за:

- генерацию prompt;
- Playbook graph;
- Flow routing как основной механизм;
- исполнение Skill;
- хранение Knowledge Space;
- provider configuration;
- artifact authoring.

---

# 4. Типы Controls

Поддержать:

```text
PRECONDITION
POSTCONDITION
ARTIFACT_VALIDATION
RUNTIME_RESTRICTION
CAPABILITY_RESTRICTION
APPROVAL_REQUIREMENT
DATA_RESIDENCY
SECURITY
COMPLIANCE
COST_LIMIT
QUALITY_GATE
PUBLICATION_GATE
ROUTING_RESTRICTION
OBSERVABILITY
RETENTION
CUSTOM
```

Примеры:

- human approval before publication;
- EU-only processing for restricted data;
- no unrestricted network in production;
- minimum evidence count;
- mandatory architecture review for high-risk changes;
- maximum execution cost;
- no write capability without approval;
- artifact schema validation;
- mandatory rollback plan.

---

# 5. Жизненный цикл

```text
DRAFT
VALIDATING
READY
ACTIVE
DEPRECATED
DISABLED
ARCHIVED
```

Правила:

- ACTIVE version используется для новых evaluations;
- published/active version immutable;
- изменение создаёт новую version;
- running Execution использует control snapshot;
- DISABLED control не применяется;
- DEPRECATED доступен только в старых snapshots;
- exception не изменяет сам Control.

---

# 6. Основные сущности

```text
Control
  └── Control Version
        ├── Applicability
        ├── Evaluation Logic
        ├── Enforcement Policy
        ├── Evidence Requirements
        ├── Remediation
        ├── Exception Policy
        ├── Ownership
        └── Monitoring
```

---

# 7. Applicability

Applicability определяет, когда Control применяется.

Поддержать условия по:

- workspace;
- environment;
- Flow;
- Playbook;
- Skill;
- artifact type;
- runtime profile;
- provider;
- model;
- capability;
- source project;
- risk;
- data classification;
- user role;
- region;
- execution type.

Пример:

```json
{
  "all": [
    {
      "field": "environment",
      "operator": "EQUALS",
      "value": "PRODUCTION"
    },
    {
      "field": "artifact.type",
      "operator": "EQUALS",
      "value": "SYSTEM_REQUIREMENTS"
    }
  ]
}
```

---

# 8. Evaluation Points

Control может выполняться в точках:

```text
ROUTING
BEFORE_EXECUTION
BEFORE_STAGE
BEFORE_PLAYBOOK
BEFORE_SKILL
BEFORE_CAPABILITY_CALL
AFTER_SKILL
AFTER_PLAYBOOK
AFTER_STAGE
BEFORE_ARTIFACT_PUBLICATION
AFTER_EXECUTION
CONTINUOUS
```

Один Control может иметь несколько evaluation points.

---

# 9. Evaluation Logic

Поддержать механизмы:

```text
DECLARATIVE_EXPRESSION
SCHEMA_VALIDATION
POLICY_AS_CODE
ARTIFACT_QUERY
METRIC_THRESHOLD
CAPABILITY_CHECK
APPROVAL_CHECK
EXTERNAL_POLICY_ENGINE
CUSTOM_VALIDATOR
```

Безопасные технологии:

- CEL;
- JSON Logic;
- OPA/Rego;
- JSON Schema;
- platform DSL.

Запрещено:

- arbitrary eval;
- shell;
- direct SQL;
- unrestricted network;
- user-provided executable code без sandbox.

---

# 10. Control Result

Результаты:

```text
PASSED
WARNING
FAILED
NOT_APPLICABLE
ERROR
OVERRIDDEN
WAIVED
```

Result содержит:

```text
controlVersionId
evaluationPoint
result
severity
blocking
message
evidence
remediation
evaluatedAt
duration
```

---

# 11. Enforcement Policy

Поддержать действия:

```text
ALLOW
WARN
BLOCK
REQUIRE_HUMAN_APPROVAL
REQUIRE_REMEDIATION
RESTRICT_CAPABILITIES
SELECT_RESTRICTED_RUNTIME
ESCALATE
FAIL_EXECUTION
PAUSE_EXECUTION
```

Пример:

```json
{
  "onFailed": "BLOCK",
  "onWarning": "WARN",
  "onError": "PAUSE_EXECUTION"
}
```

---

# 12. Severity

```text
INFO
LOW
MEDIUM
HIGH
CRITICAL
```

Severity не равна enforcement.

Например:

- HIGH + WARN;
- MEDIUM + BLOCK;
- CRITICAL + REQUIRE_HUMAN_APPROVAL.

---

# 13. Evidence Requirements

Control может требовать evidence:

- artifact section;
- Human Checkpoint decision;
- runtime snapshot;
- source document;
- metric;
- audit event;
- capability call result;
- external attestation.

Пример:

```json
{
  "minimumEvidenceItems": 2,
  "requiredTypes": [
    "ARTIFACT_SECTION",
    "HUMAN_DECISION"
  ],
  "freshnessDays": 30
}
```

---

# 14. Remediation

Control должен объяснять, как исправить нарушение.

Remediation содержит:

```text
summary
steps
responsibleRole
automaticRemediation
documentationLink
retryEvaluation
```

Пример:

```json
{
  "summary": "Add rollback requirements",
  "steps": [
    "Open artifact draft",
    "Add rollback trigger",
    "Add recovery procedure",
    "Re-run validation"
  ],
  "responsibleRole": "SolutionArchitect"
}
```

---

# 15. Exceptions и Waivers

Exception — временное разрешение не применять enforcement Control.

Содержит:

```text
controlVersionId
scope
reason
riskAcceptance
requestedBy
approvedBy
validFrom
validUntil
conditions
status
```

Статусы:

```text
REQUESTED
IN_REVIEW
APPROVED
REJECTED
EXPIRED
REVOKED
```

Exception должна быть ограничена:

- временем;
- scope;
- workspace;
- execution;
- artifact;
- Flow;
- Playbook;
- source project.

---

# 16. Override Policy

Не каждый Control разрешает override.

Поддержать:

```text
NO_OVERRIDE
CONTROL_OWNER
SECURITY_OWNER
RISK_OWNER
MULTI_APPROVER
EMERGENCY_ONLY
```

Critical security Controls по умолчанию:

```text
NO_OVERRIDE
```

---

# 17. Control Bundles

Controls могут объединяться в bundles:

```text
Production Baseline
PCI DSS
GDPR Restricted Data
High-Risk Change
AI Safety Baseline
Secure Code Generation
```

Bundle содержит references на Control Versions.

Bundle versioned и immutable после активации.

---

# 18. Control Hierarchy

Уровни:

```text
Platform
Workspace
Environment
Flow
Playbook
Skill
Runtime Profile
Execution
```

Control с верхнего уровня наследуется вниз.

Нижний уровень не может ослабить Control без approved exception.

---

# 19. Effective Controls Resolution

Алгоритм:

```text
Platform Controls
  +
Workspace Controls
  +
Environment Controls
  +
Flow / Playbook Bindings
  +
Runtime Profile Controls
  +
Risk-based Controls
  -
Approved Exceptions
  =
Effective Control Set
```

API:

```http
POST /api/v1/controls/resolve
POST /api/v1/controls/resolve/preview
```

---

# 20. Controls Catalog UI

Показывать:

- name;
- key;
- type;
- severity;
- enforcement;
- status;
- owner;
- active version;
- applicability summary;
- violation count;
- exception count;
- last evaluated;
- health.

Функции:

- search;
- filters;
- create;
- duplicate;
- validate;
- activate;
- disable;
- deprecate;
- compare versions;
- view violations;
- request exception.

---

# 21. Control Detail UI

Вкладки:

```text
Overview
Applicability
Evaluation
Enforcement
Evidence
Remediation
Exceptions
Violations
Usage
Versions
Validation
Audit
```

---

# 22. Control Editor

Fullscreen editor.

Sections:

```text
General
Applicability
Evaluation Point
Evaluation Logic
Enforcement
Evidence
Remediation
Exception Policy
Ownership
Monitoring
```

Функции:

- autosave;
- expression builder;
- JSON preview;
- test against sample context;
- validate;
- compare;
- activate.

---

# 23. Applicability Builder

Поддержать визуальные группы:

```text
ALL
ANY
NOT
```

Operators:

```text
EQUALS
NOT_EQUALS
IN
NOT_IN
CONTAINS
STARTS_WITH
GREATER_THAN
LESS_THAN
EXISTS
MATCHES
```

---

# 24. Evaluation Playground

Пользователь задаёт sample context:

```text
Workspace
Environment
Flow
Playbook
Skill
Artifact
Runtime
Risk
Classification
```

Система показывает:

- applicable or not;
- evaluation trace;
- result;
- enforcement;
- evidence;
- remediation;
- exception effect.

---

# 25. Violations UI

Violation содержит:

- Control;
- Execution;
- entity;
- severity;
- status;
- first detected;
- last detected;
- owner;
- remediation status;
- exception;
- evidence.

Статусы:

```text
OPEN
ACKNOWLEDGED
IN_REMEDIATION
RESOLVED
ACCEPTED_RISK
FALSE_POSITIVE
```

---

# 26. Continuous Controls

CONTINUOUS controls могут периодически проверять:

- provider health;
- model allowlist;
- active Runtime Profiles;
- stale Knowledge Sources;
- overdue Checkpoints;
- cost thresholds;
- retention violations;
- disabled audit logging.

Scheduler:

```text
HOURLY
DAILY
WEEKLY
EVENT_DRIVEN
```

---

# 27. Model Data

## Control

```text
Control
- id UUID PK
- workspace_id UUID FK NULL
- key VARCHAR
- name VARCHAR
- description TEXT
- type VARCHAR
- status VARCHAR
- owner_team_id UUID NULL
- current_active_version_id UUID NULL
- created_by UUID
- created_at TIMESTAMP
- updated_at TIMESTAMP
- archived_at TIMESTAMP NULL
```

Constraint:

```text
UNIQUE(workspace_id, key)
```

## ControlVersion

```text
ControlVersion
- id UUID PK
- control_id UUID FK
- version_number INTEGER
- semantic_version VARCHAR
- status VARCHAR
- severity VARCHAR
- applicability_json JSONB
- evaluation_points_json JSONB
- evaluation_type VARCHAR
- evaluation_config_json JSONB
- enforcement_policy_json JSONB
- evidence_requirements_json JSONB
- remediation_json JSONB
- exception_policy_json JSONB
- monitoring_policy_json JSONB
- checksum VARCHAR
- created_by UUID
- created_at TIMESTAMP
- activated_by UUID NULL
- activated_at TIMESTAMP NULL
- deprecated_at TIMESTAMP NULL
```

## ControlBinding

```text
ControlBinding
- id UUID PK
- control_version_id UUID FK
- scope_type VARCHAR
- scope_id UUID NULL
- scope_key VARCHAR NULL
- priority INTEGER
- enabled BOOLEAN
- created_at TIMESTAMP
```

## ControlBundle

```text
ControlBundle
- id UUID PK
- workspace_id UUID FK NULL
- key VARCHAR
- name VARCHAR
- status VARCHAR
- current_version_id UUID NULL
- created_at TIMESTAMP
```

## ControlBundleVersion

```text
ControlBundleVersion
- id UUID PK
- control_bundle_id UUID FK
- version_number INTEGER
- status VARCHAR
- control_version_ids_json JSONB
- checksum VARCHAR
- created_at TIMESTAMP
- activated_at TIMESTAMP NULL
```

## ControlEvaluation

```text
ControlEvaluation
- id UUID PK
- execution_id UUID NULL
- control_version_id UUID FK
- evaluation_point VARCHAR
- entity_type VARCHAR
- entity_id UUID NULL
- context_json JSONB
- result VARCHAR
- severity VARCHAR
- blocking BOOLEAN
- message TEXT
- evidence_json JSONB
- remediation_json JSONB
- exception_id UUID NULL
- duration_ms INTEGER
- evaluated_at TIMESTAMP
```

## ControlViolation

```text
ControlViolation
- id UUID PK
- control_evaluation_id UUID FK
- control_version_id UUID FK
- execution_id UUID NULL
- entity_type VARCHAR
- entity_id UUID NULL
- status VARCHAR
- owner_id UUID NULL
- first_detected_at TIMESTAMP
- last_detected_at TIMESTAMP
- resolved_at TIMESTAMP NULL
- resolution_json JSONB NULL
```

## ControlException

```text
ControlException
- id UUID PK
- control_version_id UUID FK
- scope_json JSONB
- reason TEXT
- risk_acceptance TEXT
- status VARCHAR
- requested_by UUID
- approved_by UUID NULL
- valid_from TIMESTAMP
- valid_until TIMESTAMP
- conditions_json JSONB
- created_at TIMESTAMP
- decided_at TIMESTAMP NULL
- revoked_at TIMESTAMP NULL
```

## ControlValidationRun

```text
ControlValidationRun
- id UUID PK
- control_version_id UUID FK
- status VARCHAR
- result_json JSONB
- started_at TIMESTAMP
- completed_at TIMESTAMP
```

---

# 28. REST API

## Controls

```http
GET    /api/v1/controls
POST   /api/v1/controls
GET    /api/v1/controls/{controlId}
PATCH  /api/v1/controls/{controlId}
DELETE /api/v1/controls/{controlId}
POST   /api/v1/controls/{controlId}/archive
POST   /api/v1/controls/{controlId}/restore
POST   /api/v1/controls/{controlId}/duplicate
```

## Versions

```http
GET  /api/v1/controls/{controlId}/versions
POST /api/v1/controls/{controlId}/versions
GET  /api/v1/controls/{controlId}/versions/{versionId}
PATCH /api/v1/controls/{controlId}/versions/{versionId}
POST /api/v1/controls/{controlId}/versions/{versionId}/validate
POST /api/v1/controls/{controlId}/versions/{versionId}/activate
POST /api/v1/controls/{controlId}/versions/{versionId}/deprecate
POST /api/v1/controls/{controlId}/versions/{versionId}/clone
POST /api/v1/controls/{controlId}/versions/{versionId}/test
```

## Resolution and evaluation

```http
POST /api/v1/controls/resolve
POST /api/v1/controls/resolve/preview
POST /api/v1/controls/evaluate
GET  /api/v1/controls/evaluations/{evaluationId}
```

## Violations

```http
GET   /api/v1/control-violations
GET   /api/v1/control-violations/{violationId}
POST  /api/v1/control-violations/{violationId}/acknowledge
POST  /api/v1/control-violations/{violationId}/resolve
POST  /api/v1/control-violations/{violationId}/accept-risk
```

## Exceptions

```http
GET  /api/v1/control-exceptions
POST /api/v1/control-exceptions
GET  /api/v1/control-exceptions/{exceptionId}
POST /api/v1/control-exceptions/{exceptionId}/approve
POST /api/v1/control-exceptions/{exceptionId}/reject
POST /api/v1/control-exceptions/{exceptionId}/revoke
```

## Bundles

```http
GET  /api/v1/control-bundles
POST /api/v1/control-bundles
GET  /api/v1/control-bundles/{bundleId}
POST /api/v1/control-bundles/{bundleId}/versions
POST /api/v1/control-bundles/{bundleId}/versions/{versionId}/activate
```

---

# 29. API examples

## Create Control

```json
{
  "key": "human-approval-before-publication",
  "name": "Human approval before publication",
  "description": "Published artifacts require an approved checkpoint",
  "type": "PUBLICATION_GATE",
  "ownerTeamId": "uuid"
}
```

## Evaluate

```json
{
  "controlVersionId": "uuid",
  "evaluationPoint": "BEFORE_ARTIFACT_PUBLICATION",
  "context": {
    "executionId": "uuid",
    "artifactVersionId": "uuid",
    "checkpointStatus": "APPROVED"
  }
}
```

Response:

```json
{
  "result": "PASSED",
  "blocking": false,
  "message": "Approved checkpoint found"
}
```

---

# 30. Control Engine

Main services:

```text
ControlApplicabilityResolver
EffectiveControlResolver
ControlEvaluationEngine
ControlEnforcementService
ControlEvidenceCollector
ControlExceptionResolver
ControlViolationService
ControlRemediationService
```

Evaluation flow:

```text
Receive evaluation context
  ↓
Resolve effective Controls
  ↓
Filter applicable Controls
  ↓
Resolve active exceptions
  ↓
Evaluate
  ↓
Persist results
  ↓
Create/update violations
  ↓
Apply enforcement
  ↓
Emit events
```

---

# 31. Integration with Playbooks

Playbook can:

- declare required Controls;
- bind Control Bundle;
- define evaluation points;
- require approval on failure;
- stop publication on blocking failure.

Playbook не может disable inherited Control.

---

# 32. Integration with Flows

Flow can:

- bind controls to stages;
- require stage gate;
- route by control result;
- pause on violation;
- require risk acceptance;
- block transition.

---

# 33. Integration with Skills

Skill manifest can declare:

```yaml
control_requirements:
  required:
    - secure-code-generation
  evaluation_points:
    - AFTER_SKILL
```

Skill не исполняет Control самостоятельно.

---

# 34. Integration with Runtime Profiles

Controls can:

- deny provider;
- restrict model;
- force sandbox;
- deny network;
- restrict region;
- require supervision;
- limit cost;
- restrict capabilities.

---

# 35. Integration with Knowledge Spaces

Controls can require:

- trusted source types;
- minimum evidence;
- freshness;
- classification;
- region;
- source availability;
- citation coverage.

---

# 36. Integration with Human Checkpoints

On failure Control may:

```text
REQUIRE_HUMAN_APPROVAL
```

Checkpoint должен показывать:

- failed control;
- evidence;
- severity;
- remediation;
- override eligibility.

---

# 37. Integration with Executions

Execution Snapshot stores effective Control Set.

Every evaluation is linked to:

- execution;
- entity;
- stage;
- playbook run;
- skill run;
- artifact.

Running Execution is not affected by newly activated Control Version unless continuous policy explicitly allows it.

---

# 38. Temporal Integration

Activities:

```text
ResolveEffectiveControlsActivity
EvaluateControlsActivity
ApplyEnforcementActivity
CreateControlViolationActivity
CreateControlCheckpointActivity
ResolveControlExceptionActivity
```

Typed outcomes:

```text
CONTINUE
WARN
BLOCKED
WAITING_FOR_HUMAN
FAILED
PAUSED
```

---

# 39. Kafka Events

Topic:

```text
control-events
```

Events:

```text
control.created
control.version.created
control.version.validated
control.version.activated
control.version.deprecated
control.evaluated
control.passed
control.warning
control.failed
control.violation.created
control.violation.resolved
control.exception.requested
control.exception.approved
control.exception.rejected
control.exception.expired
control.enforcement.applied
```

---

# 40. RBAC

Permissions:

```text
control.read
control.create
control.edit
control.validate
control.activate
control.disable
control.archive
control.evaluate
control.resolve_preview
control.violation.read
control.violation.manage
control.exception.request
control.exception.approve
control.exception.revoke
control.audit.read
```

---

# 41. Audit Events

```text
control.created
control.updated
control.archived
control.version.created
control.version.updated
control.version.validated
control.version.activated
control.version.deprecated
control.binding.created
control.binding.removed
control.evaluation.executed
control.violation.acknowledged
control.violation.resolved
control.exception.requested
control.exception.approved
control.exception.rejected
control.exception.revoked
```

---

# 42. Backend architecture

```text
modules/controls/
├── domain/
│   ├── Control
│   ├── ControlVersion
│   ├── ControlBinding
│   ├── ControlEvaluation
│   ├── ControlViolation
│   ├── ControlException
│   └── ControlBundle
├── application/
│   ├── CreateControl
│   ├── ValidateControl
│   ├── ActivateControl
│   ├── ResolveEffectiveControls
│   ├── EvaluateControls
│   ├── ApplyEnforcement
│   ├── RequestException
│   └── ResolveViolation
├── infrastructure/
│   ├── ControlRepository
│   ├── PolicyEngineAdapter
│   ├── ViolationRepository
│   └── ExceptionRepository
├── api/
└── tests/
```

---

# 43. Frontend architecture

```text
pages/controls/
├── ControlsCatalogPage
├── ControlDetailPage
├── ControlEditorPage
├── ControlPlaygroundPage
├── ControlViolationsPage
├── ControlExceptionsPage
└── ControlBundlesPage

features/controls/
├── create-control
├── edit-control
├── validate-control
├── activate-control
├── evaluate-control
├── request-exception
└── resolve-violation
```

Components:

```text
ControlCard
ControlStatusBadge
SeverityBadge
EnforcementBadge
ApplicabilityBuilder
EvaluationLogicEditor
EnforcementEditor
EvidenceRequirementsEditor
RemediationEditor
ControlResultPanel
ViolationTable
ExceptionRequestDialog
EffectiveControlsPreview
```

---

# 44. NFR

- catalog p95 < 500 ms;
- effective resolution p95 < 300 ms;
- synchronous evaluation p95 < 200 ms for declarative controls;
- external policy evaluation p95 < 1 s;
- minimum 100 000 Controls;
- minimum 10 млн evaluations/day;
- immutable active versions;
- idempotent enforcement;
- full audit;
- evaluation trace;
- optimistic locking;
- policy caching;
- circuit breaker for external engine;
- no raw secrets in context;
- configurable retention.

---

# 45. Testing

## Unit

- applicability;
- hierarchy;
- effective resolution;
- exceptions;
- severity;
- enforcement mapping;
- evidence requirements;
- violation lifecycle;
- fallback on evaluation error.

## Integration

- create/activate;
- bind to Playbook;
- evaluate during Execution;
- block publication;
- create Checkpoint;
- approve exception;
- resume;
- audit and Kafka.

## UI

- catalog;
- filters;
- editor;
- applicability builder;
- playground;
- violations;
- exception request;
- version compare.

## E2E

```text
Create Publication Gate Control
→ Bind to System Requirements
→ Start Execution
→ Generate Artifact
→ Evaluate before publication
→ Fail because approval missing
→ Open Human Checkpoint
→ Reviewer approves
→ Re-evaluate
→ Pass
→ Publish Artifact
```

---

# 46. Migration

1. Найти текущий раздел Controls/Policies.
2. Найти hardcoded checks.
3. Создать inventory existing enforcement.
4. Ввести Control и ControlVersion.
5. Добавить routes:
   - `/controls`;
   - `/controls/:id`;
   - `/controls/:id/versions/:versionId/edit`;
   - `/controls/playground`;
   - `/control-violations`;
   - `/control-exceptions`.
6. Перенести hardcoded checks в declarative Controls.
7. Добавить resolution engine.
8. Добавить evaluation engine.
9. Подключить Execution runtime.
10. Добавить exception workflow.

---

# 47. Pull Request Sequence

## PR-1

- catalog;
- detail shell;
- API types;
- status/severity badges.

## PR-2

- DB schema;
- CRUD;
- versioning.

## PR-3

- applicability builder;
- evaluation config;
- validation.

## PR-4

- effective resolution;
- synchronous evaluation;
- enforcement.

## PR-5

- violations;
- exceptions;
- Human Checkpoint integration.

## PR-6

- continuous controls;
- bundles;
- Audit/Kafka;
- migration of hardcoded checks.

---

# 48. Vertical Slice

```text
Control: Human approval before publication
  ↓
Applied to System Requirements Artifact
  ↓
Execution reaches publication
  ↓
Control evaluates approval evidence
  ↓
No approved checkpoint found
  ↓
Result: FAILED
  ↓
Enforcement: REQUIRE_HUMAN_APPROVAL
  ↓
Checkpoint created
  ↓
Reviewer approves
  ↓
Control re-evaluated
  ↓
PASSED
  ↓
Artifact published
```

---

# 49. Definition of Done

Раздел завершён, если:

- Control создаётся;
- versioning работает;
- active version immutable;
- applicability builder работает;
- evaluation points работают;
- declarative evaluation работает;
- enforcement применяется;
- violations создаются;
- exceptions работают;
- effective resolution объясним;
- Control snapshots входят в Execution;
- Human Checkpoint integration работает;
- Runtime restrictions применяются;
- bundles работают;
- RBAC работает;
- Audit/Kafka работают;
- tests проходят;
- hardcoded production checks мигрированы.

---

# 50. Первое задание coding-агенту

1. Просканируй репозиторий.
2. Найди текущие Controls, Policies и hardcoded governance checks.
3. Создай `docs/controls/CURRENT_STATE.md`.
4. Составь inventory hardcoded enforcement.
5. Создай schema `controls`, `control_versions`, `control_evaluations`.
6. Реализуй read-only catalog API.
7. Подключи UI к API.
8. Добавь Control Detail shell.
9. Реализуй state/version tests.
10. Добавь skeleton applicability resolver.
11. Обнови `docs/IMPLEMENTATION_STATUS.md`.
12. Не подключай blocking enforcement до прохождения evaluation idempotency tests.

---

# 51. Итоговая модель

```text
Governance Requirement
  ↓
Control Version
  ├── Applicability
  ├── Evaluation Point
  ├── Evaluation Logic
  ├── Enforcement
  ├── Evidence
  ├── Remediation
  └── Exception Policy
        ↓
Control Evaluation
        ↓
PASSED / WARNING / FAILED
        ↓
Allow / Block / Approve / Remediate
```

Конец документа.
