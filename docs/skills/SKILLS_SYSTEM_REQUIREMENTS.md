# System Requirements: Skills
## Governed AI Delivery Platform
### Version 1.0

---

# 1. Purpose

This document defines the complete functional and technical requirements for the **Skills** subsystem of the Governed AI Delivery Platform.

The implementation target is an existing prototype. The coding agent must migrate and extend the current codebase rather than create a disconnected greenfield application.

The Skills subsystem is responsible for:

- storing reusable cognitive operations;
- implementing stable Skill Interfaces;
- importing Anthropic-style `SKILL.md` packages;
- versioning and publishing Skills;
- validating manifests and contracts;
- testing Skills in isolation;
- binding Skill versions to Playbook Skill Slots;
- resolving the effective implementation at runtime;
- enforcing capability, policy, sandbox and model restrictions;
- recording execution telemetry and audit evidence.

A Skill is not an agent, not a workflow, and not a direct MCP integration.

---

# 2. Core model

```text
Playbook Step
  -> Skill Slot
    -> Skill Interface
      -> Skill Binding
        -> Skill Version
          -> Skill Runtime
            -> Capability Gateway
```

A Playbook references a Skill Interface, never a concrete tool.

Example:

```text
analysis.requirements.generate@1
```

Several Skill versions may implement the same interface:

```text
Core Requirements Generator
Corporate Requirements Generator
Payments Team Requirements Generator
Imported Requirements Generator
```

The runtime selects the effective Skill version using deterministic binding resolution.

---

# 3. Design principles

## 3.1 One cognitive transformation per Skill

A Skill should perform one bounded transformation.

Good examples:

- understand a work item;
- identify missing requirements;
- generate system requirements;
- review source code;
- generate test cases;
- identify operational risks;
- summarize evidence.

Bad examples:

- implement a feature end-to-end;
- run the entire SDLC;
- autonomously manage a project.

## 3.2 Skills are provider-neutral

Skills use abstract capabilities:

```text
context.search
context.read
artifact.read
artifact.patch
repository.search
repository.read
repository.patch
human.ask
publisher.publish
```

Skills must not reference:

```text
jira.getIssue
slack.search
confluence.readPage
notion.query
```

## 3.3 Published versions are immutable

A published Skill version cannot be edited in place.

Any change creates a new version.

## 3.4 Runtime reproducibility

Every Skill Run must record:

- Skill ID;
- Skill Version ID;
- package checksum;
- Skill Interface version;
- resolved rules;
- resolved controls;
- runtime profile;
- model;
- allowed capabilities;
- context snapshot hash;
- input artifact version;
- output patch;
- token and latency metrics.

## 3.5 Skills do not mutate final artifacts directly

A Skill returns an `ArtifactPatch` or another typed output contract.

The platform validates and applies the patch atomically.

---

# 4. Skills navigation section

The primary navigation entry is:

```text
Build
  Skills
```

The Skills area contains:

- Skills Catalog;
- Skill Detail;
- Skill Editor;
- Skill Interfaces;
- Import Skill;
- Skill Test Lab;
- Usage and Bindings;
- Versions;
- Validation Reports.

---

# 5. Skills Catalog

## 5.1 Purpose

The catalog provides a searchable inventory of all available Skills.

## 5.2 Required columns and card fields

- name;
- key;
- type;
- owner;
- current version;
- lifecycle status;
- implemented interfaces;
- required capabilities count;
- runtime type;
- last validation status;
- usage count;
- updated timestamp.

## 5.3 Filters

- status;
- type;
- owner;
- interface;
- capability;
- runtime type;
- validation state;
- used / unused;
- published / draft.

## 5.4 Actions

- create Skill;
- import Skill package;
- open details;
- clone;
- deprecate;
- archive;
- compare versions;
- test;
- publish;
- inspect usage.

## 5.5 API

```http
GET  /api/v1/skills
POST /api/v1/skills
```

Query parameters:

```text
q
status
skillType
ownerId
interfaceKey
capability
runtimeType
validationStatus
used
limit
cursor
sort
```

---

# 6. Skill types

Supported types:

```text
CORE
CORPORATE
TEAM
USER
IMPORTED
```

## CORE

Maintained by the platform team and shipped with the product.

## CORPORATE

Approved organization-wide implementation.

## TEAM

Owned by a domain or engineering team.

## USER

Experimental implementation created by an individual user.

## IMPORTED

Imported from an external package or repository.

