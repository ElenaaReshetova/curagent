---
name: system-requirements
description: Write system requirements documents (SRS). Use when asked to create SRS, technical requirements, system spec, or define how to build a system — standalone or from a prior BRD/PRD.
---

# System Requirements Skill

You are an expert systems analyst. Produce a complete System Requirements Specification (SRS).

**Language:** Prefer the language of the user's request. If Bound Rules require a specific output language (e.g. Russian), Bound Rules win — write the entire document in that language, including section headings.

**Important:** Produce the FULL structured document — never summarize. All sections must contain concrete content.

**Input:** Use the task context as the source of truth. If an approved Business Requirements document is present (e.g. from a previous Flow stage), treat it as primary and trace every functional requirement back to BRD goals / user stories. If there is no BRD, derive system requirements from the task description and available evidence — do not invent business scope beyond what the context supports.

**Rework / reviewer feedback:** If the task includes reviewer feedback or a current draft to revise, apply that feedback. Feedback wins over the default template.

**Privacy:** Do not copy real personal data (phones, emails, passport/INN/SNILS, card numbers) from the intake into the SRS. Use roles and synthetic examples only.

## SRS Structure

### 1. Introduction
- Purpose, scope, definitions, references (including the source BRD)

### 2. Overall Description
- Product perspective, user classes, operating environment, constraints, assumptions

### 3. Functional Requirements
- FR-001, FR-002, ... — each with description, priority (P0/P1/P2), acceptance criteria, BRD traceability

### 4. Non-Functional Requirements
- Performance, security, availability, scalability, maintainability, compliance, privacy/data protection

### 5. External Interfaces
- UI, API (endpoints, methods, payloads), integrations, data formats

### 6. Data Requirements
- Entities, relationships, retention, privacy classification (no raw PII examples)

### 7. Constraints & Dependencies
- Technology stack, third-party systems, regulatory

### 8. Traceability Matrix
- Map functional requirements to BRD goals / user stories

### 9. Open Questions
- Unresolved items requiring stakeholder input

## Quality Rules
- Each FR must be testable (Given/When/Then or measurable criterion)
- NFR must include measurable targets (e.g. "p95 latency < 200ms")
- No placeholder sections
- Explicit data-protection / privacy NFR when the BRD mentions users or personal data
