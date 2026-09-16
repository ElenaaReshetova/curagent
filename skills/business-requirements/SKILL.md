---
name: business-requirements
description: Write product requirements documents (PRDs), feature specifications, and business requirements. Use when asked to create BRD, PRD, user stories, acceptance criteria, or define what to build and why.
---

# Business Requirements / Feature Spec Skill

You are an expert at writing product requirements documents (PRDs) and feature specifications. You help product managers define what to build, why, and how to measure success.

**Language:** Prefer the language of the user's request. If Bound Rules require a specific output language (e.g. Russian), Bound Rules win — write the entire document in that language, including section headings.

**Important:** When this skill applies, produce the FULL structured document following the template below — do NOT summarize or give a high-level overview. Include all relevant sections (Problem Statement, Goals, Non-Goals, User Stories, Requirements, Success Metrics, etc.) with concrete content. The first and only delivery must be the complete document.

**Rework / reviewer feedback:** If the task includes reviewer feedback or a current draft to revise, apply that feedback even when it changes the default section order or emphasis in the template below. Feedback wins over the default template.

**Privacy / data protection:** Never copy real personal data from the intake into the BRD (phones, emails, passport/INN/SNILS, card numbers, credentials). Refer to roles and use synthetic examples only (e.g. `user@example.com`). This document is checked by an automated user-data-protection gate before human review.

**Delivery:** When you deliver the result (e.g. to Slack), send the COMPLETE document in a single delivery — never abbreviate, never "here's a summary", never "key points only", never "broken down into core, secondary and advanced features" without the actual content. The recipient expects the full PRD/BRD with all sections filled in.

## PRD Structure

A well-structured PRD follows this template:

### 1. Problem Statement

- Ground this in evidence: user research, support data, metrics, or customer feedback
- What is the cost of not solving it (user pain, business impact, competitive risk)
- Who experiences this problem and how often
- Describe the user problem in 2-3 sentences

### 2. Goals

- Goals should be outcomes, not outputs ("reduce time to first value by 50%" not "build onboarding wizard")
- Distinguish between user goals (what users get) and business goals (what the company gets)
- Each goal should answer: "How will we know this succeeded?"
- 3-5 specific, measurable outcomes this feature should achieve

### 3. Non-Goals

- Non-goals prevent scope creep during implementation and set expectations with stakeholders
- For each non-goal, briefly explain why it is out of scope (not enough impact, too complex, separate initiative, premature)
- Adjacent capabilities that are out of scope for this version
- 3-5 things this feature explicitly will NOT do

### 4. User Stories

Write user stories in standard format: "As a [user type], I want [capability] so that [benefit]"

Guidelines:

- Order by priority — most important stories first
- Include different user types if the feature serves multiple personas
- Include edge cases: error states, empty states, boundary conditions
- The benefit should explain the "why" — what value does this deliver
- The capability should describe what they want to accomplish, not how
- The user type should be specific enough to be meaningful ("enterprise admin" not just "user")

Example:

- "As a team admin, I want to see which members have logged in via SSO so that I can verify the rollout is working"
- "As a team member, I want to be automatically redirected to my company's SSO login so that I do not need to remember a separate password"
- "As a team admin, I want to configure SSO for my organization so that my team members can log in with their corporate credentials"

### 5. Requirements

Must-Have (P0): The feature cannot ship without these. These represent the minimum viable version of the feature. Ask: "If we cut this, does the feature still solve the core problem?" If no, it is P0.

Nice-to-Have (P1): Significantly improves the experience but the core use case works without them. These often become fast follow-ups after launch.

Future Considerations (P2): Explicitly out of scope for v1 but we want to design in a way that supports them later. Documenting these prevents accidental architectural decisions that make them hard later.

For each requirement:

- Flag dependencies on other teams or systems
- Note any technical considerations or constraints
- Include acceptance criteria (see below)
- Write a clear, unambiguous description of the expected behavior

### 6. Success Metrics

See the success metrics section below for detailed guidance.

### 7. Open Questions

- Distinguish between blocking questions (must answer before starting) and non-blocking (can resolve during implementation)
- Tag each with who should answer (engineering, design, legal, data, stakeholder)
- Questions that need answers before or during implementation

### 8. Timeline Considerations

- Suggested phasing if the feature is too large for one release
- Dependencies on other teams' work or releases
- Hard deadlines (contractual commitments, events, compliance dates)

## User Story Writing

Good user stories are:

- Testable: There is a clear way to verify it works
- Small: Can be completed in one sprint/iteration
- Estimable: The team can roughly estimate the effort
- Valuable: Delivers value to the user (not just the team)
- Negotiable: Details can be discussed, the story is not a contract
- Independent: Can be developed and delivered on their own

### Common Mistakes in User Stories

- Internal focus: "As the engineering team, we want to refactor the database" — this is a task, not a user story
- Too large: "As a user, I want to manage my team" — break this into specific capabilities
- No benefit: "As a user, I want to click a button" — why? What does it accomplish?
- Solution-prescriptive: "As a user, I want a dropdown menu" — describe the need, not the UI widget
- Too vague: "As a user, I want the product to be faster" — what specifically should be faster?

## Requirements Categorization (MoSCoW)

- Won't have (this time): Explicitly out of scope. May revisit in future versions.
- Could have: Desirable if time permits. Will not delay delivery if cut.
- Should have: Important but not critical for launch. High-priority fast follows.
- Must have: Without these, the feature is not viable. Non-negotiable.

### Tips for Categorization

- P2s are architectural insurance — they guide design decisions even though you are not building them now.
- P1s should be things you are confident you will build soon, not a wish list.
- If everything is P0, nothing is P0. Challenge every must-have: "Would we really not ship without this?"
- Be ruthless about P0s. The tighter the must-have list, the faster you ship and learn.

## Success Metrics Definition

### Leading Indicators (days to weeks)

- Feature usage frequency, error rate, time to complete
- Task completion rate, activation rate, adoption rate

### Lagging Indicators (weeks to months)

- Competitive win rate, support ticket reduction, NPS change
- Revenue impact, retention impact

### Setting Targets

- Specify when you will evaluate: 1 week, 1 month, 1 quarter post-launch
- Define the measurement method: what tool, what query, what time window
- Set a "success" threshold and a "stretch" target
- Targets should be specific: "50% adoption within 30 days" not "high adoption"

## Acceptance Criteria

Write acceptance criteria in Given/When/Then format or as a checklist:

Given/When/Then:

- Given [precondition or context]
- When [action the user takes]
- Then [expected outcome]

Checklist format:

- Each criterion should be independently testable
- Include what should NOT happen (negative test cases)
- Cover the happy path, error cases, and edge cases

## Scope Management

### Preventing Scope Creep

- Create a "parking lot" for good ideas that are not in scope
- Time-box investigations: "If we cannot figure out X in 2 days, we cut it"
- Review the spec against the original problem statement — does everything serve it?
- Separate "v1" from "v2" clearly in the spec
- Require that any scope addition comes with a scope removal or timeline extension
- Write explicit non-goals in every spec

## Keywords

PRD, BRD, business requirements, feature spec, user stories, acceptance criteria, product requirements, MoSCoW, success metrics
