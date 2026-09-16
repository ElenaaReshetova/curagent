# ADR-002: Skill Interface and Versioning

## Status

Accepted — 2026-07-17

## Context

Skills were stored as flat `SkillImplementation` records. The Skills SRS requires stable Skill Interfaces, immutable published versions, and provider-neutral capabilities (no direct MCP tools).

## Decision

1. Introduce `SkillRecord` + `SkillVersion` (JSON store first; SQL later).
2. Playbooks bind to **interface keys**, never to unversioned skills or MCP tools.
3. Published versions are immutable; edits go to a new draft.
4. Validation rejects direct MCP/provider tool references in SKILL.md / manifest.
5. Keep legacy `SkillImplementation` for overview/seed until Phase 2 cleanup.

## Consequences

- Catalog/Detail/Editor UI consume the versioned API.
- Legacy `POST /skills/{id}/validate` remains for old records.
- Runtime binding resolution is deferred to Phase 6.
