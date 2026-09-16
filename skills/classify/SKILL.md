---
name: classify
description: >-
  Classify an incoming task and route it to the best specialist skill
  (business-requirements, system-requirements, test-case-design, code-analysis, or general).
  Use at E2E Flow level (not inside a PDLC playbook) when the intent is not fixed in advance.
  Deterministic platform classifier (not an LLM Capability / MCP call).
---

# Classify Task

Определи тип задачи и выбери **один** skill для исполнения.

Это platform skill: runner вызывает детерминированный классификатор (`classify_task`), а не LLM.
Результат — `RoutingDecision` с `primary_skill`; playbook ветвится по меткам исходящих рёбер.

## Output

| Field | Meaning |
|-------|---------|
| `primary_skill` | ID skill для исполнения |
| `artifact_type` | Ожидаемый тип артефакта |
| `complexity` | `low` / `medium` / `high` |
| `confidence` | 0.0–1.0 |
| `requires_planning` | Нужна ли декомпозиция |

## Routing map

| Skill | Когда выбирать | Артефакт |
|-------|----------------|----------|
| `business-requirements` | BRD, PRD, user stories, acceptance criteria, бизнес-требования, feature spec | BusinessRequirementsDoc |
| `system-requirements` | SRS, NFR, API spec, системные/технические требования, архитектура | SystemRequirementsDoc |
| `test-case-design` | тест-кейсы, test plan, QA, coverage, план тестирования | TestCasePack |
| `code-analysis` | code review, анализ кода, security scan, ревью кода | CodeAnalysisReport |
| `general` | нет явного match или низкая уверенность | General |

## Platform wiring (pre-scenario)

Классификация — **до** старта сценария (для всех источников):

1. Ingress (Slack / Jira / …) → normalize
2. **Classify** → `primary_skill`
3. Выбор Temporal template / Flow по skill map
4. Старт **только** выбранного сценария (BRD или SRD, …)

Внутри шаблона шаг Classify пропускается, если решение уже принято.

| primary_skill | template |
|---------------|----------|
| `business-requirements` | `generate-business-requirements-slack` |
| `system-requirements` | `generate-system-requirements` |
| … | см. `scenario_router.SKILL_TO_TEMPLATE` |

5. Refine: `skill_id: $routing`

## Rules

- Не исполнять бизнес-логику skill'ов здесь — только маршрутизация.
- Не подменять classify эвристиками в LLM-шагах; source of truth — `classify_task`.
- При неоднозначности предпочитать более специфичный skill; иначе `general`.
