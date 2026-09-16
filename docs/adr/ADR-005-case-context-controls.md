# ADR-005: Case Context and Control Precedence

**Status:** Accepted  
**Date:** 2026-07-17

## Decision

- **Case Context** (Task Charter, Stage Brief, Context Snapshot, Artifacts, Evidence) is the structured handoff between skills/stages.
- **Controls** outrank Rules, Skill prompts, and Adaptive Zones. Hard controls cannot be removed from Control Spine. Controlled controls need approved Waiver.
- **Temporal** remains the durable executor; Run Contract is compiled once and immutable for the run.

## Consequences

Execution Inspector must show Case Context / Evidence / Controls decisions. Rules editors cannot expose permission toggles.
