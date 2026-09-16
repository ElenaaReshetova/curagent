# Системные требования (SRS)
## Управляемая платформа AI Delivery (Governed AI PDLC Platform)

| Поле | Значение |
|------|----------|
| Статус | **Нормативный источник истины** концепции продукта |
| Версия | 1.1 |
| Дата | 2026-08-14 |
| Язык продукта | Русский (технические идентификаторы — английские) |
| Назначение | Зафиксировать архитектуру, UX, модель данных, контракты и алгоритмы так, как они должны работать, чтобы получить текущий UX/UI. Реализация переписывается под этот документ, а не наоборот. |

Этот документ **замещает** playbook-центричные ТЗ (`PLAYBOOKS_*`, `CURSOR_GOVERNED_*` в части оркестрации) как SoT для сценариев, графа, рантайма и запусков. Модульные ТЗ Skills / Rules / Knowledge / Controls / Runtime Profiles остаются валидными по смыслу каталогов, но ссылки на Playbook в них читаются как **узел AI Agent / Skill slot на графе**.

---

# 1. Введение

## 1.1. Purpose

Платформа даёт команде собрать управляемого AI-агента доставки: от внешнего work item до опубликованного артефакта, с обязательными контролями, согласованием человеком и аудитом.

Оператор **не программирует Temporal**. Он рисует сценарий на канвасе, публикует версию, вооружает её для агента и наблюдает запуски / согласования.

## 1.2. Scope

В scope:

- информационная архитектура UI (Обзор / Сборка / Запуск / Управление);
- Е2Е сценарий и stage-граф на одном канвасе workflow DSL;
- навыки, правила, области знаний, профили исполнения;
- контроли и governance-gates, компилируемые в граф;
- интеграции, реестр способностей, MCP;
- запуски, инспектор, очередь согласований, аудит;
- рантайм: ingress → routing → Temporal interpreter → skills → capability gateway;
- контракты фронт ↔ API `/api/v1`.

Вне scope как доменные сущности продукта (не показывать в IA, не делать SoT):

- Playbook как отдельный каталог и сущность;
- Agent как карточка «агента» (заменён Runtime Profile);
- независимый CRUD нод/рёбер как авторский контракт (модель YAML Workflow Engine).

## 1.3. Definitions

| Термин | Определение |
|--------|-------------|
| Work Item | Внешняя задача (Jira / Slack / ручной запуск) после нормализации |
| Е2Е сценарий | Граф `kind=e2e`: сквозной процесс от триггера до публикации |
| Stage-граф | Граф `kind=stage`: переиспользуемый этап, вызывается узлом Subflow |
| workflow DSL | Документ `{identifier, title, nodes[], connections[], ui?}` — авторский SoT версии графа |
| TemporalPlan | Производный план шагов (activity / condition). Автор его не редактирует |
| Навык (Skill) | Пакет когнитивной операции (`SKILL.md` + manifest + contracts + capabilities) |
| Skill Interface | Стабильный контракт `domain.action@version`, который реализуют навыки |
| Способность (Capability) | Нормализованный инструмент за Capability Gateway, backed MCP/provider |
| Правило (Rule) | Версионированная инструкция агента (стиль, шаблон, terminologia) |
| Контроль (Control) | Обязательная проверка артефакта/исполнения; на графе проявляется как locked gate |
| Governance gate | Иммутабельный узел `policy.evaluate`, вставляемый компилятором в конец параллельной ветки |
| Профиль исполнения | Технический runtime: модель, sandbox, лимиты. Не владеет маршрутизацией |
| Область знаний | Граница контекста и источников (Jira/Confluence/Git/…) |
| Запуск (Execution) | Операторская проекция прогона: статус, стадии, артефакты, связь с engine run |
| Engine run (GraphRun) | Экземпляр интерпретатора (Temporal или local test) |
| Согласование (Checkpoint) | Очередь человека по INPUT / policy gate |
| Draft / Publish | Черновик редактируется; published — иммутабельный снимок для live-запусков |
| Launch / Stop | Вооружить / разоружить опубликованный Е2Е для агента. Не равно «создать execution» |
| Publication node | Узел, который выпускает результат наружу (Kafka, Integration, Upsert, Webhook POST/PUT/PATCH/DELETE) |

## 1.4. References

- UX shell: `src/workflow_ui/static/index.html` (навигация и экраны — нормативные по IA).
- Канвас: `frontend/src/` (GraphDesigner, PropertyInspector, workflow DSL IR).
- Рантайм: `WorkflowInterpreter`, `TaskLifecycleWorkflow`.
- Предыдущие модульные SRS: `docs/skills`, `docs/rules`, `docs/knowledge`, `docs/controls`, `docs/runtime_profiles`, `docs/executions`, `docs/human-checkpoints` — уточняются этим документом в части графа.

## 1.5. Принцип «требования → система»

1. Этот SRS описывает **концепцию UX**, а не текущие JSON-файлы, dual-store или leftover API.
2. Если код расходится с SRS — дефект кода (или явный GAP в приложении A).
3. Авторский контракт канваса — **атомарный документ графа**, не набор независимых `/nodes` `/connections`.
4. Рантайм исполняет **published TemporalPlan**, собранный из workflow DSL, а не «строки БД нод».

---

# 2. Overall Description

## 2.1. Product perspective

Продуктовая формула (нормативная):

```text
External Work Item
  → Ingress (Slack / Jira / Manual / Test)
  → Normalize
  → Route to launched published E2E graph
  → workflow DSL snapshot (version)
  → compile governance
  → parse → TemporalPlan
  → WorkflowInterpreter
       ├─ AI Agent → Skill → Capabilities → Gateway → MCP
       ├─ Condition / Input (HITL)
       ├─ Subflow → child TemporalPlan (stage graph)
       ├─ Webhook / Kafka / Integration / Upsert / Internal service
       └─ Governance gate → Controls → block or pass
  → Artifacts + Evidence + Audit
  → Human Checkpoints when waiting
```

Две плоскости:

| Плоскость | Ответственность |
|-----------|-----------------|
| Control Plane | Каталоги, версии, валидация, publish, launch, UI |
| Runtime Plane | Temporal worker, interpreter, skill runtime, gateway, checkpoints |

UI — единый Control Plane. Temporal UI — внешняя ссылка для отладки, не часть продуктовой IA.

## 2.2. User classes

| Роль | Задачи |
|------|--------|
| Platform engineer | Интеграции, способности, контроли, профили |
| Scenario author | Рисует Е2Е и stage-графы, публикует, запускает test run |
| Skill author | Пакеты навыков, интерфейсы, наследование |
| Operator / reviewer | Очередь согласований, инспектор запуска |
| Agent runtime | Не пользователь UI; потребляет launched published сценарии |

## 2.3. Operating environment

- UI: браузер, shell на русском, канвас React Flow, встроенный в static shell.
- API: FastAPI, префикс `/api/v1`.
- Оркестрация: Temporal. Local interpreter — только Test run из дизайнера.
- Инструменты: Capability Gateway → MCP (Jira, Slack, …).
- LLM: через Runtime Profile (Qwen / GigaChat / LM Studio / API providers).