Type affects governance, visibility and publication policy, not runtime semantics.

---

# 7. Skill lifecycle

```text
DRAFT
  -> VALIDATING
  -> READY
  -> PUBLISHED
  -> DEPRECATED
  -> ARCHIVED
```

Additional failure state for validation runs:

```text
INVALID
```

Rules:

- only `PUBLISHED` Skill versions can be selected for production executions;
- `READY` means validation passed but publication approval has not completed;
- `DEPRECATED` versions remain executable for frozen snapshots;
- `ARCHIVED` versions cannot be used for new bindings;
- published versions are immutable.

---

# 8. Skill package format

Minimum package:

```text
skill-package/
├── SKILL.md
├── manifest.yaml
├── schemas/
│   ├── input.schema.json
│   └── output.schema.json
├── examples/
│   ├── example-01-input.json
│   └── example-01-output.json
├── tests/
│   └── cases.yaml
└── assets/
```

Only `SKILL.md` and `manifest.yaml` are mandatory for draft import.

Schemas and tests are mandatory before publication unless explicitly waived by a Control.

---

# 9. Skill manifest

Example:

```yaml
apiVersion: platform.skills/v1
kind: Skill
metadata:
  key: team-system-requirements
  name: Team System Requirements Generator
  description: Generates system requirements from a normalized problem artifact.
  type: TEAM
  owner: payments-analysis
spec:
  version: 1.4.0
  implements:
    - analysis.system_requirements.generate@1
  requiredCapabilities:
    - context.search
    - context.read
    - artifact.read
    - artifact.patch
  optionalCapabilities:
    - human.ask
  inputContract: ProblemUnderstandingArtifact@1
  outputContract: SystemRequirementsPatch@1
  runtime:
    type: qwen-code-cli
    entrypoint: SKILL.md
    timeoutSeconds: 900
    maxAttempts: 2
  context:
    maxTokens: 24000
    evidenceLimit: 20
  security:
    dataClassifications:
      - INTERNAL
      - CONFIDENTIAL
```

Required fields:

- metadata.key;
- metadata.name;
- metadata.type;
- spec.version;
- spec.implements;
- spec.inputContract;
- spec.outputContract;
- spec.runtime.type;
- spec.runtime.entrypoint.

---

# 10. SKILL.md requirements

`SKILL.md` is the human-readable execution specification for the Skill runtime.

It must include:

```text
# Purpose
# Inputs
# Outputs
# Allowed Capabilities
# Procedure
# Quality Criteria
# Failure Conditions
# Examples
```

It must not include:

- secrets;
- direct MCP server configuration;
- hard-coded tenant identifiers;
- direct provider credentials;
- instructions to bypass Controls;
- instructions to publish without approval;
- hidden mutable state assumptions.

The editor must provide lint warnings when prohibited patterns are detected.

---

# 11. Skill Interfaces

## 11.1 Purpose

A Skill Interface is a stable extension point used by Playbooks.

Example:

```text
analysis.system_requirements.generate@1
```

## 11.2 Interface fields

- key;
- major version;
- name;
- description;
- input contract;
- output contract;
- required capabilities;
- optional capabilities;
- compatibility rules;
- status.

## 11.3 Versioning

Only the major version is part of the interface key visible to Playbooks.

Breaking changes require a new major version.

Non-breaking schema evolution may remain within the same major version if compatibility tests pass.

## 11.4 API

```http
GET    /api/v1/skill-interfaces
POST   /api/v1/skill-interfaces
GET    /api/v1/skill-interfaces/{interfaceId}
PATCH  /api/v1/skill-interfaces/{interfaceId}
POST   /api/v1/skill-interfaces/{interfaceId}/validate
POST   /api/v1/skill-interfaces/{interfaceId}/deprecate
GET    /api/v1/skill-interfaces/{interfaceId}/implementations
```

---

# 12. Skill Detail screen

Tabs:

```text
Overview
Instructions
Manifest
Interfaces
Capabilities
Versions
Tests
Bindings
Usage
Validation
Audit
```

## Overview

Displays:

- description;
- owner;
- type;
- lifecycle;
- current published version;
- implemented interfaces;
- validation state;
- runtime;
- usage count;
- last executions metrics.

## Instructions

Read-only rendering for published versions and editor for drafts.

## Manifest

Structured form and raw YAML modes.

## Interfaces

Implemented interface list and compatibility state.

## Capabilities

