# ADR-003: Skill Slots over concrete Skills

**Status:** Accepted  
**Date:** 2026-07-17

## Decision

Playbooks declare Skill Slots typed by Skill Interface (`analysis.system_requirements.generate@1`). Binding resolves to a Skill Implementation at compile/runtime. Incompatible interface versions are rejected at validate/publish.

## Consequences

Designer validates slot↔skill compatibility. Import of Anthropic SKILL.md must infer/propose an interface and flag direct MCP references.
