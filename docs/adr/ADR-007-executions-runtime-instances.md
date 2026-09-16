# ADR-007: Executions as frozen runtime instances

## Status

Accepted — 2026-07-17

## Context

Executions used legacy `Execution` entities with operator-centric fields. SRS requires FLOW-centric monitoring with snapshot, timeline, artifacts, evidence, and human checkpoints.

## Decision

1. Introduce `ExecutionRecord` with SRS statuses and immutable snapshot reference.
2. Catalog/Inspector consume enriched execution API; legacy store records merged into catalog.
3. Pause/cancel/resume update runtime state without editing Flow/Playbook definitions.
4. Start execution creates a queued instance (MVP stub).

## Consequences

- Dedicated Executions UI module replaces platform-pages executions view.
- Legacy `Execution` preserved for overview and backward-compatible endpoints.
- Compare/replay deferred to PR-2.
