# Human Checkpoints — CURRENT STATE

**Date:** 2026-07-17  
**Spec:** `HUMAN_CHECKPOINTS_SYSTEM_REQUIREMENTS.md`  
**UI:** `src/workflow_ui/static/human_checkpoints/`

## After PR-1

| Area | Location | Notes |
|------|----------|-------|
| Nav | `data-view=checkpoints` | Dedicated module |
| Inbox / Detail | `human_checkpoints/module.js` | Queue, review shell, decision panel |
| Domain | `src/platform/human_checkpoints/` | `HumanCheckpointRecord`, metrics, decision options |
| API | `/api/v1/human-checkpoints*` | Catalog, detail, claim, start review, decisions |
| Legacy | `/api/v1/approvals`, `/api/v1/checkpoints` | Compatibility aliases |

## Principle

Human Checkpoint is a governed runtime stop where execution waits for a human decision with explicit context, SLA, and audit trail.
