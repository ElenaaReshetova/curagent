# CURSOR_CONTEXTUAL_HELP_MASTER_PROMPT.md

Используй PLATFORM_CONTEXTUAL_HELP_AND_SKILL_SLOT_UX_SPEC.md как основной источник требований.

Цель:
сделать сложные настройки платформы понятными пользователю и полностью переработать UX настройки Skill Slot.

Сначала:
1. Просканируй репозиторий.
2. Создай docs/ux/CONTEXTUAL_HELP_CURRENT_STATE.md.
3. Найди все settings forms, labels, tooltips, validation messages и help components.
4. Найди Playbook Designer и Skill Slot editor.
5. Опиши текущую Skill Slot data model.
6. Найди mock Skill selectors и raw JSON mapping.
7. Найди localization и user preferences.
8. Покажи список файлов для изменения.

Первый implementation slice:
- Help Content Registry;
- YAML help schema;
- FieldHelp;
- HelpTooltip;
- HelpPopover;
- ContextHelpDrawer;
- Basic/Advanced/Expert mode;
- step-based Skill Slot editor;
- plain-language summary;
- configuration checklist;
- Skill version policy explanations;
- visual required inputs;
- Preview Input;
- explanations for Knowledge, Rules, Controls, Runtime and Capabilities;
- Explain this configuration;
- What will happen;
- actionable validation messages;
- accessibility;
- tests.

Главные правила:
- не создавать бессмысленные одинаковые tooltips;
- help content не хардкодить отдельно в каждом form component;
- basic setup Skill Slot не должен требовать raw JSON;
- real Skill API remains authoritative;
- advanced configuration remains available;
- technical codes remain available in expandable details;
- Russian localization is mandatory;
- tooltips must work with keyboard focus;
- production mocks must not be introduced.

Acceptance:
A new user can configure one Skill Slot end-to-end and understand every required choice without opening external documentation.