## 2.4. Constraints

- Нельзя обойти обязательный control через prompt или удаление gate с канваса.
- CORE/CORPORATE навыки неизменяемы; кастомизация — наследованием.
- Live-запуск идёт только от **published** версии, кроме явного Test run.
- Агент видит только сценарии с `launched=true`.
- Секреты не хранятся в DSL; только `secret_ref` / runtime secrets.
- UI layout (`ui.positions`) не участвует в TemporalPlan.

## 2.5. Assumptions

- Один workspace по умолчанию (`default`); мультитентность — поле `workspace_id` на записях.
- Нет отдельной сущности End: прогон заканчивается на листе без исходящих рёбер.
- Playbook-шаблоны `config/workflows/*.json` — legacy; целевой рантайм — interpreter.

## 2.6. Architecture — modules and services

```text
┌─────────────────────────────────────────────────────────────┐
│  UI Shell (Обзор / Сборка / Запуск / Управление)            │
│  + Graph Designer (React) embedded                          │
└───────────────────────────┬─────────────────────────────────┘
                            │ /api/v1
┌───────────────────────────▼─────────────────────────────────┐
│  Platform API                                                │
│  graphs · flows/e2e catalog · skills · rules · knowledge     │
│  runtime-profiles · controls · integrations · capabilities   │
│  executions · runs · checkpoints · audit · overview          │
└─┬───────────────┬───────────────┬───────────────┬───────────┘
  │               │               │               │
  ▼               ▼               ▼               ▼
 Catalog     Graph compile    Execution      Capability
 store       + parse          projection     Gateway
  │               │               │               │
  │               ▼               ▼               ▼
  │         Temporal  ←── worker / activities ──→ Skill runtime
  │         WorkflowInterpreter
  │         TaskLifecycleWorkflow (ingress)
  ▼
 Durable versioned records (logical SoT; physical store — NFR)
```

| Модуль | Сервис | Что делает |
|--------|--------|------------|
| Overview | dashboard/overview | Метрики, путь настройки, недавние запуски и согласования |
| Graphs | graphs service | CRUD графа, draft, validate, publish, compile governance, parse, runs |
| E2E Catalog | flows/e2e projection | Каталог сценариев, launch/stop, simulate, routing preview |
| Skills | skills service | Пакеты, файлы, validate, publish, inherit |
| Skill Interfaces | skill_interfaces | Контракты `domain.action@N` |
| Artifact Contracts | contracts | JSON Schema входов/выходов |
| Rules | rules service | Markdown-инструкции, resolve по scope |
| Knowledge | knowledge service | Пространства и source bindings |
| Runtime Profiles | runtime_profiles | Модель/sandbox/лимиты, activate |
| Controls | controls service | Packs, evaluation points, violations |
| Governance compiler | graphs.governance | Вставка locked gates в workflow DSL |
| Integrations | integrations + mcp_inventory | MCP servers, health |
| Capabilities | capabilities + gateway | Реестр способностей, dispatch |
| Executions | executions | Операторский журнал прогонов |
| Runs | graphs runs | Engine instance + Temporal signals |
| Checkpoints | human_checkpoints | Очередь HITL, decision → signal |
| Audit | audit store | Журнал control-plane действий |
| Ingress | Slack/Jira/chat gateways | Work item → TaskLifecycleWorkflow |
| Tool Gateway | resolver + dispatcher | Skill → capability → MCP |

## 2.7. Information architecture (нормативная)

Навигация — четыре зоны. Дизайнер **не** пункт меню: открывается из карточки Е2Е сценария.

```text
ОБЗОР
  Обзор

СБОРКА
  Е2Е Сценарии
  Навыки (skills)
  Правила (rules)
  Области знаний
  Профили исполнения

ЗАПУСК
  Запуски
  Согласования
  Инспектор запуска

УПРАВЛЕНИЕ
  Контроли
  Интеграции
  Реестр способностей
  Аудит
```

Путь настройки агента на Обзоре (нормативный порядок):

1. Интеграции  
2. Способности  
3. Правила  
4. Навыки  
5. Контроли  
6. Е2Е Сценарии  

Цепочка ценности на Обзоре:

```text
Work Item → Е2Е Сценарий → Навык → Способность → MCP
```

---

# 3. Functional Requirements

Каждое требование тестируемо. Приоритет: P0 — без этого UX/рантайм не существует; P1 — полный продукт; P2 — усиление.

Трассировка: колонка «Journey» указывает пользовательский путь.

## 3.1. UX и каталоги

### FR-001 Каталожный паттерн экрана
**Priority:** P0 · **Journey:** все разделы Сборки/Управления

Система SHALL показывать для каждого каталога: метрики, поиск/фильтры, карточки, detail drawer, действия Create / Open / Designer (где применимо).

**Acceptance:** Given каталог непустой, When пользователь открывает раздел, Then видны count-метрики и карточки со статусом draft/active/deprecated.

### FR-002 Обзор платформы
**Priority:** P0 · **Journey:** Обзор

SHALL отдавать: активные запуски, ожидают согласования, опубликованные сценарии, активные способности; недавние executions; очередь checkpoints; чипы навыков/сценариев; путь настройки.

**Acceptance:** Given есть launched сценарий и открытый checkpoint, When открыт Обзор, Then оба отражены без ручного refresh дольше 10 с после «Обновить».

### FR-003 Единый язык сущностей
**Priority:** P0 · **Journey:** весь UI

UI SHALL использовать: «Е2Е Сценарий», «Навык», «Способность», «Согласование», «Запуск». SHALL NOT показывать Playbook / Agent как пункты меню или типы карточек.

**Acceptance:** Given главная навигация, When пользователь проходит все пункты, Then ни один label не содержит «Playbook» или «Агенты».

### FR-004 Workspace по умолчанию
**Priority:** P1 · **Journey:** все записи

Каждая catalog-запись SHALL иметь `workspace_id` (default допустим).

## 3.2. Граф и дизайнер

### FR-005 Два kind графа, один дизайнер
**Priority:** P0 · **Journey:** Сборка сценария

`Graph.kind ∈ {e2e, stage}`. Один Graph Designer. Е2Е каталог показывает `kind=e2e`. Stage-графы создаются/открываются как цели Subflow.

Stage-граф **не** пункт главной навигации. Точки входа: Subflow inspector («Сценарии» / «Другие графы»), resolve по `graph_key`, опционально standalone BuilderShell. Отдельный каталог stage (P2) не обязателен для текущего UX.

**Acceptance:** Given автор открыл сценарий из «Е2Е Сценарии», When канвас загружен, Then `kind=e2e`. Given узел Subflow с `graph_key`, When Open, Then загружается граф `kind=stage` (или e2e, если так задано) с тем же дизайнером. Given главная навигация, When пользователь ищет отдельный пункт «Графы», Then его нет.

### FR-006 Авторский SoT — workflow DSL документ
**Priority:** P0 · **Journey:** Save draft

Версия графа хранит **один документ**:

```text
identifier, title, description, produces[],
nodes[{ identifier, title, icon?, description?, config, variables?, links?, verbose? }],
connections[{ sourceIdentifier, targetIdentifier,
              sourceOutletIdentifier?, sourceOptionIdentifier?, fallback? }],
ui?   // layout only: positions, kind — stripped from Temporal parse
```

Ноды и рёбра **не** являются независимым авторским CRUD. Сохранение — атомарная замена документа версии (optimistic `revision`).

**Acceptance:** Given два клиента с одним `revision`, When оба сохраняют, Then второй получает конфликт (409). Given save, When validate/parse, Then они видят тот же набор nodes/connections, что автор только что сохранил, плюс скомпилированные governance-узлы.

### FR-007 Канвас IR ↔ workflow DSL
**Priority:** P0 · **Journey:** Designer

Фронт работает с canvas IR (`nodes[].id/type/label/position/config`, `edges[].source/target/sourceHandle`). При save SHALL конвертировать в workflow DSL; при load — обратно. `ui.positions` сохраняются. End-ноды не существуют; при импорте legacy End отбрасывается.

**Acceptance:** Given нода перемещена, When save → reload, Then координаты совпадают ±1px.

### FR-008 Палитра типов узлов
**Priority:** P0 · **Journey:** Designer palette

Палитра SHALL содержать ровно эти авторские типы (canvas type → `config.type`):

| Palette | Canvas type | config.type | Temporal activity |
|---------|-------------|------------------|-------------------|
| Trigger | `trigger` | `SELF_SERVE_TRIGGER` / `EVENT_TRIGGER` / `SCHEDULE_TRIGGER` | не шаг (entrypoint) |
| Action | `ai_agent` | `AI_AGENT` | `ai_agent_execute` |
| Action | `ai` | `AI` | `ai_generate_summary` |
| Action | `webhook` | `WEBHOOK` | `http_webhook` |
| Action | `upsert_entity` | `UPSERT_ENTITY` | `upsert_entity` |
| Action | `kafka` | `KAFKA` | `kafka_publish` |
| Action | `integration_action` | `INTEGRATION_ACTION` | `integration_action` |
| Action | `internal_service` | `INTERNAL_SERVICE` | `internal_service` |
| Action | `subflow` | `SUBFLOW` | `execute_subflow` |
| Condition | `condition` | `CONDITION` | condition step |
| Input | `input` | `INPUT` | `human_review` + wait signal |

Реестр отдаётся `GET /schemas/node-types?kind=`.

**Acceptance:** Given kind=e2e, When палитра отрисована, Then все 11 типов доступны, End отсутствует. Given неизвестный `config.type` на publish, Then publish отклонён.

### FR-009 Порты и соединения
**Priority:** P0 · **Journey:** connect nodes

- Trigger: только out.
- Обычные action: in / out.
- Condition: out по `options[]` (идентификаторы опций).
- Input: out по `outlets[]`, согласованным с кнопками `userInputs`.
- Governance gate: out `pass` / `fail` (не авторские).

Соединение SHALL хранить outlet в `sourceOutletIdentifier` (INPUT) или `sourceOptionIdentifier` (CONDITION).

**Acceptance:** Given Condition с options yes/no, When ребро с yes, Then parse ставит ветку yes → target. Given Input approve/decline, When HITL approve, Then интерпретатор идёт в target approve.

### FR-010 Инспектор свойств
**Priority:** P0 · **Journey:** клик по узлу

При пустом выборе — свойства сценария (имя, описание, карта produces по веткам). При выборе узла — схема типа: trigger type, AI Agent skill, webhook URL/method, subflow graph_key, condition options, input buttons, artifact `produces` на агенте.

Governance-узел SHALL быть read-only (нельзя менять service, нельзя удалить вручную).

**Acceptance:** Given locked gate выбран, When пользователь пытается удалить, Then удаление блокируется. Given AI Agent, When выбран skill из каталога, Then `config.agentIdentifier` = skill key и при необходимости проставляется `produces`.

### FR-011 Node presets
**Priority:** P1 · **Journey:** palette presets

Автор MAY сохранить узел как preset (`name`, `node_type`, `label`, `config`, optional `kind`) и бросить его на канвас.

**Acceptance:** Given preset сохранён, When reload дизайнера, Then preset в палитре. DELETE удаляет только preset, не графы.

### FR-012 Save / Validate / Publish / Test run в хроме дизайнера
**Priority:** P0 · **Journey:** Designer chrome

Дизайнер SHALL вызывать:

- Save → `POST /graphs/{id}/draft` (normalize + compile governance + validate report).
- Validate → `POST /graphs/{id}/validate` (без смены статуса версии).
- Publish → `POST /graphs/{id}/publish` только если validation ok; пишет TemporalPlan в published version.
- Test run → `POST /runs` с маркером источника TEST; исполняет **draft** local interpreter, не требует launch.

**Acceptance:** Given invalid graph, When Publish, Then 400 и версия остаётся DRAFT. Given Test run, When Temporal недоступен, Then test всё равно идёт locally. Given live run без published, When не TEST, Then 400.

### FR-013 Компиляция governance при каждом save
**Priority:** P0 · **Journey:** Save draft

`prepare_workflow_doc` = parse → normalize → `compile_governance`.

Правила компилятора:

1. Параллельные ветки определяются по графу (split после condition/нескольких исходящих).
2. Если на ветке есть хотя бы один typed producer (`produces` / skill→artifact), в **конец ветки перед merge/publication** вставляется один locked gate.
3. Если ветка без типа, но есть publication и продюсеры в сценарии — ветка получает `GENERAL`.
4. Gate: `INTERNAL_SERVICE` / `service=policy.evaluate`, `metadata.immutable=true`, id `governance-{anchor}`.
5. Исходящие рёбра якоря переводятся на `pass` gate; `fail` возвращает к producer (или блокирует публикацию).
6. При удалении якоря orphan gates удаляются (`pruneOrphanGovernance`).
7. Авторские координаты сохраняются; новым gate даётся слот справа от якоря, только если позиции ещё нет.

**Acceptance:** Given две параллельные ветки BRD и SRD, When save, Then ровно два gate, по одному на ветку, не на каждый промежуточный AI. Given publication node без produces на агентах, When validate, Then ошибка `MISSING_PRODUCES` или `MISSING_GOVERNANCE_GATE`.

### FR-014 Validate правила графа
**Priority:** P0 · **Journey:** Validate/Publish

Минимум:

- не пустой граф;
- есть trigger;
- все connections ссылаются на существующие identifier;
- SUBFLOW имеет `graph_key`;
- AI_AGENT имеет `agentIdentifier`;
- WEBHOOK имеет `url`;
- при publication + producers обязателен produces и хотя бы один gate;
- нет неизвестных types.

**Acceptance:** Given отчёт, When ok=false, Then Publish запрещён. Issues содержат `code`, `message`, optional `node_id`.

### FR-015 Parse → TemporalPlan
**Priority:** P0 · **Journey:** Publish / Run