Required and optional capabilities with provider availability status.

## Versions

Version timeline, compare action, publish and deprecate operations.

## Tests

Test suites, run history and assertion results.

## Bindings

Scopes where the Skill is currently selected.

## Usage

Playbooks, flows, executions and success metrics.

## Validation

Static, schema, security and runtime validation reports.

---

# 13. Skill Editor

## 13.1 Layout

Three-column IDE-style layout:

```text
File Tree | Editor | Inspector / Problems
```

## 13.2 File tree

Supports:

- SKILL.md;
- manifest.yaml;
- JSON schemas;
- examples;
- tests;
- assets metadata.

## 13.3 Editor features

- Markdown editor;
- YAML editor;
- JSON schema editor;
- syntax highlighting;
- validation markers;
- autosave;
- diff against published version;
- command palette;
- preview;
- undo/redo;
- keyboard shortcuts.

## 13.4 Inspector

Shows:

- parsed metadata;
- interface compatibility;
- capabilities;
- unresolved problems;
- context estimate;
- package size;
- security findings.

## 13.5 API

```http
GET  /api/v1/skills/{skillId}/versions/{versionId}/files
GET  /api/v1/skills/{skillId}/versions/{versionId}/files/{path}
PUT  /api/v1/skills/{skillId}/versions/{versionId}/files/{path}
POST /api/v1/skills/{skillId}/versions/{versionId}/files
DELETE /api/v1/skills/{skillId}/versions/{versionId}/files/{path}
POST /api/v1/skills/{skillId}/versions/{versionId}/preview
```

Editing published versions must return `409 IMMUTABLE_VERSION`.

---

# 14. Import Skill flow

## 14.1 Sources

- ZIP upload;
- Git repository URL;
- internal artifact registry;
- copied `SKILL.md` text;
- local directory through development tooling.

## 14.2 Import stages

```text
Upload
  -> Scan
  -> Parse
  -> Normalize
  -> Validate
  -> Review
  -> Create Draft
```

## 14.3 Security checks

- archive path traversal;
- executable file detection;
- package size limit;
- secret scanning;
- prohibited extension detection;
- symlink rejection;
- malware scanning hook;
- prompt injection heuristics;
- direct provider/tool references.

## 14.4 API

```http
POST /api/v1/skills/imports
GET  /api/v1/skills/imports/{importId}
POST /api/v1/skills/imports/{importId}/validate
POST /api/v1/skills/imports/{importId}/create-draft
DELETE /api/v1/skills/imports/{importId}
```

---

# 15. Validation pipeline

Validation levels:

## 15.1 Package validation

- required files;
- file size;
- safe paths;
- supported encodings;
- manifest syntax.

## 15.2 Manifest validation

- required fields;
- semantic version;
- known runtime type;
- known interfaces;
- known capabilities;
- contract references.

## 15.3 Instruction validation

- required sections;
- empty instructions;
- prohibited direct integrations;
- contradictory output format;
- excessive size;
- unsupported directives.

## 15.4 Contract validation

- input schema exists;
- output schema exists;
- interface contract compatibility;
- sample data validity;
- patch schema validity.

## 15.5 Security validation

- secret scan;
- tool bypass instructions;
- network access requests;
- shell execution requirements;
- sensitive data conflicts;
- unsafe package files.

## 15.6 Runtime validation

- sandbox startup;
- entrypoint loading;
- capability interception;
- timeout handling;
- deterministic test execution.

## 15.7 Publication validation

Publication is blocked when any error-level problem exists.

Warnings may require explicit waiver and audit record.

## 15.8 API

```http
POST /api/v1/skills/{skillId}/versions/{versionId}/validate
GET  /api/v1/skills/{skillId}/versions/{versionId}/validation-report
```

---

# 16. Skill Test Lab

## 16.1 Purpose

Allows developers to execute a draft Skill with controlled inputs before publication.

## 16.2 Test modes

```text
STATIC
CONTRACT
MOCK_CAPABILITIES
SANDBOX
SHADOW
REGRESSION
```

## 16.3 Test case fields

- name;
- input artifact;
- rules fixture;
- controls fixture;
- evidence fixture;
- mocked capability responses;
- expected output schema;
- assertions;
- maximum tokens;
- maximum duration.

## 16.4 Assertions

- schema valid;
- required field exists;
- prohibited field absent;
- evidence references present;
- patch operation count;
- no capability violation;
- token limit;
- latency limit;
- semantic evaluator score.

