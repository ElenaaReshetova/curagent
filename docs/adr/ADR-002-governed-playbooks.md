# ADR-002: Governed Playbooks with Pluggable Skills

**Status:** Accepted  
**Date:** 2026-07-17  
**Spec:** CURSOR_GOVERNED_PDLC_PLATFORM_SPEC.md

## Context

Предыдущая модель (Operators / Blueprints / visible Execution Contracts) не отражает продуктовую формулу: Flow → Playbook → Skill Slot → Skill → Rules → Controls → Knowledge → Capability Gateway.

## Decision

1. **Playbook** = governed stage process with Control Spine + Skill Slots (not free MCP graph).
2. **Skill Slot** binds to **Skill Interface**; **Skill Implementation** is pluggable.
3. **Operator** legacy maps to Skill Interface/Implementation or deterministic internal action.
4. **Policy Pack** → **Control Pack** with precedence over user rules.
5. **Execution Contract** → immutable **Run Contract**, not a primary UI entity.
6. **Capability Gateway** (existing tool_gateway) is the only path to MCP tools.
7. Keep static HTML/CSS shell; evolve pages in place (no React rewrite in this iteration).

## Consequences

- Nav and APIs rename; legacy endpoints remain read-only adapters.
- Flow Studio becomes Playbook Designer; Flows get a separate catalog.
- Skills must not reference raw MCP tool names.