`parse_workflow_to_temporal` SHALL построить TemporalPlan:

- trigger metadata + inputs из userInputs;
- каждый не-trigger узел → ActivityStep или ConditionStep;
- `next_step` / `outlets` из connections;
- INPUT: `wait_for_signal=true`, `signal_name=review_decision`;
- порядок `step_order` — BFS от trigger.

TemporalPlan хранится на **published** версии. Это не второй авторский DSL.

**Acceptance:** Given published version, When create live run, Then interpreter получает plan с published snapshot, а не текущий draft.

## 3.3. Е2Е сценарии: жизненный цикл

### FR-016 Идентичность сценария
**Priority:** P0 · **Journey:** catalog create

Е2Е сценарий — Graph `kind=e2e` с:

- `id` (UUID), `key` (stable, вида `e2e:<slug>` допустим), `name`, `description`;
- `status ∈ {draft, active, deprecated, archived}`;
- `launched: bool`;
- `current_draft_version_id`, `current_published_version_id`.

Каталог UI MAY быть тонкой проекцией этой записи (метрики, flow_type). **Не допускается второй независимый SoT документа графа.** Если существует таблица/файл Flow рядом с Graph — это проекция: любое save графа обновляет проекцию, любое save проекции обновляет граф. Конфликт режется в пользу Graph DSL.

**Acceptance:** Given save в дизайнере, When открыт detail сценария, Then стадии/рёбра соответствуют DSL. Given два независимых документа (flow stages vs graph dsl) расходятся, When publish, Then система либо синхронизирует из Graph, либо отказывает; молчаливая рассинхронизация запрещена.

### FR-017 Версии: draft / publish / deprecate
**Priority:** P0 · **Journey:** versioning

Паттерн для Graph, Skill, Rule:

1. Record указывает на current draft и current published.
2. Редактирование идёт в DRAFT (revision++).
3. Publish: validate → snapshot → статус PUBLISHED → прежний PUBLISHED становится DEPRECATED → record.status=active.
4. Semantic version на версии (строка `0.1.0`), не integer «на самом record».
5. Live execution ссылается на **version_id**, не на «latest».

Control и Runtime Profile: шаг 3 = **activate** → статус версии `ACTIVE` (не PUBLISHED). Смысл тот же: иммутабельный текущий снимок.

**Acceptance:** Given published v1 и изменённый draft, When новый live run, Then исполняется v1. Given publish draft, When новый live run, Then исполняется новый snapshot. Given GET versions, Then видны DRAFT, PUBLISHED, DEPRECATED (для control/profile — DRAFT, ACTIVE, DEPRECATED).

### FR-018 Launch и Stop
**Priority:** P0 · **Journey:** Запуски / Е2Е

`POST .../launch` разрешён только если есть published version и статус не deprecated/archived. Ставит `launched=true`.  
`POST .../stop` ставит `launched=false`, published snapshot сохраняется.

Агент / ingress SHALL выбирать только launched+published Е2Е.

**Acceptance:** Given published но не launched, When приходит Slack work item, Then этот сценарий не выбирается. Given launch, When Stop, Then новые ingress его не берут; уже идущие executions не убиваются автоматически.

### FR-019 Запуски как витрина вооружённых сценариев
**Priority:** P0 · **Journey:** Запуски

Экран «Запуски» SHALL показывать published сценарии с флагом launched / available to arm, метрики launched/published/ignored, действие «Вооружить» / «Снять».

Это **не** список Execution. Три разных действия, три экрана:

| Действие | Экран | Смысл |
|----------|-------|--------|
| Publish | Дизайнер «Опубликовать» | Иммутабельный снимок |
| Launch | **Запуски** «+ Запустить сценарий» | Агент начинает брать сценарий; иначе карточка IDLE / «Игнорируется» |
| Run | **Инспектор запуска** «+ Новое выполнение» или ingress | Экземпляр work item |

Карточки Е2Е: **LAUNCHED** («Агент выполняет») vs **IDLE** («Опубликован, но не запущен — система игнорирует»).

**Acceptance:** Given published unlaunched, When пользователь на Запусках, Then сценарий в available, не в armed.

### FR-020 Simulate и route preview
**Priority:** P1 · **Journey:** detail сценария

`POST /flows/{id}/simulate` проходит happy-path по рёбрам.  
`POST /flows/route` / `route/preview` показывает, какой launched сценарий получит work item данного source.

Ingress routing живёт на проекции Е2Е как `routing_rules[]` (source, channel, expression, knowledge_space). Правила маршрутизации бьют skill-эвристики. Приоритет выбора: явный `flow_key` (launched+published) → `route_preview(routing_rules)` → единственный launched сценарий для source.

**Acceptance:** Given два launched сценария и routing rule, When preview с source=SLACK, Then возвращается один ключ и reason.

## 3.4. Skills, rules, knowledge, profiles

### FR-021 Skill как пакет, не агент
**Priority:** P0 · **Journey:** Навыки

SkillRecord + SkillVersion: `SKILL.md`, files[], manifest, `interface_key`, input/output contract keys, `allowed_capabilities`, runtime_type. Типы: CORE, CORPORATE, TEAM, IMPORTED. CORE/CORPORATE immutable; кастом — `POST /skills/{id}/inherit`.

Граф ссылается на skill через `AI_AGENT.config.agentIdentifier` (= skill key), не на конкретный file path.

**Acceptance:** Given CORE skill, When PUT файлов, Then 403/400. Given inherit, When publish child, Then AI Agent может выбрать child key. Given publish skill без contracts, Then validation fail.

### FR-022 Skill Interface и Artifact Contract
**Priority:** P0 · **Journey:** skills / contracts

Interface key `^[a-z][a-z0-9_.]*\.[a-z0-9_.]+@[0-9]+$`. Input и output contract обязательны и из реестра ArtifactContract (json_schema, satisfies, accepts).

**Acceptance:** Given unknown contract key, When create interface, Then 400.

### FR-023 Rules resolve
**Priority:** P0 · **Journey:** Правила + runtime skill

RuleVersion: markdown, scope (PLATFORM…SKILL), priority, conflict_strategy. Runtime SHALL резолвить эффективный пакет правил для (workspace, skill, graph) и передавать в skill runtime. Более узкий scope весит больше.

**Acceptance:** Given ORGANIZATION и SKILL rule с одним conflict_key OVERRIDE, When resolve, Then побеждает SKILL. Given AI Agent run, When SKILL.md исполняется, Then resolved rules присутствуют в контексте.

### FR-024 Knowledge Space как граница контекста
**Priority:** P1 · **Journey:** Области знаний

Пространство: type, classification, sources[], search/access policy. Сценарий/версия MAY указать `default_knowledge_space_key`. Skill retrieval идёт только в рамках пространства.

**Acceptance:** Given CONFIDENTIAL space, When search, Then не возвращаются источники вне space. Given activate/disable, Then статус меняется и отражается в каталоге.

### FR-025 Runtime Profile вместо Agent
**Priority:** P0 · **Journey:** Профили исполнения