## 16.5 UI

The Test Lab contains:

- input editor;
- fixture selector;
- capability mock panel;
- run button;
- streaming logs;
- output preview;
- patch diff;
- assertion results;
- token and latency metrics.

## 16.6 API

```http
POST /api/v1/skills/{skillId}/versions/{versionId}/test-runs
GET  /api/v1/skills/{skillId}/versions/{versionId}/test-runs
GET  /api/v1/skill-test-runs/{testRunId}
POST /api/v1/skill-test-runs/{testRunId}/cancel
GET  /api/v1/skill-test-runs/{testRunId}/events
```

---

# 17. Skill Bindings

## 17.1 Purpose

Bindings select a concrete Skill version for a Skill Interface in a specific scope.

## 17.2 Scope precedence

From lowest to highest priority:

```text
PLATFORM
WORKSPACE
KNOWLEDGE_SPACE
FLOW
PLAYBOOK
PLAYBOOK_STEP
EXECUTION_OVERRIDE
```

## 17.3 Binding fields

- interface;
- Skill version;
- scope type;
- scope selector;
- priority;
- conditions;
- enabled;
- effective dates;
- fallback binding.

## 17.4 Resolution algorithm

1. Load all published compatible Skill versions.
2. Load bindings matching the execution snapshot context.
3. Remove disabled and expired bindings.
4. Remove versions blocked by Controls.
5. Remove versions whose required capabilities cannot be resolved.
6. Sort by scope specificity.
7. Sort by explicit priority.
8. Evaluate conditions.
9. Select the first deterministic match.
10. Persist the result in Execution Snapshot.

A runtime execution must never re-resolve a Skill after snapshot creation unless an explicit recovery policy allows fallback.

## 17.5 API

```http
GET    /api/v1/skill-bindings
POST   /api/v1/skill-bindings
GET    /api/v1/skill-bindings/{bindingId}
PATCH  /api/v1/skill-bindings/{bindingId}
DELETE /api/v1/skill-bindings/{bindingId}
POST   /api/v1/skill-bindings/resolve
POST   /api/v1/skill-bindings/simulate
```

---

# 18. Skill runtime

## 18.1 Runtime types

Initial supported runtimes:

```text
qwen-code-cli
llm-prompt-runtime
container-runtime
remote-skill-runtime
```

MVP must support `qwen-code-cli` and `llm-prompt-runtime`.

## 18.2 Runtime input

```json
{
  "executionId": "uuid",
  "skillRunId": "uuid",
  "skillVersion": {},
  "interface": {},
  "taskCharter": {},
  "stageGoal": "...",
  "artifactSnapshot": {},
  "evidenceBundle": [],
  "rulesBundle": [],
  "controls": [],
  "allowedCapabilities": [],
  "outputContract": {},
  "limits": {}
}
```

## 18.3 Runtime output

```json
{
  "status": "SUCCEEDED",
  "artifactPatch": {},
  "signals": [],
  "openQuestions": [],
  "decisions": [],
  "evidenceReferences": [],
  "metrics": {
    "inputTokens": 0,
    "outputTokens": 0,
    "durationMs": 0
  }
}
```

## 18.4 Sandbox requirements

- isolated workspace;
- read-only Skill package;
- explicit temporary directory;
- blocked direct network by default;
- capability calls through a proxy;
- CPU, memory and time limits;
- process tree termination on timeout;
- stdout/stderr capture;
- no host credentials;
- no unrestricted shell inheritance.

## 18.5 Capability interception

The Skill runtime receives a local capability client.

Every request is routed to Capability Gateway and recorded as a Capability Call.

Direct MCP access is forbidden.

---

# 19. Skill execution lifecycle

```text
CREATED
PREPARING
RUNNING
WAITING_CAPABILITY
WAITING_HUMAN
VALIDATING_OUTPUT
APPLYING_PATCH
SUCCEEDED
FAILED
CANCELLED
TIMED_OUT
```

Execution algorithm:

1. Load Skill version from frozen snapshot.
2. Verify checksum.
3. Verify runtime profile.
4. Build minimal context.
5. Resolve allowed capabilities from Skill, Playbook and Controls.
6. Start sandbox.
7. Execute Skill.
8. Stream logs and runtime events.
9. Validate output contract.
10. Validate evidence references.
11. Validate Artifact Patch.
12. Apply patch atomically.
13. Persist metrics.
14. Emit audit and Kafka events.
15. Close sandbox.

