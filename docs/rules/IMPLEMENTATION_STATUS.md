# Rules — IMPLEMENTATION STATUS

**Updated:** 2026-07-17

| PR | Status | Notes |
|----|--------|-------|
| PR-1 Navigation & screens | done | Catalog / Detail drawer / Resolve preview |
| PR-2 Persistence | partial | JSON `rule_records` / `rule_versions` |
| PR-3 Editor | pending | Content tab read-only; autosave later |
| PR-4 Scope / conflicts | partial | Resolve preview MVP; Control wins |
| PR-5 Trace / compare | stub | Trace UI placeholder |
| PR-6 Execution integration | partial | Bound `rule_keys` / playbook bindings resolve into skill executor prompt + artifact provenance |

## Spec / ADR

- `docs/rules/RULES_SYSTEM_REQUIREMENTS.md`
- `docs/adr/ADR-003-rules-versioning-and-resolution.md`

## PR-1 deliverables

- Build → Rules catalog (metrics, filters, table, health)
- Detail drawer tabs: Overview, Content, Scope, Usage, Versions, Validation
- Create draft modal
- Effective rules resolve preview
- No MCP / Control-bypass instructions
- Tests: `tests/test_rules_module.py`
