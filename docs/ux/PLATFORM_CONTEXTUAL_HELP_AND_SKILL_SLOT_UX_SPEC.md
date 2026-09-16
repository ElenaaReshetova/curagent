# PLATFORM_CONTEXTUAL_HELP_AND_SKILL_SLOT_UX_SPEC.md

## Governed AI Delivery Platform
### Implementation-grade задание для Cursor на понятные подсказки, подписи, onboarding и удобное редактирование Skill Slot

---

# 0. Проблема

Платформа содержит большое количество сложных технических настроек:

- Playbooks;
- Skill Slots;
- Skills;
- Rules;
- Controls;
- Runtime Profiles;
- Knowledge Spaces;
- Capabilities;
- Integrations;
- Input Mapping;
- Output Mapping;
- retry;
- timeout;
- version policy;
- runtime resolution;
- Human Checkpoints;
- publication;
- evidence.

Пользователь не понимает:

- что означает конкретная настройка;
- зачем она нужна;
- когда её менять;
- что произойдёт после изменения;
- какие значения безопасны;
- какие поля обязательны;
- чем похожие сущности отличаются друг от друга;
- как корректно настраивать Skill Slot.

Текущий интерфейс предполагает, что пользователь уже знает внутреннюю архитектуру платформы.

Это неверное предположение.

---

# 1. Цель

Необходимо сделать интерфейс самодокументируемым.

Пользователь должен понимать назначение настройки непосредственно в момент работы, без необходимости искать отдельную документацию.

Целевой принцип:

```text
Название поля
  ↓
Краткое понятное объяснение
  ↓
Пример
  ↓
Последствия изменения
  ↓
Рекомендованное значение
  ↓
Ссылка на подробную документацию
```

---

# 2. Основные UX-принципы

## 2.1. Progressive disclosure

Не показывать пользователю сразу всю техническую сложность.

Настройки делятся на:

```text
Basic
Advanced
Expert
```

По умолчанию открыт Basic mode.

Advanced и Expert раскрываются по запросу.

---

## 2.2. Plain language

Не использовать технический термин без объяснения.

Плохо:

```text
Implementation resolution policy
```

Хорошо:

```text
Как выбрать реализацию Skill

Определяет, какую конкретную реализацию использовать при запуске.
Обычно оставьте «Выбирать автоматически».
```

---

## 2.3. Explain consequences

Каждая важная настройка должна объяснять последствия.

Пример:

```text
Pinned Version

Playbook всегда будет использовать выбранную версию Skill.
Новые версии Skill не будут подхватываться автоматически.
```

---

## 2.4. Safe defaults

Для большинства полей интерфейс должен:

- выбрать безопасное значение;
- объяснить, почему оно выбрано;
- предупредить перед опасным изменением.

---

## 2.5. Examples before schemas

Пользователь сначала должен видеть понятный пример.

Только после этого — JSON Schema, JSONPath, CEL и технические детали.

---

# 3. Уровни помощи

Необходимо реализовать пять уровней contextual help.

## Level 1 — Постоянная подпись

Короткий текст под полем.

Пример:

```text
Runtime Profile

Среда, модель и ограничения, в которых будет выполняться Skill.
```

## Level 2 — Tooltip

Показывается по hover или focus на значок `?`.

Содержит 1–3 коротких предложения.

## Level 3 — Learn More Popover

Показывается по клику.

Содержит:

- подробное объяснение;
- пример;
- recommended value;
- consequences;
- related concepts.

## Level 4 — Side Help Panel

Контекстная панель справа.

Меняется при выборе поля, node или раздела.

## Level 5 — Documentation Page

Полная документация с deep link.

---

# 4. Компоненты системы помощи

Необходимо создать переиспользуемые компоненты:

```text
FieldHelp
HelpTooltip
HelpPopover
ContextHelpPanel
ConceptExplanation
ConfigurationExample
RecommendedValue
ConsequenceWarning
RelatedConcepts
GlossaryLink
FirstTimeHint
GuidedTour
EmptyStateGuide
ValidationExplanation
```

---

# 5. FieldHelp API

Пример React API:

```tsx
<FieldHelp
  conceptKey="skill-slot.runtime-profile"
  label="Runtime Profile"
  shortDescription="Среда и ограничения выполнения Skill."
  recommendedValue="Использовать настройку Playbook"
  consequences={[
    "Влияет на модель и стоимость",
    "Определяет доступные capabilities",
    "Может ограничивать сеть и файловую систему"
  ]}
/>
```

Контент не должен хардкодиться отдельно в каждом компоненте.

---

# 6. Help Content Registry

Создать централизованный Help Content Registry.

```text
help_content
- concept_key
- title
- short_description
- full_description
- example
- recommended_value
- consequences
- warnings
- related_concepts
- documentation_url
- audience_level
- locale
- version
```

Источник истины может быть:

```text
YAML files in repository
```

После сборки контент может импортироваться или собираться в frontend bundle.

---

# 7. Формат help YAML

```yaml
conceptKey: skill-slot.runtime-profile
title: Runtime Profile
shortDescription: >
  Среда, модель и ограничения, в которых выполняется Skill.

fullDescription: >
  Runtime Profile определяет AI-провайдера, модель, сетевой доступ,
  файловую систему, доступные capabilities, лимиты стоимости и retry.

recommendedValue: >
  Для большинства Playbooks используйте настройку «Наследовать от Playbook».

example:
  title: Requirements Runtime
  value:
    provider: OpenAI
    model: governed-default
    network: restricted

consequences:
  - Изменение может повлиять на качество результата.
  - Изменение может увеличить стоимость.
  - Некоторые capabilities могут стать недоступны.

warnings:
  - Не выбирайте unrestricted network без необходимости.

relatedConcepts:
  - runtime-profile
  - capability
  - control

documentationPath: /docs/runtime-profiles
audienceLevel: BASIC
```

---

# 8. Локализация

Help Content Registry должен поддерживать:

```text
ru-RU
en-US
```

Если перевод отсутствует:

1. показать fallback locale;
2. не показывать пустую tooltip;
3. записать missing translation metric.

---

# 9. Первый запуск

Для новых пользователей добавить Guided Tour.

Этапы:

```text
1. Что такое Playbook
2. Что такое node
3. Что такое Skill Slot
4. Как соединять nodes
5. Как выбрать Skill
6. Как настроить input
7. Как проверить validation
8. Как выполнить test run
9. Как активировать Version
```

Tour можно:

- пропустить;
- перезапустить;
- отключить.

---

# 10. Режимы интерфейса

Добавить переключатель:

```text
Simple
Advanced
Expert
```

## Simple

Показывает:

- основные поля;
- plain-language labels;
- recommended defaults;
- визуальный mapping assistant;
- минимум JSON.

## Advanced

Показывает:

- version policies;
- retry;
- timeout;
- runtime overrides;
- Rules;
- Controls;
- Knowledge Spaces.

## Expert

Показывает:

- raw JSON;
- CEL;
- JSONPath;
- implementation resolution;
- detailed dependency settings;
- raw schemas.

---

# 11. Что такое Skill Slot

В UI термин должен объясняться так:

> Skill Slot — это место в Playbook, где во время выполнения вызывается конкретный Skill.

Skill Slot определяет:

- какой Skill вызывается;
- какую версию использовать;
- какие данные передать Skill;
- какой Runtime Profile использовать;
- какие Knowledge Spaces доступны;
- какие Rules применить;
- какие Controls проверить;
- куда сохранить результат;
- что делать при ошибке.

---

# 12. Skill Slot vs Skill

Нужно постоянно объяснять различие.

```text
Skill
= переиспользуемая возможность платформы

Skill Slot
= конкретное использование Skill внутри Playbook
```

Пример:

```text
Skill:
Generate System Requirements

Skill Slots:
- Generate initial requirements
- Regenerate after review
- Generate requirements for security scope
```

Один Skill может использоваться в нескольких Skill Slots с разными настройками.

---

# 13. Skill Slot Card

На canvas Skill Slot должен показывать понятную summary.