---

# 20. Data model

## 20.1 Skill

```text
Skill
- id UUID PK
- workspace_id UUID NULL
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
- revision INTEGER
```

Unique:

```text
(workspace_id, key)
```

## 20.2 SkillVersion

```text
SkillVersion
- id UUID PK
- skill_id UUID FK
- semantic_version VARCHAR
- status VARCHAR
- manifest_json JSONB
- skill_markdown TEXT
- package_uri TEXT
- package_checksum VARCHAR
- runtime_type VARCHAR
- input_contract_key VARCHAR
- output_contract_key VARCHAR
- validation_status VARCHAR
- created_by UUID
- created_at TIMESTAMP
- published_by UUID NULL
- published_at TIMESTAMP NULL
- deprecated_at TIMESTAMP NULL
```

Unique:

```text
(skill_id, semantic_version)
```

## 20.3 SkillFile

```text
SkillFile
- id UUID PK
- skill_version_id UUID FK
- path VARCHAR
- media_type VARCHAR
- content_text TEXT NULL
- content_uri TEXT NULL
- content_hash VARCHAR
- size_bytes BIGINT
- created_at TIMESTAMP
```

## 20.4 SkillInterface

```text
SkillInterface
- id UUID PK
- key VARCHAR
- major_version INTEGER
- name VARCHAR
- description TEXT
- input_contract_key VARCHAR
- output_contract_key VARCHAR
- required_capabilities JSONB
- optional_capabilities JSONB
- compatibility_policy JSONB
- status VARCHAR
- created_at TIMESTAMP
```

## 20.5 SkillImplementation

```text
SkillImplementation
- id UUID PK
- skill_version_id UUID FK
- skill_interface_id UUID FK
- compatibility_status VARCHAR
- validation_report_id UUID NULL
- created_at TIMESTAMP
```

## 20.6 SkillBinding

```text
SkillBinding
- id UUID PK
- workspace_id UUID FK
- skill_interface_id UUID FK
- skill_version_id UUID FK
- scope_type VARCHAR
- scope_id UUID NULL
- playbook_step_key VARCHAR NULL
- priority INTEGER
- conditions_json JSONB
- fallback_binding_id UUID NULL
- effective_from TIMESTAMP NULL
- effective_to TIMESTAMP NULL
- enabled BOOLEAN
- created_at TIMESTAMP
```

## 20.7 SkillValidationRun

```text
SkillValidationRun
- id UUID PK
- skill_version_id UUID FK
- status VARCHAR
- validator_version VARCHAR
- report_json JSONB
- error_count INTEGER
- warning_count INTEGER
- started_at TIMESTAMP
- completed_at TIMESTAMP NULL
```

## 20.8 SkillTestCase

```text
SkillTestCase
- id UUID PK
- skill_version_id UUID FK
- key VARCHAR
- name VARCHAR
- definition_json JSONB
- enabled BOOLEAN
- created_at TIMESTAMP
```

## 20.9 SkillTestRun

```text
SkillTestRun
- id UUID PK
- skill_version_id UUID FK
- test_case_id UUID NULL
- mode VARCHAR
- status VARCHAR
- input_json JSONB
- output_json JSONB NULL
- assertion_results JSONB NULL
- metrics_json JSONB NULL
- started_at TIMESTAMP
- completed_at TIMESTAMP NULL
```

## 20.10 SkillRun

```text
SkillRun
- id UUID PK
- execution_id UUID FK
- playbook_run_id UUID FK
- playbook_step_key VARCHAR
- skill_version_id UUID FK
- skill_interface_id UUID FK
- status VARCHAR
- attempt INTEGER
- runtime_profile_id UUID FK
- context_snapshot_hash VARCHAR
- input_artifact_version_id UUID NULL
- output_patch_id UUID NULL
- token_usage_json JSONB
- cost_json JSONB
- started_at TIMESTAMP
- completed_at TIMESTAMP NULL
- error_json JSONB NULL
```

## 20.11 SkillImport

```text
SkillImport
- id UUID PK
- workspace_id UUID FK
- source_type VARCHAR
- source_reference VARCHAR
- status VARCHAR
- scan_report JSONB
- normalized_manifest JSONB NULL
- created_skill_id UUID NULL
- created_at TIMESTAMP
- completed_at TIMESTAMP NULL
```

---

# 21. REST API

## Skills

