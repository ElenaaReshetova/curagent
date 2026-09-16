# ADR-006: Runtime Profiles as versioned execution config

## Status

Accepted — 2026-07-17

## Context

Runtime Profiles were flat `RuntimeProfile` entities migrated from Agents. SRS requires versioned provider/model/sandbox/capability configuration without embedding Skill or Playbook logic.

## Decision

1. Introduce `RuntimeProfileRecord` + `RuntimeProfileVersion` with typed provider, limits, sandbox, capabilities.
2. Secrets stored as references only (`vault://`, `secret://`), never inline values.
3. Effective runtime resolution preview for Flow/Playbook/Skill context.
4. Editor is a visual shell in PR-1; full persistence in PR-3.

## Consequences

- Catalog/Detail/Editor consume versioned API.
- Legacy `RuntimeProfile` remains for overview until cleanup.
- Provider connectivity test returns stub until real adapters land.
