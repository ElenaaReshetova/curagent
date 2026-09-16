# System Requirements: Capabilities (Tool Gateway) и Resolver

**Версия:** 1.0  
**Дата:** 2026-07-12  
**Статус:** Approved for implementation  
**Компоненты:** Tool Gateway (Capabilities), Resolver  
**Платформа:** Enterprise Autonomous Agent Platform

---

## 1. Overview

Tool Gateway (Capabilities) — контрольная граница между **reasoning-слоем** автономных агентов и **execution-слоем** инструментов, адаптеров и внешних систем. Gateway обеспечивает единую точку доступа, registry capabilities, policy enforcement, dispatch orchestration, audit и нормализацию результатов.

**Resolver** — обязательный pre-execution компонент внутри Tool Gateway. Resolver принимает agent-proposed **ToolIntent**, выполняет refusal-first evaluation и возвращает либо canonical **ToolCall** для dispatch, либо typed **Denial**. Resolver не выполняет dispatch и не взаимодействует с внешними системами напрямую.

**Архитектурный intent:**
- strict separation: reasoning ≠ execution;
- refusal-first control model;
- typed request/response/denial envelopes;
- destructive actions только через approval + evidence + reversal contract;
- no silent bypass;
- replayability и auditability всех resolution decisions;
- adapters — thin integration boundary без policy authority.

---

## 2. Scope

### 2.1 In Scope

| Область | Описание |
|---------|----------|
| Tool Gateway | Registry, authorization surface, dispatch orchestration, result normalization, audit emission |
| Resolver | Pre-execution resolution, schema/evidence/approval validation, ToolCall/Denial generation |
| Integration contract | ToolIntent → ResolutionOutcome → ToolCall/Denial → AdapterRequest → NormalizedResult |
| Cross-cutting | Security policy hooks, telemetry, idempotency, tenant isolation |

### 2.2 Out of Scope

- UI для управления capabilities (отдельный deliverable — Workflow UI)
- Реализация конкретных adapters (Jira, Slack, Confluence и т.д.)
- LLM reasoning и skill selection
- Post-execution compensating saga orchestration (кроме metadata contract)
- Выбор конкретного policy engine vendor

---

## 3. Definitions

| Термин | Определение |
|--------|-------------|
| **Capability** | Зарегистрированная, versioned операция с уникальным ID, I/O schema, approval tier, side-effect class и adapter binding |
| **Capability Manifest** | Machine-readable описание capability |
| **ToolIntent** | Proposal от reasoning layer |
| **ToolCall** | Canonical executable command после Resolver ACCEPT |
| **Denial** | Typed refusal с machine-readable reason code |
| **Approval Tier** | `none`, `soft`, `hard`, `destructive` |
| **Side-effect Class** | `read`, `write`, `destructive`, `external_publish` |
| **Decision Record** | Immutable audit artifact resolution decision |

---

## 4. Functional Requirements: Capabilities / Tool Gateway

**CAP-001.** System shall maintain centralized Capability Registry as sole authoritative source of invokable operations.

**CAP-002.** Gateway shall assign each capability globally unique `capability_id` with explicit `manifest_version`.

**CAP-003.** Each manifest shall declare input and output JSON Schema.

**CAP-004.** Each manifest shall declare `approval_tier` and `side_effect_class`.

**CAP-005.** Each manifest shall declare `adapter_binding` without embedding policy rules.

**CAP-006.** Registry shall support lifecycle states: `draft`, `published`, `deprecated`, `disabled`.

**CAP-007.** Gateway shall reject unknown/disabled capabilities with typed Denial.

**CAP-008.** Gateway shall enforce visibility filtering per tenant/caller/skill/playbook.

**CAP-009.** Gateway shall support policy-based access with recorded `policy_version`.

**CAP-010.** Gateway shall enforce tenant-aware access; cross-tenant requests Denied.

**CAP-011.** Gateway shall accept requests exclusively via typed ToolIntent envelope.

**CAP-012.** Gateway shall return outcomes via typed ResolutionOutcome envelope.

**CAP-013.** Gateway shall normalize adapter responses to capability output schema.

**CAP-014.** Gateway shall route accepted ToolCall exclusively through Dispatcher without re-authorization.

**CAP-015.** Gateway shall support protocol abstraction via adapter binding.

**CAP-016.** Gateway shall support per-capability dispatch timeout.

**CAP-017.** Gateway may support async dispatch mode per manifest (optional).

**CAP-018.** Gateway shall require idempotency_key for write/destructive/external_publish side effects.

**CAP-019.** Gateway shall deduplicate requests with same tenant+capability+idempotency_key within TTL.

**CAP-020.** Gateway shall not deduplicate destructive capabilities unless manifest declares idempotent=true.

**CAP-021.** Gateway shall block destructive dispatch without valid approval and evidence.

**CAP-022.** Destructive manifests shall declare reversal contract.

**CAP-023.** Gateway shall persist reversal metadata in Decision Record.

**CAP-024.** Gateway shall support controlled hot reload of manifests and policy config.

**CAP-025.** Gateway shall log all Denials without silent drop.

**CAP-026.** Gateway shall emit structured telemetry with correlation IDs.

---

## 5. Functional Requirements: Resolver

**RES-001.** Resolver shall execute before any dispatch for every ToolIntent.

**RES-002.** Resolver shall implement refusal-first model (default Deny).

**RES-003.** Resolver shall be stateless; state read from registry/policy/evidence stores.

**RES-004.** Resolver shall produce deterministic ResolutionOutcome per intent+snapshot.

**RES-005.** Resolver shall perform capability lookup by capability_id.

**RES-006.** Resolver shall perform visibility check; invisible → `CAPABILITY_NOT_VISIBLE`.

