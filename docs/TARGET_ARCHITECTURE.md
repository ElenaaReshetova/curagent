# TARGET_ARCHITECTURE — Governed AI Delivery Platform V2

**Spec:** CURSOR_GOVERNED_AI_PLATFORM_SPEC_V2.md

## Product formula

```text
External Work Item → Routing → Flow → Playbook → Steps → Skill Slots
  → Skill Implementations → Capabilities → Capability Gateway → Providers/MCP
```

Influencers: Rules, Controls, Knowledge Spaces, Runtime Profile, Human Supervision, Case Context.

## UI IA (normative §20)

```text
Dashboard
Build: Flows, Playbooks, Skills, Rules, Knowledge Spaces, Runtime Profiles
Run: Executions, Human Checkpoints, Execution Inspector
Govern: Controls, Integrations, Capability Registry, Audit
```

Setup path (Dashboard): Integrations → Capabilities → Rules → Skills → Playbooks → Flows.

Playbook Designer — не top-level menu; доступ из Playbooks (Open Designer).

## Backend modules (target)

Workspace → Config (Playbooks/Skills/Rules/KS/Controls/Flows/RuntimeProfiles) → Execution Service → Temporal → Skill Runtime → Context Broker → Capability Gateway → Audit.

## Runtime Profile (replaces Agent)

Technical execution config only: provider, model, fallbacks, generation, sandbox, concurrency, retries, cost/context limits, secrets ref, region.  
Does **not** own ingress routing or playbook allow-lists (those belong to Flow/Router).