Профиль: provider, model, sandbox, supervision, limits, capability allow/deny, secret_ref, region, fallback. Версия профиля и контроля переводится в действие через **activate** (`ACTIVE`), не через publish. Сценарий ссылается на profile key. Профиль **не** содержит allow-list сценариев и ingress routing. Хранится на Flow/E2E проекции как `runtime_profile_key` (и MAY на GraphVersion metadata).

**Acceptance:** Given activate profile, When skill run, Then используется model/provider этой версии. Given UI, When нет раздела Agents, Then pass FR-003.

## 3.5. Controls, интеграции, способности

### FR-026 Controls catalog
**Priority:** P0 · **Journey:** Контроли

Control: type (QUALITY_GATE, PUBLICATION_GATE, …), severity, evaluation_point (`AFTER_SKILL`, `BEFORE_ARTIFACT_PUBLICATION`, `AFTER_GRAPH`, …), expression, enforcement (BLOCK, REQUIRE_HUMAN_APPROVAL, …), applicability by artifact type. Жизненный цикл версии: DRAFT → **ACTIVE** (activate), не PUBLISHED.

Governance compiler SHALL подбирать packs по artifact types ветки (`resolve_applicable_packs`) и встраивать `packs[]` в gate на compile time. Explicit bindings MAY жить в DSL `policies.control_bindings` / node `packs`; они **strippятся** из Temporal activity config при normalize.

**Acceptance:** Given BRD artifact type, When compile, Then gate несёт BRD pack. Given BLOCK failed, When interpreter проходит gate, Then publication не выполняется и создаётся checkpoint либо execution FAILED согласно enforcement.

### FR-027 Интеграции и MCP
**Priority:** P0 · **Journey:** Интеграции → способности

Каталог интеграций + `GET /mcp/servers` + capability manifests. Настройка MCP обязательна до появления способностей.

**Acceptance:** Given MCP server offline, When catalog, Then health ≠ online. Given server tools, When реестр способностей, Then tools отображаются как capabilities.

### FR-028 Capability Gateway
**Priority:** P0 · **Journey:** skill tool call

Skill не вызывает MCP напрямую. Каждый tool call: resolve capability → policy (profile allow/deny, approval_required) → dispatch → audit.

**Acceptance:** Given capability в deny профиля, When skill вызывает tool, Then вызов блокируется и пишется audit. Given allow, When success, Then audit с caller, capability id, без секретов.

## 3.6. Запуски, HITL, инспектор

### FR-029 Execution как операторская сущность
**Priority:** P0 · **Journey:** Инспектор

Execution SHALL содержать: id, title, source, flow/graph key+name, version_id, graph_run_id, status, progress, current node/stage, stage_runs[], timeline[], artifacts[], evidence[], runtime_effective, snapshot (version pins).

Статусы (нормативные): `CREATED, QUEUED, STARTING, RUNNING, WAITING_FOR_EVENT, WAITING_FOR_HUMAN, PAUSED, CANCELLING, CANCELLED, COMPLETED, COMPLETED_WITH_WARNINGS, FAILED, TIMED_OUT`.

Создание live execution SHALL стартовать engine run (Temporal). Pause/resume/cancel SHALL сигналить Temporal, не только патчить JSON.

**Acceptance:** Given POST execution на launched graph, When 201, Then существует GraphRun + Temporal workflow id. Given pause, When interpreter, Then статус WAITING/PAUSED и шаги не продолжаются. Given cancel, When completed steps already done, Then новых activity нет.

### FR-030 Dual tracking запрещён как SoT
**Priority:** P0 · **Journey:** Inspector

Engine run и Execution — две проекции **одного** прогона. Инспектор читает execution и подмешивает `GET /runs/{id}/state` (current_node_id, outputs, pending_approval). Расхождение статусов > 5 с после refresh — дефект.

Единственный мост worker → control plane: `runtime_bridge` (`record_execution_started`, `update_execution_progress`, `ensure_live_run`). Temporal activities не пишут в JSON/DB в обход моста.

**Acceptance:** Given interpreter waiting on INPUT, When inspector, Then current node подсвечен и статус WAITING_FOR_HUMAN.

### FR-031 Human checkpoints
**Priority:** P0 · **Journey:** Согласования

При INPUT или gate с REQUIRE_HUMAN_APPROVAL система создаёт Checkpoint: type, blocking, artifact preview, evidence, control results, decision_options.

Решения: APPROVE, REJECT, REQUEST_CHANGES, … → `POST /human-checkpoints/{id}/decisions` → Temporal signal `approve` / `reject` / `review_decision` / `resume` с `node_id`.

Очередь: claim, claim-next, start-review, views my/team/unassigned/overdue.

**Acceptance:** Given blocking INPUT, When checkpoint не решён, Then interpreter не идёт дальше. Given APPROVE, When signal доставлен, Then берётся outlet approve. Given REJECT, Then fail-path или terminate согласно графу.

### FR-032 Inspector и viewer
**Priority:** P0 · **Journey:** Инспектор / designer run mode

`GET /runs/{id}/viewer` возвращает dsl + plan + state для подсветки канваса. Operator actions: pause, resume, cancel, retry (только FAILED), replan (P2).

**Acceptance:** Given running node, When viewer, Then узел current подсвечен. Given FAILED, When retry, Then новый или resumed run; When COMPLETED retry, Then 400.

### FR-033 Audit
**Priority:** P0 · **Journey:** Аудит

Control-plane действия (create/publish/launch/decision/capability dispatch) пишут audit: actor, action, entity, at. Без секретов и сырого PII.

**Acceptance:** Given publish graph, When GET /audit, Then есть событие publish с graph id.

## 3.7. Runtime algorithms (нормативные)

### FR-034 Ingress
**Priority:** P0 · **Journey:** Slack/Jira/Manual

1. Gateway (Slack/Jira) публикует work item (Kafka `tasks` или прямой API).
2. `start_workflow` собирает `WorkflowInput` (`task_id`, title, description, source, source_id, optional `flow_key`) и стартует `TaskLifecycleWorkflow` с устойчивым id (`task-{source_id}`, reject duplicate).
3. `normalize_task` канонизирует Work Item; `record_execution_started` создаёт Execution и связывает GraphRun (`ensure_live_run`).
4. Routing: `find_ingress_port_plan` / launched published e2e (FR-020). plan wins; classify только если вооружённого сценария нет.
5. Иначе — не исполнять скрытый legacy playbook как основной путь продукта. Допустимо только явное «нет вооружённого сценария» → FAILED/queued с причиной.

**Acceptance:** Given launched e2e и Slack message, When ingress, Then child `WorkflowInterpreter` с plan published версии. Given ни одного launched, When ingress, Then execution не «тихо» идёт в старый template.

### FR-035 Интерпретатор
**Priority:** P0 · **Journey:** run

Цикл: взять `step_order` / next; для Activity выполнить Temporal activity (timeout 30m, retry 3); для Condition вычислить expression и выбрать outlet; для wait_for_signal — status=waiting, query `getRunState`, ждать signal; SUBFLOW — child workflow с plan дочернего **published** графа; on_failure continue|terminate; выходы писать в `outputs[node_id]`; шаблоны `{{outputs.x}}` рендерятся перед activity.

