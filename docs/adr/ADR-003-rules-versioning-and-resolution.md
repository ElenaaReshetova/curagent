# ADR-003: Rules versioning and scope resolution

## Status

Accepted — 2026-07-17

## Context

Rules were flat `RuleSet` records. SRS requires versioned Rules with scope inheritance, conflict detection, and effective-bundle resolution for Skill runs — without weakening Controls.

## Decision

1. Introduce `RuleRecord` + `RuleVersion` (JSON store first).
2. Categories: STYLE, TERMINOLOGY, FORMAT, NAMING, DOMAIN, QUALITY, CODING_STANDARD, DOCUMENT_TEMPLATE, OUTPUT_CONSTRAINT, LANGUAGE.
3. Scopes: PLATFORM → ORGANIZATION → WORKSPACE → DOMAIN → TEAM → PLAYBOOK → SKILL (higher weight wins).
4. On conflict with Controls, Control always wins.
5. Validation rejects MCP tool refs and instructions to bypass Controls.

## Consequences

- Catalog/Detail/Preview consume versioned API.
- Legacy `RuleSet` remains for overview until cleanup.
- Full runtime freeze deferred to PR-6.
