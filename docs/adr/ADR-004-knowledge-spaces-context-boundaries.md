# ADR-004: Knowledge Spaces as context boundaries

## Status

Accepted — 2026-07-17

## Context

Skills must remain provider-neutral. Binding Skills directly to Jira/Slack/Confluence/MCP tools breaks reuse across domains.

## Decision

1. Knowledge Space is a managed context boundary with typed source bindings.
2. Skills request `context.search` / `context.read`; Context Broker resolves via Knowledge Space.
3. Source bindings reference integrations + selectors, not raw MCP tool names in Skill packages.
4. Search playground validates resolution without side effects (MVP mock ranking).

## Consequences

- Catalog/Detail/Playground consume versioned KS API.
- Legacy flat `KnowledgeSpace` remains until migration cleanup.
- Full Context Broker runtime deferred to PR-4+.