Query `getRunState`: `{status, current_node_id, outputs, pending_approval, approvals, run_id, error}`.

**Acceptance:** Given condition expression true для option A, When step, Then next = A. Given webhook fail и onFailure=continue, When error, Then идём в next. Given subflow, When child completes, Then parent продолжает с outputs child.

### FR-036 Skill execution path
**Priority:** P0 · **Journey:** AI Agent node

`ai_agent_execute`:

1. Resolve skill published version by `agentIdentifier`.
2. Resolve rules + knowledge space + runtime profile.
3. Validate input against input contract.
4. Run skill runtime (Qwen CLI / LLM) с allowed_capabilities.
5. Tool calls только через Gateway.
6. Validate output contract.
7. Append artifact + evidence на Execution.
8. Если у узла `produces` — пометить artifact type для последующего gate.

**Acceptance:** Given skill output не бьётся в contract, When node finishes, Then шаг FAILED (или warning, если контракт soft — default FAIL). Given tool не в allow list, Then tool не вызывается. Given AI_AGENT, When skill вызывает способность, Then вызов идёт через Capability Gateway (не прямой MCP и не «LLM without tools» как единственный путь).

### FR-037 Local vs Temporal
**Priority:** P0 · **Journey:** Test run vs live

| Режим | Движок | Версия | Launch required |
|-------|--------|--------|-----------------|
| Test (`_source=TEST` / `source=TEST`) | in-process local_run | draft предпочтительно | нет |
| Live | Temporal WorkflowInterpreter | published | да для ingress; ручной run MAY с published без launch |

Local SHALL реализовывать тот же step semantics (HITL через те же signal API), включая SUBFLOW как вложенный прогон того же интерпретатора (не «только один уровень»).

**Acceptance:** Given test run INPUT, When approve via `/runs/{id}/signal/approve`, Then local run продолжает. Given test run с SUBFLOW, When child graph published, Then local исполняет child plan до return в parent.

---

# 4. Non-Functional Requirements

### NFR-001 Performance
- `GET` каталогов p95 < 300 ms при ≤ 500 записей (без payload файлов скилла).
- `POST /graphs/{id}/draft` p95 < 800 ms для графа ≤ 80 узлов (включая compile).
- `GET /runs/{id}/state` p95 < 200 ms (query Temporal или local snapshot).
- UI Обзор: первичная отрисовка < 2 s на локальном API.

### NFR-002 Availability
- Control Plane API: цель 99.5% (dev/stage не измеряется).
- Temporal worker outage: UI остаётся read-only для каталогов; live run create возвращает понятную ошибку; Test run жив.

### NFR-003 Durability
- Published версии, executions, checkpoints, audit — durable store (транзакции). JSON-файлы `config/platform/*.json` **не** являются целевым SoT.
- Optimistic concurrency: `revision` на draft.
- Backup/restore published graphs без потери `version_id` ссылок executions.

### NFR-004 Security
- Секреты только secret_ref / vault; запрет в DSL, audit, checkpoint preview.
- Capability deny нельзя обойти prompt injection (enforcement на gateway).
- Immutable skills и gates нельзя изменить API без role, которой нет у scenario author.

### NFR-005 Auditability
- Каждое publish/launch/decision/tool-dispatch — audit event.
- Retention audit ≥ 365 дней (P1); executions ≥ 90 дней.

### NFR-006 Privacy
- Не логировать тексты Slack/Jira сверх нужного для Work Item; маскировать emails/tokens в audit.
- Knowledge classification ограничивает retrieval.

### NFR-007 Maintainability
- Один интерпретатор для local и Temporal (разделяется только transport).
- Реестр нод — единственный список типов (backend registry → `/schemas/node-types` → палитра).
- Запрещено добавлять второй авторский DSL.

### NFR-008 Localization
- UI русский. API поля camelCase или snake_case — единообразно в одном контракте; целевой публичный JSON: **snake_case** для platform API, workflow DSL поля как в (`identifier`, `sourceIdentifier`) внутри `dsl`.

### NFR-009 Compatibility
- Canvas IR MAY приниматься на draft и конвертироваться сервером в workflow DSL (legacy helper). После конвертации хранится только workflow DSL.

---

# 5. External Interfaces

## 5.1. UI ↔ API (контракт, который должен держать UX)

База: `/api/v1`. Ошибки: 400 validation, 404 missing, 409 revision conflict. Тело ошибки: `{ "detail": string }` или `{ "code", "message", "details" }` — единообразно; целевое: `{ "error": { "code", "message", "issues?": [] } }`.

### 5.1.1. Designer (обязательный набор)

| Method | Path | Назначение | Request | Response |
|--------|------|------------|---------|----------|
| GET | `/schemas/node-types?kind=` | Палитра | | `{ node_types: NodeRegistryEntry[] }` |
| GET | `/schemas/workflow-graph` | JSON Schema IR | | schema bundle |
| GET | `/node-presets?kind=` | Presets | | `{ presets }` |
| POST | `/node-presets` | Save preset | `{name, node_type, label, config, kind?, id?}` | preset |
| DELETE | `/node-presets/{id}` | | | `{ok}` |
| GET | `/graphs?kind=` | Список графов | | `{ graphs }` |
| POST | `/graphs` | Создать | `{key, name, kind, description?, dsl?}` | GraphRecord |
| GET | `/graphs/resolve?kind&key` | Get-or-create by key | | `{id,key,kind,name}` |
| GET | `/graphs/{id}` | Record + draft canvas | | record + `draft` + `canvas` (IR) |
| POST | `/graphs/{id}/draft` | Save | `{dsl\|graph, revision?}` | GraphVersion |
| POST | `/graphs/{id}/validate` | | `{dsl?}` | ValidationReport `{ok, issues[]}` |
| POST | `/graphs/{id}/publish` | | `{version_id?}` | GraphVersion with `temporal_plan` |
| GET | `/graphs/{id}/versions` | | | `{ versions }` |
| POST | `/graphs/normalize` | Preview strip ui | `{dsl}` | `{ok, dsl}` |
| POST | `/graphs/parse` | Preview plan | `{dsl}` | `{ok, validation, dsl, plan}` |
| POST | `/runs` | Start run | `{graph_id, input?, version_id?, start_temporal?}` | GraphRun |
| GET | `/runs/{id}` | | | GraphRun |
| GET | `/runs/{id}/state` | Interpreter snapshot | | RunStateSnapshot |
| GET | `/runs/{id}/viewer` | Canvas + state | | `{run, dsl, plan, state, graph_id, version_id}` |
| GET | `/runs/{id}/events` | | | `{ events }` |
| POST | `/runs/{id}/signal/approve` | HITL | `{node_id, comment?}` | run |
| POST | `/runs/{id}/signal/reject` | | `{node_id, reason?}` | run |
| POST | `/runs/{id}/signal/changes` | | `{node_id, changeText?}` | run |
| POST | `/runs/{id}/update/resume` | | `{node_id?, payload?}` | run |

