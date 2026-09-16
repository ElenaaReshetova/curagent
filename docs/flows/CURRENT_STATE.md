# Flows — CURRENT STATE

**Date:** 2026-07-18  
**Spec:** [FLOWS_SYSTEM_REQUIREMENTS.md](FLOWS_SYSTEM_REQUIREMENTS.md)  
**UI:** `src/workflow_ui/static/flows/`

## After Platform UX Simplification

| Area | Location | Notes |
|------|----------|-------|
| Nav | Build → Flows (first) | Flow-first IA |
| Catalog / Detail / Designer / Routing | `flows/module.js` | Cards + drawer + designer + route preview |
| Graph persist | `PUT .../versions/{id}/graph` | Draft save with revision |
| Publish | `POST .../versions/{id}/publish` | Immutable snapshot; clones next draft |
| Domain | `src/platform/flows/` | `FlowRecord` + `FlowVersion` with stages |
| Deep-links | Playbook / Knowledge Open buttons | Via `PlatformUtil.navigateTo` |

## Principle

Flow orchestrates Playbook stages. It does not run Skills or embed MCP tools.
Executions use the published version snapshot — editing drafts does not change running flows.