```http
GET    /api/v1/skills
POST   /api/v1/skills
GET    /api/v1/skills/{skillId}
PATCH  /api/v1/skills/{skillId}
DELETE /api/v1/skills/{skillId}
POST   /api/v1/skills/{skillId}/clone
GET    /api/v1/skills/{skillId}/usage
GET    /api/v1/skills/{skillId}/metrics
```

## Versions

```http
GET    /api/v1/skills/{skillId}/versions
POST   /api/v1/skills/{skillId}/versions
GET    /api/v1/skills/{skillId}/versions/{versionId}
PATCH  /api/v1/skills/{skillId}/versions/{versionId}
POST   /api/v1/skills/{skillId}/versions/{versionId}/validate
POST   /api/v1/skills/{skillId}/versions/{versionId}/publish
POST   /api/v1/skills/{skillId}/versions/{versionId}/deprecate
POST   /api/v1/skills/{skillId}/versions/{versionId}/clone
GET    /api/v1/skills/{skillId}/versions/{versionId}/diff
```

## Files

```http
GET    /api/v1/skills/{skillId}/versions/{versionId}/files
GET    /api/v1/skills/{skillId}/versions/{versionId}/files/{path}
PUT    /api/v1/skills/{skillId}/versions/{versionId}/files/{path}
POST   /api/v1/skills/{skillId}/versions/{versionId}/files
DELETE /api/v1/skills/{skillId}/versions/{versionId}/files/{path}
```

## Imports

```http
POST   /api/v1/skills/imports
GET    /api/v1/skills/imports/{importId}
POST   /api/v1/skills/imports/{importId}/validate
POST   /api/v1/skills/imports/{importId}/create-draft
DELETE /api/v1/skills/imports/{importId}
```

## Interfaces

```http
GET    /api/v1/skill-interfaces
POST   /api/v1/skill-interfaces
GET    /api/v1/skill-interfaces/{interfaceId}
PATCH  /api/v1/skill-interfaces/{interfaceId}
GET    /api/v1/skill-interfaces/{interfaceId}/implementations
POST   /api/v1/skill-interfaces/{interfaceId}/validate
```

## Bindings

```http
GET    /api/v1/skill-bindings
POST   /api/v1/skill-bindings
GET    /api/v1/skill-bindings/{bindingId}
PATCH  /api/v1/skill-bindings/{bindingId}
DELETE /api/v1/skill-bindings/{bindingId}
POST   /api/v1/skill-bindings/resolve
POST   /api/v1/skill-bindings/simulate
```

## Tests

```http
POST   /api/v1/skills/{skillId}/versions/{versionId}/test-runs
GET    /api/v1/skills/{skillId}/versions/{versionId}/test-runs
GET    /api/v1/skill-test-runs/{testRunId}
POST   /api/v1/skill-test-runs/{testRunId}/cancel
GET    /api/v1/skill-test-runs/{testRunId}/events
```

---

# 22. API response examples

## Skill detail

```json
{
  "data": {
    "id": "sk-001",
    "key": "team-system-requirements",
    "name": "Team System Requirements Generator",
    "type": "TEAM",
    "status": "PUBLISHED",
    "owner": {"id": "team-payments", "name": "Payments Analysis"},
    "currentVersion": {
      "id": "skv-014",
      "semanticVersion": "1.4.0",
      "validationStatus": "PASSED"
    },
    "interfaces": ["analysis.system_requirements.generate@1"],
    "requiredCapabilities": ["context.search", "context.read", "artifact.patch"],
    "usage": {"playbooks": 6, "executions30d": 184}
  },
  "meta": {"requestId": "uuid"}
}
```

## Binding resolution

```json
{
  "data": {
    "interface": "analysis.system_requirements.generate@1",
    "selectedSkillVersionId": "skv-014",
    "bindingId": "bind-009",
    "reasons": [
      "PLAYBOOK_STEP binding matched",
      "Skill version is published",
      "Required capabilities are available",
      "No control restriction was violated"
    ],
    "alternatives": ["skv-010", "skv-core-003"]
  }
}
```

---

# 23. Kafka events

Topics:

```text
skill-catalog-events
skill-validation-events
skill-test-events
skill-binding-events
skill-run-events
```

Events:

```text
skill.created
skill.updated
skill.version.created
skill.version.validated
skill.version.published
skill.version.deprecated
skill.import.started
skill.import.completed
skill.test.started
skill.test.completed
skill.binding.created
skill.binding.resolved
skill.run.created
skill.run.started
skill.run.capability-requested
skill.run.completed
skill.run.failed
```