```text
Generate System Requirements

Uses:
Requirements Generator

Input:
Work item + approved business requirements

Output:
System Requirements Artifact

Runtime:
Inherited from Playbook

Knowledge:
Architecture Standards

Controls:
2 active
```

Не показывать только technical key.

---

# 14. Skill Slot Editor Layout

Properties Panel Skill Slot должен быть разбит на понятные шаги.

```text
1. What should happen?
2. Which Skill performs it?
3. What data does it receive?
4. What context may it use?
5. Where does the result go?
6. What happens if it fails?
7. Advanced settings
```

---

# 15. Skill Slot Step 1 — Purpose

Поля:

```text
Display Name
Description
Expected Result
```

Подсказка:

```text
Опишите бизнес-результат этого шага, а не техническую реализацию.
```

Пример:

```text
Подготовить системные требования на основе утверждённых бизнес-требований.
```

---

# 16. Skill Slot Step 2 — Skill Selection

Label:

```text
Which Skill should perform this step?
```

Selector показывает:

```text
Name
Plain description
Input expected
Output produced
Risk level
Status
Version
Required capabilities
Recommended use cases
```

Добавить action:

```text
Why is this Skill recommended?
```

---

# 17. Skill Recommendation

Skill Selector может ранжировать Skills по:

- compatible input schema;
- compatible expected output;
- Playbook category;
- previous usage;
- active status;
- risk;
- available Runtime Profile;
- available capabilities.

Рекомендация должна быть explainable.

Пример:

```text
Recommended because:
- accepts Business Requirements Artifact;
- produces System Requirements Artifact;
- approved for Production;
- compatible with current Runtime Profile.
```

---

# 18. Skill Version Policy

Переименовать технические режимы в понятные labels.

## PINNED

UI label:

```text
Always use this exact version
```

Help:

```text
Самый предсказуемый вариант.
Playbook не будет автоматически использовать новые версии Skill.
```

## LATEST_COMPATIBLE

UI label:

```text
Use the newest compatible version
```

Help:

```text
Платформа сможет подхватывать новые совместимые версии.
Результаты могут измениться после обновления Skill.
```

## RUNTIME_RESOLVED

UI label:

```text
Let the platform choose
```

Help:

```text
Платформа выберет подходящую реализацию при запуске.
Используйте только если в организации настроены правила выбора.
```

Recommended default:

```text
PINNED for Production
LATEST_COMPATIBLE for Development
```

---

# 19. Skill Slot Step 3 — Input Mapping

Вместо пустого JSON editor сначала показывать визуальный mapping assistant.

Layout:

```text
Available data            Skill expects
----------------          ----------------
Work item title      →     title
Approved artifact    →     businessRequirements
Risk level           →     risk
```

---

# 20. Input Mapping Help

Для каждого target field показать:

```text
Field name
Human description
Type
Required/optional
Example
Current source
Validation state
```

Пример:

```text
businessRequirements

Что это:
Утверждённый документ с бизнес-требованиями.

Ожидаемый тип:
Artifact Reference

Обязательное:
Да

Источник:
Architecture Review → approvedArtifact
```

---

# 21. Mapping Suggestions

Добавить automatic suggestions.

Основания:

- matching field name;
- schema type;
- semantic metadata;
- artifact type;
- upstream node output;
- known aliases.

Suggestion не применяется без подтверждения.

---

# 22. Mapping Preview

Пользователь должен иметь кнопку:

```text
Preview Input
```

Она показывает реальный пример payload.

```json
{
  "title": "Payment cancellation",
  "businessRequirements": {
    "artifactId": "BR-184",
    "version": 3
  },
  "risk": "MEDIUM"
}
```

Sensitive values masked.

---

# 23. Mapping Validation

Показывать понятные ошибки.

Плохо:

```text
MAPPING_TYPE_MISMATCH
```

Хорошо:

```text
Поле businessRequirements ожидает ссылку на Artifact,
но сейчас получает обычный текст.
```

Сохранять technical code в expandable details.

---

# 24. Skill Slot Step 4 — Context

Sections:

```text
Knowledge
Rules
Controls
Runtime
Capabilities
```

Каждая section должна начинаться с одного простого вопроса.

