---
name: normalize-task
description: >-
  Normalize an incoming autonomous-agent task into a canonical work-item envelope:
  title, description, commit URL, repo, diff scope, policy/SDD refs, and language.
  Use as the first productive skill in a playbook when the request comes from
  GigaCode Desktop (or similar) with a linked commit.
---

# Task Normalizer

Приведи входящую задачу к каноническому виду для последующих шагов playbook.

**Language:** Same language as the user's request (Russian → Russian, English → English).

## Inputs

- Raw task text / work item from ingress (GigaCode Desktop, Slack, API, …)
- Optional links: commit URL, repo, SDD/policy paths

## Outputs

Structured normalized task (WorkItem / Problem Understanding patch) with:

| Field | Meaning |
|-------|---------|
| `title` | Short task title |
| `description` | Cleaned task body |
| `commit_url` | Linked commit URL if present |
| `repo` | Repository identity if present |
| `diff_scope` | Files / paths / PR scope if present |
| `policy_refs` | Paths or IDs of SDD / security policy docs |
| `language` | Detected language of the request |
| `source` | Origin system (e.g. `GIGACODE_DESKTOP`) |

## Procedure

1. Parse the user request; do not invent commit URLs or file paths.
2. Extract commit / repo / scope / policy references when explicitly provided.
3. Produce a concise title and cleaned description.
4. Mark missing critical fields as open questions (do not block silently).
5. Return a typed patch only — no free-form essay.

## Rules

- Do not execute code review or policy analysis here — only normalization.
- Do not copy secrets or real PII into the normalized envelope; redact if present.
- Preserve the user's linked commit URL verbatim when present.
