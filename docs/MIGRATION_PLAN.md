# MIGRATION_PLAN — V2

## Phase 0 — Audit (this iteration)

Docs + ADR-001 remove Agent entity.

## Phase 1 — Application Shell (this iteration / first PR)

1. Remap sidebar to Dashboard / Build / Run / Govern.
2. Remove Agents from primary nav (keep hidden legacy view + read-only API).
3. Add Runtime Profiles page + `/api/v1/runtime-profiles`.
4. Migrate seed from `agents.json` model_profile_key → RuntimeProfile.
5. Keep CSS tokens; bump asset cache.
6. Route/API tests; do not break Playbook Designer.

## Phase 2+

Per V2 §15: PostgreSQL/workspace → Playbooks versions/graph → Skills import → Rules/KS/Controls → Flows+Profiles → Execution runtime → Artifacts → Approvals → Capability Gateway → E2E vertical slice.

## Agent → Runtime Profile mapping

| Agent field | Destination |
|-------------|-------------|
| model_profile_key | RuntimeProfile.model (+ provider from models catalog) |
| supervision_profile_key | note in profile.limits_json / later supervision policy |
| ingress_bindings | Flow triggers / Router (Phase 6–7) |
| allowed_playbook_keys / flows | Flow + routing rules |
| skill_bindings | SkillBinding scope (Phase 4) |
| knowledge_space_bindings | Execution routing / Flow defaults |

## Deprecation

- `/api/v1/agents` — read-only compatibility until Phase 6.
- `view-agents` — hidden, not deleted.
- `config/platform/agents.json` — retained read-only.
