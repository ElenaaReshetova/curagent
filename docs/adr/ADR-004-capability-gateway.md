# ADR-004: Capability Gateway

**Status:** Accepted  
**Date:** 2026-07-17

## Decision

Extend `src/tool_gateway` as Capability Gateway. Skills request stable capabilities (`work_item.read`, `context.search`, …). MCP tools are discovered, fingerprinted, quarantined, mapped to capabilities, and resolved by context. LLM never sees raw MCP tool catalogs.

## Consequences

Existing capability manifests remain the contract surface. New MCP tools start in quarantine until approved.