Event envelope must use the common platform event format.

---

# 24. Temporal integration

## Activities

```text
ResolveSkillBindingActivity
LoadSkillPackageActivity
BuildSkillContextActivity
CreateSkillSandboxActivity
RunSkillActivity
ValidateSkillOutputActivity
ApplyArtifactPatchActivity
PersistSkillMetricsActivity
DestroySkillSandboxActivity
```

## Retry policy

- validation errors: no retry;
- timeout: retry only if manifest policy allows;
- transient capability failure: retry with backoff;
- sandbox startup failure: retry once;
- invalid output contract: no automatic retry unless correction loop is configured.

## Heartbeats

Long-running runtimes must heartbeat with:

```text
phase
progress
lastCapabilityCall
logOffset
```

---

# 25. Permissions

Required permissions:

```text
skill.read
skill.create
skill.edit
skill.import
skill.validate
skill.test
skill.publish
skill.deprecate
skill.archive
skill.binding.read
skill.binding.manage
skill.interface.read
skill.interface.manage
skill.runtime.inspect
```

Recommended roles:

- SkillDeveloper;
- ProcessDesigner;
- WorkspaceAdmin;
- ComplianceOfficer;
- Viewer;
- Auditor.

Publication may require a separate approver from the author.

---

# 26. Audit requirements

Audit events are required for:

- creating a Skill;
- editing draft files;
- importing packages;
- validation waivers;
- publishing;
- deprecating;
- changing bindings;
- test execution;
- runtime execution;
- capability violations;
- sandbox failures;
- viewing restricted package contents.

Published package checksums must be stored in Audit.

---

# 27. Security requirements

- packages are untrusted input;
- imported archives must be scanned before extraction;
- no executable package file runs during validation;
- direct network access is denied by default;
- runtime secrets are injected only through references;
- package files must not contain credentials;
- capability calls are policy checked;
- data classification must be compatible with runtime provider;
- logs must redact sensitive values;
- output patches must be schema validated;
- prompt injection findings must be shown in validation reports.

---

# 28. Non-functional requirements

## Performance

- Skills catalog p95 < 500 ms;
- Skill detail p95 < 700 ms;
- draft file save p95 < 600 ms;
- validation start response < 300 ms;
- binding resolution p95 < 100 ms excluding database cold start;
- UI editor opens < 2 seconds for packages under 2 MB.

## Scale

- 50,000 Skill versions;
- 10,000 active Skills;
- 100,000 bindings;
- 1,000 concurrent Skill Runs;
- package size up to 20 MB by default;
- at least 300 abstract capability/provider mappings.

## Reliability

- idempotent publication;
- immutable packages;
- checksum verification;
- outbox for events;
- deterministic binding resolution;
- resilient test execution;
- isolated runtime cleanup.

---

# 29. Frontend structure

```text
frontend/src/pages/skills/
├── skills-catalog-page
├── skill-detail-page
├── skill-editor-page
├── skill-import-page
├── skill-interfaces-page
├── skill-test-lab-page
└── skill-bindings-page
```

Reusable entities:

```text
entities/skill
entities/skill-version
entities/skill-interface
entities/skill-binding
entities/skill-test-run
```

Required shared components:

- status pill;
- version badge;
- capability chip;
- interface badge;
- code editor;
- Markdown preview;
- YAML form editor;
- validation problem list;
- diff viewer;
- test run console;
- package file tree.

---

# 30. Backend structure

```text
backend/modules/skills/
├── domain/
│   ├── entities
│   ├── value-objects
│   ├── services
│   └── policies
├── application/
│   ├── commands
│   ├── queries
│   ├── validators
│   └── ports
├── infrastructure/
│   ├── persistence
│   ├── package-storage
│   ├── scanners
│   ├── runtimes
│   └── messaging
├── api/
└── tests/
```

Important domain services:

```text
SkillPackageParser
SkillValidator
SkillPublicationService
SkillInterfaceCompatibilityService
SkillBindingResolver
SkillRuntimeFactory
SkillSandboxManager
```

---

# 31. UI acceptance requirements

The UI prototype and production implementation must include:

1. Skills Catalog with filters and cards/table mode.
2. Skill Detail with all required tabs.
3. Full-screen Skill Editor.
4. Import wizard.
5. Skill Interfaces list.
6. Skill Test Lab.
7. Bindings table and resolution simulator.
8. Validation report with error navigation.
9. Version comparison.
10. Usage view.

