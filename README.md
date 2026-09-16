# Governed AI Delivery Platform

Source of truth: [docs/requirements/CURSOR_GOVERNED_AI_PLATFORM_SPEC_V2.md](docs/requirements/CURSOR_GOVERNED_AI_PLATFORM_SPEC_V2.md)

```text
Flow → Playbook → Skill Slot → Skill → Capabilities → Gateway → Providers
```

## Quick start

```bash
docker compose up -d
# UI
open http://localhost:8092
```

## Menu (V2)

- **Dashboard**
- **Build:** Playbooks, Skills, Rules, Knowledge Spaces, Flows, Runtime Profiles
- **Run:** Executions, Human Checkpoints, Execution Inspector
- **Govern:** Controls, Integrations, Capability Registry, Audit

Agents are deprecated — use **Runtime Profiles**.

## Docs

- [CURRENT_STATE](docs/CURRENT_STATE.md)
- [TARGET_ARCHITECTURE](docs/TARGET_ARCHITECTURE.md)
- [MIGRATION_PLAN](docs/MIGRATION_PLAN.md)
- [IMPLEMENTATION_STATUS](docs/IMPLEMENTATION_STATUS.md)
