# Playbook Designer — CURRENT STATE

**Date:** 2026-07-17  
**Spec:** PLAYBOOK_DESIGNER_IMPLEMENTATION_SPEC.md (external package)  
**Module:** `src/workflow_ui/static/playbooks/`

## 1. Current route

- Shell view: `#view-playbooks-list`
- Module root: `#playbooks-module`
- Screens: Catalog (`#pb-catalog-view`) → Detail (`#pb-detail-view`) → Designer (`#pb-designer-view`)

## 2. Component tree

```text
#playbooks-module
├── #pb-catalog-view
├── #pb-detail-view
│   ├── tabs (Обзор / Привязки Skills / Привязки Rules / Controls / Версии / Запуски)
│   └── Open Designer
└── #pb-designer-view
    ├── .pb-designer-top (title, Canvas|DSL, save status, Validate, Publish)
    └── .pb-designer-grid
        ├── .pb-palette (node type buttons + problems)
        ├── .pb-canvas-wrap
        │   ├── #pb-canvas (shared FlowCanvas)
        │   └── #pb-dsl-panel (JSON DSL editor)
        └── .pb-inspector (selected node fields)
```

Single controller: `PlaybooksModule` in `module.js` (vanilla IIFE). No React, no React Flow, no Zustand/Redux.

## 3. Graph library

Shared `window.FlowCanvas` (`static/flow-canvas.js`) — same engine as Flow Designer. Playbook mounts it on `#pb-canvas` with domain adapters `toFlowGraph` / `fromFlowGraph`. DSL mode edits the same graph document as pretty-printed JSON.

## 4. Graph data shape

```json
{
  "schema_version": "1",
  "nodes": [
    {
      "key": "generate-requirements",
      "type": "SKILL_SLOT",
      "name": "Generate requirements",
      "interface_key": "analysis.system_requirements.generate@1",
      "immutable": false,
      "control_source": null,
      "config": {},
      "position": { "x": 40, "y": 120 }
    }
  ],
  "edges": [
    {
      "key": "e0",
      "source": "start",
      "target": "generate-requirements",
      "condition": null,
      "priority": 100,
      "config": {}
    }
  ]
}
```

Models: `PlaybookNode`, `PlaybookEdge`, `PlaybookGraph` in `src/platform/playbooks/models.py`.  
Version carries `revision`, `checksum`, `status`, bindings, validation report.

## 5. Mock / fake behavior (pre PR-1 Designer persistence)

| Item | Status |
|------|--------|
| localStorage as primary storage | Not used |
| Fake `setTimeout` save | Not present |
| Autosave label | Static `"Draft graph"` (no API call) |
| Palette add | Dead buttons (no handlers) |
| Apply changes | Disabled (`title="PR-3"`) |
| Canvas edges | Previously ignored; rendered by node array order |
| Node positions | Model field existed; UI ignored it |
| Simulation | Real endpoint but summary-only (not a full test run) |

## 6. Fake actions removed / fixed in Designer PR-1

- Production save now hits `PUT .../graph` with revision.
- Autosave states: UNSAVED / SAVING / SAVED / SAVE_FAILED / CONFLICT / OFFLINE.
- No second unsynchronized graph model; designer state is the draft graph document.

## 7. Existing API endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/playbooks` | Catalog |
| GET | `/api/v1/playbooks/{id}` | Detail + embedded versions |
| POST | `/api/v1/playbooks` | Create |
| GET | `/api/v1/playbooks/{id}/versions` | List |
| POST | `/api/v1/playbooks/{id}/versions` | Create draft |
| GET | `/api/v1/playbooks/{id}/versions/{vid}` | Version |
| GET | `/api/v1/playbooks/{id}/versions/{vid}/graph` | Graph + revision |
| PUT | `/api/v1/playbooks/{id}/versions/{vid}/graph` | Save + optimistic lock |
| GET | `/api/v1/playbooks/{id}/versions/{vid}/designer` | Aggregate load (Designer PR-1) |
| POST | `.../validate` | Graph validation |
| POST | `.../publish` | Publish draft |
| POST | `.../simulations` | MVP simulation summary |

## 8. Missing backend endpoints (later PRs)

- PATCH version with `If-Match` header (spec preferred; body revision used for now)
- Node schema registry `/playbook-node-types`
- Compile preview, test-runs, dependencies, compare
- Structured graph transactions / operation log

## 9. Reusable components

- `PlatformUtil.fetchJSON` / `esc` / `toast`
- Skills module draft save + revision pattern (`skills/module.js`)
- Playbook validation engine (`playbooks/validation.py`)

## 10. Technical debt

- Node type names differ from full designer spec (e.g. `SKILL_SLOT` vs `SKILL`)
- Linear seed graphs lack positions until first layout pass
- No workspace isolation beyond `workspace_id` field on records
- Simulation is not a real sandbox execution

## 11. Risks

- Concurrent editors only protected by revision; conflict UX must not silent-overwrite
- Large graphs: current DOM canvas will need virtualization later
- Palette may show types without full runtime handlers until Node Schema Registry PR

## 12. Migration plan

| Stage | Focus |
|-------|--------|
| Designer PR-1 | Real load/save, autosave, conflict, positions, edges, ACTIVE read-only |
| PR-2 | Node schema registry, real palette, dynamic ports |
| PR-3 | Full graph editing (undo/redo, copy/paste, auto layout) |
| PR-4 | Backend + fast validation UX |
| PR-5 | Real selectors (Skills, Controls, …) |
| PR-6 | Mapping editors |
| PR-7 | Test run |
| PR-8 | Activation / compare / clone |
| PR-9 | Hardening (a11y, perf, audit, remove remaining mocks) |