---

# 25. Knowledge Spaces Help

Label:

```text
What information may the Skill use?
```

Explanation:

```text
Knowledge Space определяет, какие управляемые документы и источники
Skill может использовать как контекст.
```

Для каждого Knowledge Space показывать:

```text
Name
Description
Sources
Freshness
Classification
Region
Why selected
```

---

# 26. Rules Help

Label:

```text
How should the Skill produce the result?
```

Explanation:

```text
Rules задают инструкции и стандарты формирования результата.
Они влияют на содержание, стиль и структуру ответа.
```

Example:

```text
Use company architecture terminology.
Always include non-functional requirements.
```

---

# 27. Controls Help

Label:

```text
What must be checked or enforced?
```

Explanation:

```text
Controls независимо проверяют результат и могут предупредить,
заблокировать выполнение или потребовать approval.
```

Показывать enforcement badge:

```text
Warn
Block
Require approval
```

---

# 28. Runtime Profile Help

Label:

```text
Where and under which limits should the Skill run?
```

Simple options:

```text
Use Playbook setting
Use Skill default
Choose another Runtime Profile
```

Advanced options спрятаны.

---

# 29. Capabilities Help

Label:

```text
What external actions may this Skill perform?
```

Explanation:

```text
Capabilities — это разрешённые действия, например:
прочитать Jira issue, найти документ или опубликовать Artifact.
```

Показывать:

```text
Requested
Allowed
Blocked
Requires approval
Unavailable
```

---

# 30. Skill Slot Step 5 — Output Mapping

Plain-language question:

```text
Where should the result be saved?
```

Options:

```text
Save as Playbook context value
Create Artifact
Update existing Artifact
Pass to next step
Use as final Playbook output
```

---

# 31. Output Preview

Показывать:

```text
Skill produces
  ↓
Mapping
  ↓
Playbook receives
```

Example:

```text
Skill output:
systemRequirements

Saved as:
context.systemRequirementsArtifact

Available to:
Architecture Approval node
```

---

# 32. Skill Slot Step 6 — Failure Handling

Plain-language options:

```text
Stop the Playbook
Retry automatically
Go to another node
Ask a human
Skip this optional step
```

Под каждым вариантом объяснение.

---

# 33. Retry Help

Fields:

```text
Attempts
Initial delay
Backoff
Maximum delay
Retryable errors
```

Simple mode:

```text
No retry
Standard retry
Extended retry
```

Presets:

```text
Standard:
3 attempts, exponential backoff

Extended:
5 attempts, exponential backoff
```

---

# 34. Timeout Help

Показывать human duration:

```text
15 minutes
1 hour
24 hours
```

Tooltip:

```text
Если Skill не завершится за это время, шаг будет считаться failed.
```

---

# 35. Skill Slot Summary

В верхней части editor показывать summary sentence.

Пример:

```text
Этот шаг использует Skill «Generate System Requirements» версии 2.1,
получает Work Item и Business Requirements,
работает в Requirements Runtime,
использует Architecture Knowledge
и сохраняет результат как System Requirements Artifact.
```

Summary автоматически обновляется.

---

# 36. Configuration Completeness

Показывать checklist:

```text
✓ Purpose defined
✓ Skill selected
✓ Required input mapped
✓ Runtime resolved
! Knowledge not selected
✓ Output mapped
✓ Failure policy configured
```

---

# 37. Explain This Configuration

Добавить кнопку:

```text
Explain this configuration
```

Она открывает side panel с plain-language описанием всей конфигурации.

Без AI-зависимости в первой версии.

Explanation строится детерминированно из config.

---

# 38. What Will Happen?

Добавить кнопку:

```text
What will happen when this runs?
```

Показывать sequence:

```text
1. Playbook prepares input.
2. Platform selects Skill version 2.1.
3. Requirements Runtime is selected.
4. Architecture Knowledge is retrieved.
5. Skill executes.
6. Output is validated.
7. Artifact Draft is created.
8. Two Controls are evaluated.
9. Playbook continues to Architecture Approval.
```

---

# 39. Dangerous Settings