DesignerHandle на фронте: `getGraph, setGraph, save, validate, publish, autoLayout, deleteSelected`.

### 5.1.2. Е2Е каталог / launch

| Method | Path | UX |
|--------|------|-----|
| GET | `/flows` | Каталог + metrics |
| GET | `/flows/{id}` | Detail: record, draft, published, validation, path |
| POST | `/flows` | Create e2e (создаёт graph kind=e2e) |
| PUT | `/flows/{id}` | Метаданные (name, description, type) |
| DELETE | `/flows/{id}` | Если нет live executions |
| GET | `/flows/{id}/versions` | |
| POST | `/flows/{id}/versions` | New draft from published |
| POST | `/flows/{id}/validate` | |
| POST | `/flows/{id}/simulate` | |
| POST | `/flows/{id}/launch` | Arm |
| POST | `/flows/{id}/stop` | Disarm |
| GET | `/launches` | Armed catalog |
| GET | `/launches/metrics` | |
| POST | `/flows/route` `/route/preview` | |
| GET | `/flows/consumers?graph_key=` | Кто ссылается на stage graph |

PUT `/flows/{id}/versions/{vid}/graph` — допустим как адаптер, но SHALL писать в тот же Graph DSL (FR-016).

### 5.1.3. Остальные каталоги (минимум, который держит UI)

Skills: `GET/POST /skills`, `GET/PUT/DELETE /skills/{id}`, `POST inherit`, `GET versions`, `PUT files/SKILL.md`, `POST validate/publish`.  
Interfaces: CRUD `/skill-interfaces`, `GET /artifact-contracts`.  
Rules: list/metrics/resolve/CRUD/versions/content/publish.  
Knowledge: CRUD, sources, search, health, activate/disable.  
Runtime profiles: CRUD, draft, versions, activate, resolve, validate, test.  
Controls: CRUD, draft, validate, activate, test, resolve.  
Integrations: list/config/metrics/CRUD.  
Capabilities: `/capabilities`, `/mcp/servers`, `/capability-manifests`.  
Overview: `/overview`, `/dashboard/summary`, `/dashboard/pending-actions`.  
Executions: list/metrics/get/create, pause/resume/cancel/retry, contract/artifacts/evidence/events.  
Checkpoints: list/get/claim/start-review/decisions/artifact/diff/evidence/controls.  
Audit: `GET /audit`.  
Help: `GET /help`, `GET /help/{concept_key}`.

### 5.1.4. Что намеренно отсутствует в авторском API

Нет продуктового требования на независимые:

- `CRUD /nodes`
- `CRUD /stages`
- `CRUD /connections`
- `CRUD /activities` (worker mapping)

Маппинг type → Temporal activity — **код реестра**, не таблица, редактируемая с канваса. Read-only view допустим (P2).

## 5.2. Integrations

- Temporal: workflow `WorkflowInterpreter`, `TaskLifecycleWorkflow`; signals `approve`, `reject`, `human_decision`, `review_decision`; update `resume`; query `getRunState`.
- MCP: Jira, Slack, прочие servers из inventory.
- LLM providers из Runtime Profile.
- Kafka / HTTP webhook как узлы графа.

## 5.3. Data formats

- workflow DSL JSON как выше.
- TemporalPlan JSON: `{name, version, description, trigger, inputs, step_order, steps{id: activity|condition}}`.
- ValidationIssue: `{code, message, severity, node_id?}`.
- Canvas IR: `frontend/src/types.ts` WorkflowGraph.

---

# 6. Data Requirements

## 6.1. Conceptual model

```text
Workspace 1──* GraphRecord (kind: e2e|stage)
                 ├── current_draft → GraphVersion (status DRAFT, dsl, revision)
                 └── current_published → GraphVersion (PUBLISHED, dsl, temporal_plan)

GraphVersion.dsl = WorkflowDsl document (SoT authoring)
GraphVersion.temporal_plan = derived, required on PUBLISHED

GraphRecord 1──* GraphRun (engine)
GraphRun 1──1 ExecutionRecord (operator projection; same business run)
ExecutionRecord 1──* HumanCheckpoint
ExecutionRecord *──* Artifact / Evidence (refs)

Graph node AI_AGENT.agentIdentifier → SkillRecord.key
SkillRecord 1──* SkillVersion (SKILL.md, contracts, capabilities)
SkillVersion.interface_key → SkillInterface.key
SkillInterface → ArtifactContract (in/out)

Graph compile → Control packs by artifact type
ControlRecord 1──* ControlVersion
ControlEvaluation / Violation / Exception

RuleRecord 1──* RuleVersion (scope → skill|graph|workspace)
KnowledgeSpaceRecord 1──* SourceBinding
RuntimeProfileRecord 1──* RuntimeProfileVersion
GraphVersion MAY ref runtime_profile_key, knowledge_space_key

NodePreset (optional library, not runtime)
CapabilityDef ← MCP inventory
AuditEvent (append-only)
```

## 6.2. GraphRecord

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| workspace_id | string | default ok |
| key | string | unique; e2e/stage prefix allowed |
| name, description | string | |
| kind | e2e \| stage | |
| status | draft \| active \| deprecated \| archived | |
| launched | bool | только смысл для e2e |
| owner_team | string | |
| current_published_version_id | UUID? | |
| current_draft_version_id | UUID? | |
| created_at, updated_at | datetime | |
| revision | int | record-level |

## 6.3. GraphVersion

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| graph_id | UUID | FK |
| semantic_version | string | |
| status | DRAFT \| PUBLISHED \| DEPRECATED \| ARCHIVED | |
| dsl | JSON | document + ui |
| temporal_plan | JSON? | set on publish |
| validation_status | unknown \| valid \| invalid \| warning | |
| validation_report | JSON | |
| revision | int | optimistic lock draft |
| created_at, published_at, updated_at | datetime | |

## 6.4. GraphRun

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | |
| graph_id, version_id | UUID | pin |
| status | pending \| running \| waiting \| completed \| failed \| cancelled | |
| input, output, state | JSON | state.outputs, pending |
| events | JSON[] | |
| temporal_workflow_id | string? | null для local |
| error | string? | |
| created_at, updated_at | datetime | |

## 6.5. ExecutionRecord (оператор)

Поля FR-029. Обязательная связь `graph_id`, `graph_run_id`, `graph_version_id`. `flow_key` = graph.key для e2e. Стадии инспектора строятся из Temporal events / SUBFLOW имён, не из отдельного документа stages, если stages не проекция DSL.

## 6.6. Catalog entities (сжато)

Все: id, workspace_id, key, name, status, current_draft/published (или active) version id, timestamps, revision.