**RES-007.** Resolver shall evaluate policy rules before ACCEPT.

**RES-008.** Resolver shall validate inputs against input schema → `SCHEMA_VALIDATION_FAILED`.

**RES-009.** Resolver shall validate execution mode compatibility.

**RES-010.** Resolver shall require approval artifact for soft/hard/destructive tiers.

**RES-011.** Resolver shall validate approval artifact integrity and scope.

**RES-012.** Resolver shall require evidence bundle for hard/destructive tiers.

**RES-013.** Resolver shall validate evidence freshness → `EVIDENCE_STALE`.

**RES-014.** Resolver shall Deny missing evidence → `EVIDENCE_MISSING`.

**RES-015.** Destructive tier requires reversal contract in manifest.

**RES-016.** On ACCEPT, Resolver shall generate canonical ToolCall.

**RES-017.** On DENY, Resolver shall generate typed Denial with denial_code enum.

**RES-018.** Denial shall not be unstructured exception text only.

**RES-019.** Resolver shall attach retryability hints to Denial.

**RES-020.** Resolver shall emit Decision Record for every ACCEPT/DENY.

**RES-021.** Decision Records shall be version-aware (manifest_version, policy_version).

**RES-022.** System shall support replay of Resolver decision from Decision Record.

**RES-023.** Resolver shall not invoke adapters or cause side effects.

---

## 6. Security and Policy Requirements

**SEC-001.** Least privilege visibility per caller role.

**SEC-002.** Reasoning layer shall not invoke adapters directly.

**SEC-003.** Direct adapter access from reasoning network is policy violation.

**SEC-004.** Destructive actions require approval + evidence + reversal contract.

**SEC-005.** Invalid/expired/cross-tenant approval → Deny.

**SEC-006.** Missing required evidence → Deny.

**SEC-007.** Policy-as-code compatibility with versioned external rules.

**SEC-008.** Tenant isolation enforced at Resolver and Gateway.

**SEC-009.** Caller identity propagates through full chain.

**SEC-010.** Secrets redacted in audit/telemetry.

**SEC-011.** Tampered intent → `INTEGRITY_CHECK_FAILED`.

---

## 7. Auditability and Observability Requirements

**AUD-001.** Full Decision Record persisted before dispatch (ACCEPT) or before caller response (DENY).

**AUD-002.** Denied requests included in audit trail with equal fidelity.

**AUD-003.** Structured logging with stable field names.

**AUD-004.** Correlation IDs propagated end-to-end.

**AUD-005.** End-to-end traceability from task_id to result.

**AUD-006.** Audit replay support for compliance.

**AUD-007.** Denial explainability payload for operators.

**AUD-008.** Metrics: denied/accepted totals, latency, idempotent hits.

---

## 8. Reliability and Operational Requirements

**REL-001.** Resolver path stateless and horizontally scalable.

**REL-002.** Idempotency store strongly consistent or conflict-free dedup.

**REL-003.** Adapter unavailability → typed error, no audit loss.

**REL-004.** Per-capability timeout policies.

**REL-005.** Retry hooks at dispatch; re-entry must pass Resolver.

**REL-006.** Execution failure record linked to Decision Record.

**REL-007.** At-most-once side effect for idempotent operations.

**REL-008.** Hot reload uses atomic snapshot per request.

**REL-009.** Registry unavailable → fail closed `REGISTRY_UNAVAILABLE`.

---

## 9. Boundary and Responsibility Model

| Layer | Responsible for | NOT responsible for |
|-------|-----------------|---------------------|
| Reasoning | ToolIntent proposal | Policy, dispatch, registry |
| Gateway API | Ingress, orchestration, audit | Pre-dispatch auth (→ Resolver) |
| Resolver | Refusal-first, ToolCall/Denial | Dispatch, adapters |
| Dispatcher | Adapter invocation | Authorization |
| Adapter | Protocol translation | Policy decisions |
| Rollback layer | Compensating flows | Pre-execution auth |

**BND-001–BND-006.** See implementation guide in `src/tool_gateway/README.md`.

---

## 10. Acceptance Criteria

**ACC-001.** Direct adapter bypass blocked (SEC-002).  
**ACC-002.** 100% ToolIntents pass Resolver (RES-001, AUD-001).  
**ACC-003.** Unknown capability → `CAPABILITY_NOT_FOUND` (CAP-007).  
**ACC-004.** Destructive without approval/evidence Denied (RES-010–014).  
**ACC-005.** Idempotency dedup works (CAP-019).  
**ACC-006.** Schema invalid → `SCHEMA_VALIDATION_FAILED` (RES-008).  
**ACC-007.** Stale evidence → `EVIDENCE_STALE` (RES-013).  
**ACC-008.** Decision Record has version fields (RES-020).  
**ACC-009.** Hot reload atomic snapshot (CAP-024).  
**ACC-010.** Cross-tenant Denied (CAP-010).  
**ACC-011.** Denial explainability available (AUD-007).  
**ACC-012.** Adapter failure audit persisted (REL-006).  
**ACC-013.** Dispatcher rejects ToolCall without decision_id (BND-003).  
**ACC-014.** Registry down → `REGISTRY_UNAVAILABLE` (REL-009).

---

## 11. Open Questions

| ID | Question |
|----|----------|
| OQ-1 | Per-tenant Gateway vs shared cluster |
| OQ-2 | Decision Record store: DB vs event bus |
| OQ-3 | Approval artifact format |
| OQ-4 | Hot reload consistency window |
| OQ-5 | Caller identity for system playbook steps |
| OQ-6 | Evidence TTL precedence |
| OQ-7 | Async dispatch for long-running capabilities |