Настройки повышенного риска должны иметь warning block.

Примеры:

```text
Unrestricted network
Latest unpinned version
Write capability
Skip on failure
No output validation
Expert raw JSON
```

Warning должен объяснять конкретный риск.

---

# 40. Validation Messages

Каждое сообщение должно содержать:

```text
What is wrong
Why it matters
How to fix it
Technical details
```

Example:

```text
Input field «businessRequirements» is not configured.

Why it matters:
The selected Skill cannot run without approved business requirements.

How to fix:
Select an upstream Artifact Reference for this field.

Technical details:
SKILL_INPUT_REQUIRED_FIELD_MISSING
```

---

# 41. Empty States

Каждая пустая section должна объяснять, что делать.

Плохо:

```text
No rules
```

Хорошо:

```text
No additional Rules are configured.

Rules are optional instructions that shape the Skill output.
The Skill will still use inherited Platform and Workspace Rules.

[Add Rule]
[Learn more]
```

---

# 42. Inline Examples

Для сложных fields показывать example toggle:

```text
Show example
```

Examples нужны для:

- JSONPath;
- CEL;
- input mapping;
- output mapping;
- event correlation;
- condition;
- retry;
- capability binding;
- artifact reference.

---

# 43. Glossary

Создать встроенный glossary.

Concepts:

```text
Playbook
Playbook Version
Node
Skill
Skill Slot
Rule
Control
Knowledge Space
Runtime Profile
Capability
Integration
Artifact
Evidence
Human Checkpoint
Input Mapping
Output Mapping
Execution
Step Run
```

Glossary должен быть доступен:

- из global help;
- из tooltip;
- через search;
- через keyboard shortcut.

---

# 44. Global Help Search

Добавить:

```text
Search help
```

Search по:

- title;
- aliases;
- descriptions;
- related concepts;
- settings;
- validation errors.

---

# 45. Help Drawer

Global Help Drawer должен содержать:

```text
Current page
Selected object
Common tasks
Concepts on this page
Validation problems
Related documentation
```

---

# 46. Context-aware Help

При выборе Skill Slot Help Drawer автоматически показывает:

```text
What is a Skill Slot?
How to choose a Skill
How input mapping works
How output mapping works
Runtime Profile
Rules vs Controls
Common mistakes
```

---

# 47. First-Time Hints

Первый раз при открытии сложного поля показать non-blocking hint.

Пример:

```text
Input Mapping connects data from previous Playbook steps
to fields expected by this Skill.
```

Hints не должны повторяться после dismiss.

---

# 48. Help Preferences

Сохранять:

```text
helpLevel
guidedTourCompleted
dismissedHints
preferredMode
showInlineDescriptions
showExamples
```

Можно хранить в user preferences API.

---

# 49. Telemetry

Собирать обезличенные UX metrics:

```text
tooltip opened
learn more opened
validation help opened
guided tour completed
field abandoned
mapping suggestion accepted
help search query
configuration reverted
```

Не записывать sensitive config values.

---

# 50. Help Content Governance

Help content должен иметь:

```text
owner
reviewer
version
last reviewed date
product version compatibility
```

Устаревший help опасен.

---

# 51. UI Integration Map

## Playbook Designer

Help для:

- node palette;
- ports;
- transitions;
- properties;
- validation;
- test run;
- activation;
- versioning.

## Skills

Help для:

- interface;
- implementation;
- schemas;
- capabilities;
- runtime requirements.

## Rules

Help для:

- scope;
- priority;
- conflicts;
- applicability.

## Controls

Help для:

- applicability;
- severity;
- enforcement;
- evidence;
- exceptions.

## Runtime Profiles

Help для:

- provider;
- model;
- sandbox;
- network;
- filesystem;
- capability policy;
- cost;
- retry.

## Integrations

Help для:

- authentication;
- scopes;
- credentials;
- webhooks;
- sync;
- health.

## Capability Registry

Help для:

- contract;
- risk;
- integration binding;
- authorization;
- usage.

---

# 52. Backend/API

Help content API:

```http
GET /api/v1/help/concepts
GET /api/v1/help/concepts/{conceptKey}
GET /api/v1/help/search?q=
GET /api/v1/help/pages/{pageKey}
```

User preferences:

```http
GET /api/v1/users/me/help-preferences
PATCH /api/v1/users/me/help-preferences
```

---

# 53. Frontend Architecture

```text
features/contextual-help/
├── components/
│   ├── FieldHelp
│   ├── HelpTooltip
│   ├── HelpPopover
│   ├── ContextHelpDrawer
│   ├── GuidedTour
│   ├── Glossary
│   └── ValidationExplanation
├── hooks/
│   ├── useHelpConcept
│   ├── usePageHelp
│   └── useHelpPreferences
├── registry/
├── analytics/
└── tests/
```

Skill Slot:

```text
features/playbooks/skill-slot-editor/
├── SkillSlotSummary
├── PurposeSection
├── SkillSelectionSection
├── InputMappingSection
├── ContextSection
├── OutputMappingSection
├── FailurePolicySection
├── ConfigurationChecklist
└── ExecutionExplanation
```

---

# 54. Accessibility

Tooltips должны:

- открываться keyboard focus;
- закрываться Escape;
- иметь ARIA descriptions;
- не зависеть только от hover;
- быть доступны screen reader;
- не перекрывать active field;
- сохранять readable contrast.

---

# 55. Mobile and narrow layouts

На узком экране:

- tooltip превращается в popover;
- Help Drawer открывается fullscreen;
- inline descriptions остаются видимыми;
- Skill Slot steps становятся accordion.

---

# 56. Performance

Help content не должен замедлять основной UI.

Targets:

```text
Tooltip open < 100 ms
Help concept cached after first load
Page help load < 300 ms
Search result < 500 ms
```

---

# 57. No-Mock Rule

Нельзя:

- добавлять одинаковый lorem ipsum tooltip;
- показывать tooltip без реального смысла;
- делать hardcoded help только для одного экрана;
- использовать непереведённые technical field names как explanation;
- скрывать проблему только косметическими labels;
- оставлять старые mock Skill options.

---

# 58. Repository Discovery

Cursor должен найти:

```text
all settings forms
Playbook Designer
Skill Slot editor
field labels
tooltips
popover components
help components
validation messages
Skill selector
mapping editors
Runtime Profile selector
Rules selector
Controls selector
Knowledge selector
current documentation links
```

Создать:

```text
docs/ux/CONTEXTUAL_HELP_CURRENT_STATE.md
```

---

# 59. Current State Document

Должен включать:

1. Screens and forms.
2. Fields without descriptions.
3. Technical labels.
4. Existing tooltips.
5. Duplicate tooltip implementations.
6. Skill Slot component tree.
7. Current Skill Slot data model.
8. Current mapping UX.
9. Validation messages.
10. Missing help APIs.
11. Accessibility problems.
12. Priority list.

---

# 60. Implementation Sequence

## PR-1 — Help foundation

- Help Content Registry;
- FieldHelp;
- Tooltip;
- Popover;
- Help Drawer;
- YAML schema;
- localization;
- tests.

## PR-2 — Skill Slot simplification

- step-based layout;
- plain labels;
- summary;
- configuration checklist;
- Basic/Advanced/Expert modes.

## PR-3 — Skill selection

- real Skill API;
- detailed Skill cards;
- recommendations;
- version policy explanations.

## PR-4 — Mapping UX

- visual mapping;
- schema browser;
- suggestions;
- preview;
- understandable validation.

## PR-5 — Context configuration

- Knowledge;
- Rules;
- Controls;
- Runtime;
- Capabilities;
- consequences and recommendations.

## PR-6 — Failure/output

- output destinations;
- failure presets;
- retry presets;
- timeout help;
- execution explanation.

## PR-7 — Platform coverage

- Playbooks;
- Skills;
- Rules;
- Controls;
- Runtime Profiles;
- Integrations;
- Capability Registry.

## PR-8 — Guided onboarding

- guided tour;
- first-time hints;
- glossary;
- help search;
- user preferences.

## PR-9 — Analytics and hardening

