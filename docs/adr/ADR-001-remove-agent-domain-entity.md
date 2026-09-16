# ADR-001: Remove Agent as a domain entity

**Status:** Accepted  
**Date:** 2026-07-17  
**Spec:** CURSOR_GOVERNED_AI_PLATFORM_SPEC_V2.md §1, §5.9, §17, §18

## Context

The prototype exposed **Agents** as a first-class Control Plane entity (ingress, playbook allow-lists, skill bindings, model profile). V2 forbids Agents as a central domain entity and introduces **Runtime Profiles** for technical execution configuration.

## Decision

1. Remove Agents from the primary product navigation and documentation.
2. Introduce **RuntimeProfile** as the replacement for LLM/provider/limits/sandbox configuration.
3. Keep `Agent` model + `/api/v1/agents` as **read-only legacy** until routing/bindings are fully migrated to Flow + SkillBinding + Router.
4. Do not delete Agent files in Phase 1; hide UI and stop seeding Agents as a primary concept.
5. Migrate seed: `requirements-agent.model_profile_key` → Runtime Profile `default-gigachat` (or equivalent).

## Consequences

- UI menu matches V2 §20 (Build / Run / Govern).
- Later phases must not add Agent-centric features.
- Ingress/routing configuration moves to Flows and Execution routing services.