- **SkillVersion:** skill_markdown, files[], manifest, interface_key, contracts, allowed_capabilities, runtime_type, checksum.
- **RuleVersion:** content_markdown, scope_type, scope_selector, priority, conflict_strategy, language.
- **KnowledgeSpace:** purpose, space_type, classification, sources[], policies, freshness_hours.
- **RuntimeProfileVersion:** provider, model, sandbox, supervision, generation_config, limits, capabilities allow/deny, secret_ref, region, fallback.
- **ControlVersion:** control_type, severity, evaluation_point, expression, enforcement_*, applicability[], evidence_requirements.
- **HumanCheckpoint:** execution_id, type, status, blocking, artifact_*, decision_options, evidence, controls, selected_decision.
- **ArtifactContract:** key, json_schema, satisfies[], accepts[].
- **NodePreset:** name, node_type, label, config, kind?.
- **AuditEvent:** at, action, entity_type, entity_id, summary, actor.

## 6.7. Relationships that must not be inverted

- Worker/activity name **не** сущность, которую автор CRUD-ит; она следует из `config.type`.
- Connection **не** живёт без родительской версии графа.
- Stage в смысле YAML **не** таблица-SoT; «стадия» UX — либо SUBFLOW-узел e2e, либо отображаемое имя шага.
- Execution **не** создаётся без ссылки на graph version (кроме явно запрещённого legacy).

## 6.8. Retention and privacy

- Draft DSL: пока record не archived.
- Published DSL + plan: пока есть executions, ссылающиеся на version_id, плюс NFR-005.
- Checkpoints: как execution.
- Classification полей: DSL/config — INTERNAL; secret_ref — RESTRICTED (значение секрета не хранить); Work Item text — по Knowledge classification.

---

# 7. Constraints & Dependencies

- Temporal обязателен для live.
- React Flow канвас + FastAPI `/api/v1`.
- MCP SDK для интеграций.
- PostgreSQL — целевое хранилище control plane (NFR-003).
- Нельзя сделать авторский SoT из нормализованных `/nodes`+`/connections` без сборки документа: это сломает FR-006, FR-013, FR-015.
- Qwen Code CLI / GigaChat / LM Studio — опциональные provider'ы профиля.
- Docker Compose — среда разработки.

Зависимости продукта: Jira/Slack MCP, Temporal cluster, LLM endpoint.

Регуляторное: обязательные controls нельзя снять сценарием; exception — отдельная сущность ControlException с expiry и audit.

---

# 8. Traceability Matrix

Нет отдельного BRD; трассировка к продуктовым целям UX.

| Goal / Journey | Requirements |
|----------------|--------------|
| Собрать агента по пути Обзора | FR-002, FR-027, FR-028, FR-023, FR-021, FR-026, FR-016 |
| Нарисовать и сохранить сценарий | FR-005–FR-012, FR-016 |
| Не обойти контроль | FR-013, FR-014, FR-026, FR-003 |
| Опубликовать иммутабельный снимок | FR-017, FR-015 |
| Вооружить агента | FR-018, FR-019, FR-034 |
| Прогнать test без Temporal | FR-012, FR-037 |
| Исполнить skill через MCP | FR-036, FR-028, FR-022, FR-025 |
| Согласовать человеком | FR-031, FR-009, FR-035 |
| Наблюдать запуск | FR-029, FR-030, FR-032, FR-033 |
| Единый язык без Playbook/Agent | FR-003, FR-025, FR-016 |

---

# 9. Open Questions

1. Нужен ли отдельный `flow_type` (FEATURE_DELIVERY, …) на e2e record или достаточно tags? Пока: сохранить enum как метаданные каталога (P2).
2. Ручной live run unpublished: запрещён (FR-012). Подтвердить, что operator никогда не гоняет draft в Temporal.
3. Мульти-workspace UI: нет в текущем UX — P2.
4. Параллельные split без CONDITION (несколько исходящих с одного action): компилятор веток должен их видеть; уточнить визуальный контракт «неявного split».
5. Retry: новый GraphRun vs reset того же workflow id — целевое: новый run с ссылкой `retried_from` (P1).

---

# Приложение A. Gaps текущей реализации (не часть концепции)

Ниже — расхождения кода с этим SRS. Их надо закрывать переписыванием системы **под SRS**, а не ослаблением требований.

| Gap | Сейчас | Требование |
|-----|--------|------------|
| Dual SoT Flow + Graph | `FlowRecord.stages/edges` и `GraphVersion.dsl` зеркалятся | Один Graph DSL; catalog — проекция (FR-016) |
| JSON files | `config/platform/*.json` (+ legacy зеркала `flows.json`, `executions.json`, …) | Durable DB (NFR-003). Postgres сейчас: `workspaces` + опционально skills |
| Execution create | Часто пишет запись, не стартуя Temporal | FR-029 |
| Ingress fallback | `TaskLifecycleWorkflow` → classify → `run_configurable_pipeline` / JSON playbook templates | FR-034 graph-only для продукта |
| Hardcoded template map | `runtime_resolver.GRAPH_CHAIN_TEMPLATES` | Plan с published graph version |
| AI_AGENT без Gateway | `ai_agent_execute` → `execute_skill()` LLM-only, без tool loop | FR-036 / FR-028: tool calls через Capability Gateway |
| Local SUBFLOW | `local_run` не поднимает child plan | FR-037 тот же semantics, что Temporal |
| Agents API | `/agents`, `agents.json` | Убрать из IA (FR-003, FR-025) |
| domain.Playbook | leftover models; UI copy без «Плейбук», но DOM/API ещё `playbook_*` | Не SoT; вычистить идентификаторы |
| YAML-style CRUD nodes | отсутствует (правильно) | Не добавлять как авторский API (5.1.4) |

---

# Приложение B. Алгоритм compile_governance (псевдокод)

```text
doc ← normalize(parse(raw))
stamp untyped branches with GENERAL if publication exists
branches ← discover parallel paths (split → merge/leaf, skip governance nodes)
for each branch with artifact types:
    packs ← controls applicable to types
    gate ← immutable INTERNAL_SERVICE policy.evaluate
            (producer=last producing node, anchor=branch tip, packs, types)
    rewire: anchor → gate.pass → former successors of anchor
            gate.fail → last producer
produces(graph) ← union of node produces
return doc with gates + ui.positions
```

---

# Приложение C. Маппинг экранов → модули

| Экран UI | Модуль | Главные API |
|----------|--------|-------------|
| Обзор | overview | `/overview`, `/dashboard/summary` |
| Е2Е Сценарии | graphs + e2e catalog | `/flows*`, `/graphs*` |
| Дизайнер | graphs | `/graphs/{id}/draft\|validate\|publish`, `/runs` |
| Навыки | skills | `/skills*` |
| Правила | rules | `/rules*` |
| Области знаний | knowledge | `/knowledge-spaces*` |
| Профили | runtime_profiles | `/runtime-profiles*` |
| Запуски | e2e launch | `/launches`, `/flows/{id}/launch\|stop` |
| Согласования | checkpoints | `/human-checkpoints*` |
| Инспектор | executions + runs | `/executions/{id}`, `/runs/{id}/viewer\|state` |
| Контроли | controls | `/controls*` |
| Интеграции | integrations | `/integrations*`, `/mcp/servers` |
| Реестр способностей | capabilities | `/capabilities`, `/capability-manifests` |
| Аудит | audit | `/audit` |
