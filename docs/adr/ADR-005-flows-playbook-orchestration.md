# ADR-005: Flows as Playbook orchestration

## Status

Accepted — 2026-07-17

## Context

Flows were flat `FlowDefinition` graphs. SRS requires versioned end-to-end routes across Playbooks with routing, simulation, and designer — without embedding Skill prompts or MCP tools.

## Decision

1. Introduce `FlowRecord` + `FlowVersion` with typed stage nodes referencing Playbook keys.
2. Flow selects Playbooks; Skills stay inside Playbooks.
3. Routing preview maps work-item context → Flow version.
4. Designer is a visual shell in PR-1; full graph edit in PR-3.

## Consequences

- Catalog/Detail/Designer/Routing consume versioned Flow API.
- Legacy `FlowDefinition` remains until cleanup.
- Temporal execution deferred to later PRs.