The existing product visual style must be retained:

- dark navigation;
- light content surface;
- compact enterprise density;
- blue primary actions;
- status chips;
- clear fullscreen IDE mode.

---

# 32. Migration from current prototype

The coding agent must:

1. Inspect existing Skills page and related mock data.
2. Preserve reusable layout, cards, tables and navigation.
3. Replace static data with typed API clients.
4. Introduce Skill Interface and Skill Version concepts.
5. Separate catalog, detail, editor, imports and test lab routes.
6. Remove direct tool/MCP configuration from Skill forms.
7. Add capability chips instead of provider tool selectors.
8. Add version immutability.
9. Add validation and publication lifecycle.
10. Add tests before removing old code.

Do not break Playbook Skill Slot bindings during migration.

---

# 33. Implementation phases

## Phase 1: Catalog and domain model

- database migrations;
- Skill CRUD;
- version CRUD;
- catalog UI;
- detail UI;
- mock migration.

## Phase 2: Interfaces and contracts

- Skill Interface CRUD;
- schemas;
- compatibility validation;
- interface badges and filters.

## Phase 3: Editor and packages

- package storage;
- file API;
- editor;
- preview;
- immutable published versions.

## Phase 4: Imports and validation

- ZIP import;
- scanning;
- parser;
- validation pipeline;
- reports.

## Phase 5: Test Lab

- fixtures;
- mock capabilities;
- sandbox execution;
- assertions;
- logs.

## Phase 6: Bindings

- binding CRUD;
- precedence;
- simulator;
- integration with Playbook Designer.

## Phase 7: Production runtime

- Qwen Code CLI adapter;
- LLM prompt runtime;
- capability proxy;
- sandbox;
- Temporal activities;
- metrics and audit.

---

# 34. Mandatory first vertical slice

Implement one complete Skill:

```text
System Requirements Generator
```

It must:

- implement `analysis.system_requirements.generate@1`;
- accept `ProblemUnderstandingArtifact@1`;
- use `context.search`, `context.read`, `artifact.read`, `artifact.patch`;
- run through Qwen Code CLI or the configured MVP runtime;
- return `SystemRequirementsPatch@1`;
- pass static and sandbox validation;
- include at least three test cases;
- be bindable to a Playbook Skill Slot;
- execute inside a real Playbook Run;
- create Artifact Patch and Skill Run records;
- expose metrics in Skill Detail and Execution Inspector.

---

# 35. Definition of Done

The Skills subsystem is complete when:

- all database migrations exist;
- API is documented;
- catalog, detail and editor are functional;
- import security checks are implemented;
- published versions are immutable;
- interface compatibility is enforced;
- test lab works;
- binding resolution is deterministic;
- runtime uses Capability Gateway;
- direct MCP access is impossible;
- audit events are generated;
- RBAC is enforced;
- backend tests pass;
- frontend tests pass;
- end-to-end vertical slice passes;
- Docker Compose environment runs the feature;
- implementation status documentation is updated.

---

# 36. Forbidden shortcuts

The implementation must not:

- model a Skill as a full autonomous Agent;
- let Skills select arbitrary MCP tools;
- store only one mutable Skill definition;
- edit published versions;
- bind Playbooks directly to unversioned Skills;
- execute imported packages without scanning;
- allow direct unrestricted network access;
- bypass Capability Gateway;
- apply unvalidated artifact output;
- use production executions as the only testing mechanism;
- hide validation warnings;
- silently fall back to another Skill without recording the decision.

---

# 37. First task for the coding agent

1. Scan the existing repository.
2. Locate the current Skills page, models, routes and mock data.
3. Create `docs/SKILLS_CURRENT_STATE.md`.
4. Create `docs/SKILLS_MIGRATION_PLAN.md`.
5. Add an ADR: `docs/adr/ADR-002-skill-interface-and-versioning.md`.
6. Implement database entities for Skill, SkillVersion and SkillInterface.
7. Add read-only catalog and detail APIs.
8. Replace the prototype Skills page with API-backed data while preserving visual style.
9. Add routes for Skill Detail, Skill Editor, Interfaces, Imports and Test Lab.
10. Add tests.
11. Update `docs/IMPLEMENTATION_STATUS.md`.
12. Do not implement production runtime until the domain model and versioning tests pass.

---

End of document.