- telemetry;
- accessibility;
- localization coverage;
- stale help detection;
- performance.

---

# 61. First Vertical Slice

Сделать полностью понятным один Skill Slot.

Scenario:

```text
Open Playbook Designer
  ↓
Select Skill Slot
  ↓
See plain-language summary
  ↓
Choose real Skill
  ↓
Understand version policy
  ↓
Map required input visually
  ↓
Select Knowledge Space
  ↓
Understand Rules and Controls
  ↓
Choose output destination
  ↓
See configuration checklist
  ↓
Preview what will happen
  ↓
Save
```

---

# 62. Acceptance Criteria

1. Пользователь без знания архитектуры понимает, что такое Skill Slot.
2. Каждая основная настройка имеет short description.
3. Сложные настройки имеют Learn More.
4. Skill Slot имеет пошаговый layout.
5. Input Mapping можно настроить без ручного JSON.
6. Пользователь видит, какие input fields обязательны.
7. Пользователь видит preview входа.
8. Пользователь понимает различие Rules и Controls.
9. Пользователь понимает Runtime Profile.
10. Пользователь понимает последствия version policy.
11. Configuration checklist показывает незавершённые настройки.
12. Explain this configuration работает.
13. What will happen работает.
14. Validation messages содержат способ исправления.
15. Tooltips доступны с клавиатуры.
16. Help content локализован.
17. Help не использует mock data.
18. Tests проходят.

---

# 63. Exact Cursor Task

```text
Use PLATFORM_CONTEXTUAL_HELP_AND_SKILL_SLOT_UX_SPEC.md as the authoritative specification.

First inspect the repository and create:
docs/ux/CONTEXTUAL_HELP_CURRENT_STATE.md

Identify:
- every complex settings screen;
- every field without a description;
- every technical label visible to users;
- current tooltip and popover components;
- Playbook Designer component tree;
- Skill Slot editor component tree;
- current Skill selector;
- current input/output mapping editors;
- validation message implementation;
- localization system;
- documentation routing;
- user preference storage.

Before changing code, output:
- discovered files;
- current Skill Slot flow;
- current data model;
- existing help components;
- missing reusable components;
- proposed Help Content Registry format;
- files planned for modification.

Then implement PR-1 and the first Skill Slot vertical slice:

1. Create Help Content Registry with YAML schema.
2. Create FieldHelp, HelpTooltip, HelpPopover and ContextHelpDrawer.
3. Add Russian help content.
4. Add Basic/Advanced/Expert UI mode.
5. Restructure Skill Slot properties into:
   - Purpose;
   - Skill;
   - Input;
   - Context;
   - Output;
   - Failure handling.
6. Add a plain-language Skill Slot summary.
7. Add configuration completeness checklist.
8. Add help for Skill version policy.
9. Add visual required-input list.
10. Add Preview Input.
11. Add explanations for Knowledge, Rules, Controls, Runtime Profile and Capabilities.
12. Add deterministic “Explain this configuration”.
13. Add deterministic “What will happen when this runs?”.
14. Replace technical validation messages with actionable messages while preserving technical codes in details.
15. Add accessibility and tests.
16. Update docs/IMPLEMENTATION_STATUS.md.

Do not:
- create meaningless generic tooltips;
- hardcode help directly in every form;
- hide advanced settings without a way to access them;
- replace real configuration with fake examples;
- use mock Skills in production;
- require raw JSON for basic Skill Slot setup.

Acceptance test:

A new user can configure one Skill Slot from an upstream Artifact to an output Artifact, understand every required choice, preview the input, see what will happen at runtime, and save the configuration without reading external documentation.
```

---

# 64. Definition of Done

Система помощи считается готовой, если:

- help registry централизован;
- основные настройки имеют descriptions;
- complex concepts имеют examples и consequences;
- Skill Slot понятен без внешней документации;
- Basic mode не требует JSON;
- Expert mode сохраняет полный контроль;
- validation помогает исправить ошибку;
- Help Drawer контекстный;
- glossary и search работают;
- onboarding работает;
- accessibility соблюдена;
- content локализован;
- mocks не используются;
- tests проходят.

Конец документа.
