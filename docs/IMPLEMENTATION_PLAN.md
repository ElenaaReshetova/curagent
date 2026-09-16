# IMPLEMENTATION_PLAN — Governed Playbooks with Pluggable Skills

**Source of truth:** [CURSOR_GOVERNED_PDLC_PLATFORM_SPEC.md](requirements/CURSOR_GOVERNED_PDLC_PLATFORM_SPEC.md)  
**Design:** сохранить текущий UI (colors, sidebar, cards, typography).

## Phase 0 — Assessment (done when CURRENT_STATE + STATUS + ADRs существуют)

- [x] Inventory repo
- [x] CURRENT_STATE.md
- [x] IMPLEMENTATION_PLAN.md
- [x] IMPLEMENTATION_STATUS.md
- [x] ADRs
- [ ] Test baseline note

## Phase 1 — Product shell (same design)

Nav remap (Control Plane):

```text
Обзор → Agents → Playbooks → Playbook Designer → Skills
→ Knowledge Spaces → Rules → Flows → Controls
→ Capabilities (MCP) → Integrations → Models → Users → Audit
```

Runtime:

```text
Executions → Human Checkpoints → Activity → Queue → Events
```

Legacy (скрыто / read-only): Operators, Blueprints, Contracts.

Files:

- `src/workflow_ui/static/index.html`
- `overview.js`, `platform-pages.js`, `app.js`
- `styles.css` — только дополнения, без смены tokens

## Phase 2 — Configuration core

New entities in `src/platform/domain/`:

- Agent, FlowDefinition, PlaybookDefinition (governed)
- SkillInterface, SkillImplementation, RuleSet
- ControlPack, KnowledgeSpace, Capability
- CaseContext fields on Execution; RunContract (hidden)

Store: `config/platform/governed/*.json` + migration from operators/policies.

API: `/api/v1/agents|flows|skills|skill-interfaces|rules|controls|knowledge-spaces|…`

## Phase 3+ — per spec sections 30

Playbook Designer locked nodes → Skills import → Controls → Knowledge/Gateway → Runtime → Qwen → Supervision → Flow orchestration → Inspector → Hardening.

## First vertical slice (priority after Phase 2 shell)

**System Requirements from Jira/Slack** — seed playbook with Control Spine + skill slots + capability-only skill runtime stub.

## Quality gates

```bash
pytest tests/test_platform_*.py
# later: ruff, mypy, frontend lint when React lands
```
