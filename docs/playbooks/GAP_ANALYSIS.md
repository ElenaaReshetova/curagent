# Playbooks — GAP ANALYSIS

| Requirement | Current (PR-1) | Remaining |
|-------------|----------------|-----------|
| Catalog metrics / filters / table | Done | — |
| Detail tabs | Done (executions placeholder) | Wire real executions |
| Fullscreen Designer | Done (read canvas) | PR-3 drag/edit/autosave |
| PlaybookVersion lifecycle | JSON DRAFT/PUBLISH | SQL + deprecate/archive |
| Graph validate/publish | Done | Optimistic locking polish |
| Skill bindings by interface | Displayed | Resolver API |
| Control spine locked nodes | Seeded immutable flags | Enforce on edit |
| Simulation | MVP summary | Full no-side-effect sim |
| No Agents ownership | Done | Keep |

## Prototype mapping

| Prototype | Platform |
|-----------|----------|
| Catalog | `#pb-catalog-view` in `#view-playbooks-list` |
| Detail | `#pb-detail-view` |
| Designer fullscreen | `#pb-designer-view` |
| Create modal | `#pb-create-modal` |
