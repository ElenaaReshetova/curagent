# Системные требования: Сценарий
## Модель данных, API, взаимодействие слоёв

| Поле | Значение |
|------|----------|
| Статус | Нормативный SoT среза «Сценарий» |
| Версия | 2.1 |
| Дата | 2026-08-17 |
| Замещает | v2.0 (две JSONB-таблицы без нормализованного графа) |
| Концепция слоёв | [SCENARIO.md](SCENARIO.md) |
| Физическая модель | PostgreSQL `workflows` + topology + executions (см. §6); YAML Workflow Engine — каталог сущностей, не авторский CRUD |

Один сценарий. Три статуса. Картинку меняет PUT. Статус меняет POST. Слои те же: UI → Parser → Runtime.

---

# 1. Introduction

## 1.1. Purpose

Сценарий — одна карточка с картинкой канваса. Автор не работает с «версиями», «черновик-эндпоинтами» и «вооружением» как с отдельными ресурсами.

## 1.2. Scope

Scenario, ScenarioRun, dsl, plan, статусы, API, алгоритмы слоёв.

Вне scope: skills, rules, controls, YAML-ноды, Flow+Graph dual-store, история версий как сущность.

## 1.3. Definitions

| Термин | Определение |
|--------|-------------|
| Scenario | Одна сущность: мета + dsl + plan + status |
| status | `draft` \| `published` \| `launched` |
| dsl | Картинка: узлы, соединения, координаты в `ui` |
| plan | План шагов. Появляется при переходе в `published`. Runtime больше dsl не видит |
| ScenarioRun | Прогон. В момент старта копирует `plan` (пин). Дальнейшие правки сценария его не меняют |

## 1.4. References

`docs/requirements/SCENARIO.md` — три слоя.

---

# 2. Overall Description

## 2.1. Статусы

```text
        PUT dsl (только здесь)
(draft) ──────────────────────────► (draft)
   │
   │ POST { status: "published" }     validate + parser → plan
   ▼
(published) ── POST { status: "launched" } ──► (launched)
   ▲                                              │
   └──────── POST { status: "published" } ────────┘
                    (снять с агента, снимок тот же)

(published | launched) ── POST { status: "draft" } ──► (draft)
                    (можно снова править dsl; агент его не берёт)
```

Смысл:

| status | Можно PUT dsl | Агент берёт на work item | plan |
|--------|---------------|--------------------------|------|
| draft | да | нет | null или устаревший, runtime не использует |
| published | нет | нет | обязателен, заморожен |
| launched | нет | да, только kind=e2e | тот же замороженный |

Идущие Run не убиваются сменой статуса: у них свой скопированный plan.

## 2.2. Слои

```text
PUT dsl          → UI + store (+ validate, без plan)
POST status=published → Parser пишет plan
POST status=launched  → только статус
POST /runs       → Runtime получает копию plan
```

## 2.3. Constraints

- Нет отдельных ресурсов Version, Node, Connection, Stage.
- Нет URL `/draft`, `/publish`, `/launch`.
- Runtime не читает dsl.
- `launched` только для `kind=e2e`.
- Live run стартует только из `launched`. Test run — из любого статуса, plan собирается на лету из текущего dsl.

## 2.4. Users

Автор: PUT dsl, POST status. Оператор/агент: POST runs, signals. Ingress: найти `status=launched`.

---

# 3. Functional Requirements

### FR-001 Одна карточка Scenario
**P0**

Автор видит одну карточку: мета + dsl + status. Версии — физический снимок для publish/run, не отдельный экран.

**Acceptance:** Given GET /scenarios/{id}, When смотрим тело, Then есть `status`, `dsl`, и `plan` (null в draft).

### FR-002 Три статуса
**P0**

Допустимы только `draft`, `published`, `launched`. Переход — POST тела `{ "status": "…" }` на тот же id.

**Acceptance:** Given status=draft, When POST `{status:"launched"}`, Then 400 (нет plan / нельзя прыгнуть). Given published, When POST `{status:"launched"}`, Then 200 launched, parser не вызывался.

### FR-003 PUT только в draft
**P0**

PUT меняет `name`, `description`, `dsl`. Если status ≠ draft → 409 `NOT_DRAFT`.

**Acceptance:** Given launched, When PUT dsl, Then 409, dsl на диске не изменился.

### FR-004 Переход в published собирает plan
**P0**

`draft → published`: validate dsl; если ok — parser → записать plan, status=published. Если не ok — 400, статус не меняется.

**Acceptance:** Given невалидный dsl, When POST published, Then 400, status=draft, plan не записан. Given валидный, Then plan.steps покрывает не-trigger узлы, в plan нет `ui`.

### FR-005 published → launched без parser
**P0**

Только kind=e2e. Stage → 400. plan уже должен быть.

**Acceptance:** Given e2e published, When POST launched, Then status=launched, plan байт-в-байт тот же.

### FR-006 Возврат в draft
**P0**

`published|launched → draft`: status=draft, launched снимается. dsl остаётся. plan можно оставить (для просмотра), но live ingress его не берёт. PUT dsl снова разрешён; при следующем published plan пересчитывается.

**Acceptance:** Given launched и running Run, When POST draft, Then Run продолжает идти по своему pinned plan; новых ingress на этот сценарий нет.

### FR-007 Пин plan на Run
**P0**

При старте run копирует `plan` (live: с Scenario; test: свежий parse dsl) в Run.plan. Runtime читает только Run.plan.

**Acceptance:** Given launched run, When сценарий вернули в draft и изменили dsl, Then GET run viewer показывает старый plan, interpreter не видит новую картинку.

### FR-008 Test run не требует launched
**P0**

POST /runs `{ "mode": "test" }` парсит текущий dsl (даже draft), local interpreter. Temporal не обязателен.

### FR-009 Live только launched
**P0**

POST /runs `{ "mode": "live" }` или ingress: scenario.status должен быть launched. Иначе 400 `NOT_LAUNCHED`.

### FR-010 HITL signal
**P0**

INPUT → run.status=waiting. POST `/runs/{id}/signal` `{ "decision": "approve"|"reject", "node_id"? }`.

### FR-011 Subflow
**P0**

Ключ дочернего Scenario. Для live child берётся **plan дочернего, если он published или launched**. Если ребёнок draft — fail шага. Child Run с `parent_run_id`.

### FR-012 Атомарный dsl
**P0**

PUT заменяет весь dsl. Нет CRUD одной ноды.

### FR-013 Optimistic lock
**P0**

Scenario.revision. PUT без актуального revision → 409 `REVISION_CONFLICT`. POST status тоже шлёт revision.

### FR-014 Слои не прыгают
**P0**

PUT не принимает поле `plan` (400). Runtime не ходит за dsl. Parser не стартует Temporal.

---

# 4. Non-Functional Requirements

- GET список p95 < 200 ms (без dsl в списке).
- PUT dsl p95 < 400 ms при ≤ 80 узлах.
- POST status=published p95 < 800 ms при ≤ 80 узлах.
- GET run state p95 < 200 ms.
- PUT/POST status сериализуются на scenario id.
- После 200 published plan читается после рестарта.
- Целевой store: PostgreSQL, §6. Не JSON-файлы flow+graph.
- Test run жив без Temporal. Live без Temporal → 503, run=failed.
- В dsl не хранить секреты.

---

# 5. API

База `/api/v1`. Ошибка: `{ "error": { "code", "message", "issues": [] } }`.

Коды: `NOT_FOUND`, `BAD_REQUEST`, `REVISION_CONFLICT`, `NOT_DRAFT`, `VALIDATION_FAILED`, `NOT_LAUNCHED`, `BAD_TRANSITION`, `AMBIGUOUS_LAUNCH`, `NO_LAUNCHED_SCENARIO`, `RUNTIME_UNAVAILABLE`, `RUN_NOT_WAITING`.

## 5.1. Сценарии — четыре ручки

| Method | Path | Зачем |
|--------|------|--------|
| GET | `/scenarios` | список |
| POST | `/scenarios` | создать (status=draft) |
| GET | `/scenarios/{id}` | карточка + dsl + plan |
| PUT | `/scenarios/{id}` | обновить картинку/имя (draft) |
| POST | `/scenarios/{id}` | сменить status |
| DELETE | `/scenarios/{id}` | удалить, если нет running/waiting |

`{id}` — UUID или key.

Это весь control-plane сценария. Не добавлять `/draft`, `/publish`, `/launch`, `/versions`.

### GET `/scenarios`

Query: `kind`, `status`, `q`, `page` (0), `limit` (50).

Список **без** dsl и plan:

```json
{
  "items": [
    {
      "id": "…",
      "key": "slack-brd-delivery",
      "name": "Slack BRD",
      "kind": "e2e",
      "status": "launched",
      "updated_at": "2026-08-14T10:00:00Z"
    }
  ],
  "total": 1
}
```

Каталог Е2Е: `?kind=e2e`. «Запуски»: `?kind=e2e` и колонка status (published = есть снимок, не у агента; launched = у агента).

### POST `/scenarios`

```json
{ "key": "slack-brd-delivery", "name": "Slack BRD", "kind": "e2e", "description": "" }
```

201: сценарий в `draft`, dsl = Trigger, plan=null, revision=1. 409 если key занят.

### GET `/scenarios/{id}`

```json
{
  "id": "…",
  "key": "slack-brd-delivery",
  "name": "Slack BRD",
  "description": "",
  "kind": "e2e",
  "status": "draft",
  "revision": 4,
  "dsl": { },
  "plan": null,
  "canvas": { },
  "validation": { "ok": true, "issues": [] },
  "created_at": "…",
  "updated_at": "…"
}
```

`canvas` — проекция dsl для дизайнера, не колонка БД.

### PUT `/scenarios/{id}`

```json
{
  "revision": 4,
  "name": "Slack BRD",
  "description": "",
  "dsl": { }
}
```

`dsl` — или canvas IR (сервер приводит к dsl). Поле `plan` запрещено. Поле `status` в PUT игнорируется или 400: статус только POST.

ALG-SAVE. 200 полное тело GET. 409 `NOT_DRAFT` / `REVISION_CONFLICT`. Черновик с ошибками канваса сохраняется, `validation.ok=false`.

### POST `/scenarios/{id}`

```json
{ "revision": 4, "status": "published" }
```

`status` обязателен. ALG-STATUS.

| Сейчас | Запрос | Результат |
|--------|--------|-----------|
| draft | published | parser → plan, freeze |
| published | launched | если e2e |
| launched | published | снять с агента |
| published или launched | draft | снова можно PUT |
| draft | launched | 400 `BAD_TRANSITION` |
| launched | launched | 200 идемпотентно |
| published | published | 200 идемпотентно |

### DELETE `/scenarios/{id}`

204. 409 если есть run в running/waiting.

## 5.2. Прогоны

| Method | Path | Зачем |
|--------|------|--------|
| POST | `/runs` | старт |
| GET | `/runs/{id}` | запись |
| GET | `/runs/{id}/state` | для поллинга |
| POST | `/runs/{id}/signal` | HITL |
| POST | `/runs/{id}/cancel` | отмена |

### POST `/runs`

```json
{
  "scenario_id": "…",
  "mode": "live",
  "input": { "title": "INC-1", "text": "…" }
}
```

`mode`: `live` | `test`. Вместо id можно `scenario_key`.

201 Run (включая скопированный plan не обязательно в коротком ответе; в GET полном — да).

### GET `/runs/{id}/state`

```json
{
  "status": "waiting",
  "current_node_id": "input-1",
  "outputs": {},
  "pending_approval": { "node_id": "input-1" },
  "error": null,
  "run_id": "…"
}
```

### GET `/runs/{id}`

Run + `dsl_snapshot` опционально для viewer (копия dsl на старте, P1). Минимум: pinned `plan` + state.

### POST `/runs/{id}/signal`

```json
{ "decision": "approve", "node_id": "input-1", "comment": "" }
```

`decision`: `approve` | `reject`. 400 `RUN_NOT_WAITING`.

### POST `/runs/{id}/cancel`

status=cancelled.

## 5.3. Ingress

Внутренний вызов, не третья публичная «ручка сценария»:

```json
{ "task_id": "…", "source": "slack", "source_id": "…", "title": "…", "text": "…", "scenario_key": null }
```

Ищет `kind=e2e` и `status=launched`. Ноль → `NO_LAUNCHED_SCENARIO`. Несколько без key → `AMBIGUOUS_LAUNCH`. Дальше как live POST /runs. Идемпотентность по source+source_id.

## 5.4. UI → API

| Кнопка | Вызов |
|--------|--------|
| Сохранить | `PUT /scenarios/{id}` `{revision, dsl}` |
| Опубликовать | `POST /scenarios/{id}` `{revision, status:"published"}` |
| Запустить / снять | `POST /scenarios/{id}` `{status:"launched"|"published"}` |
| Править снова | `POST /scenarios/{id}` `{status:"draft"}` |
| Test | `POST /runs` `{mode:"test"}` |
| Утвердить | `POST /runs/{id}/signal` `{decision:"approve"}` |

Палитра: `GET /schemas/node-types?kind=` — схема узлов, не сущность сценария.

## 5.5. Запрещено в авторском API

`/scenarios/{id}/draft|publish|launch`, PATCH plan, поэлементный CRUD ноды как способ сохранить канвас.

Физические таблицы `node_types`, `workflow_stages`, `workflow_connections` — проекция PUT dsl, не публичный контракт дизайнера. YAML `/nodes` `/stages` `/connections` не экспонируем как авторские ручки.

Старые `/flows` `/graphs` — адаптеры на этот контракт.

---

# 6. Data Requirements

Сценарий в продукте = `workflows`. Авторский документ по-прежнему атомарный workflow DSL; в БД он раскладывается по таблицам.

```text
node_types 1──* temporal_activities
workflows 1──* workflow_versions 1──* workflow_stages
                              └────* workflow_connections
workflows 1──* executions 1──* execution_steps
executions.workflow_version_id → pinned snapshot
execution_steps.stage_id → workflow_stages (SET NULL)
```

## 6.0. Расхождения с Workflow Engine API.yaml

YAML принят как каталог сущностей. Ниже — где схема YAML недостаточна, и что сделано вместо этого.

1. **`Node` без `workflowId`, но с `dsl`.** Это смешение каталога типов и инстанса на канвасе. Каталог — `node_types` (`type` ∈ Trigger/Activity/Input/Condition, `subtype` = `config.type`, `key` = canvas type). Инстанс — `workflow_stages`.
2. **`Node.required` содержит `worker`, поля `worker` нет.** Баг YAML. Worker живёт в `temporal_activities`.
3. **`Connection` только `workflow` + `dsl`.** Нет source/target — нельзя повесить FK и искать исходящие рёбра. Колонки `source_stage_id`, `target_stage_id`, `source_outlet`, `source_option`, `fallback`; `dsl` хранит полный workflow-edge.
4. **Версия на той же строке Workflow + `GET /workflows/{id}/versions` возвращает Workflow.** Невозможно хранить историю и пин прогона. Отдельная `workflow_versions`: integer `version_number` (YAML `version`), `dsl`, `plan`. Execution ссылается на version id, не на «текущую» строку.
5. **Stage без version.** Правка published графа переписала бы историю execution. Stage/connection принадлежат `workflow_version_id`; `workflow_id` денормализован для фильтра YAML `?workflowId=`.
6. **Нет шагов прогона.** YAML Execution — только шапка. Инспектор и HITL требуют `execution_steps` (status по узлу, input/output, attempt).
7. **Нет `kind` / draft-published-launched.** Без них нельзя отличить e2e от stage и вооружить агента. `workflows.kind`, `status`, `launched`.
8. **Поэлементный CRUD `/nodes` `/connections` как авторский контракт.** Канвас сохраняет документ целиком (FR-012). PUT dsl транзакционно пересобирает stages/connections. Runtime читает pinned `plan`, не «живые» строки стадий.
9. **`segmentId` string vs workspace.** `segment_id` TEXT + `workspace_id` UUID FK на `workspaces`.
10. **Enum типов слишком узкий.** YAML: Trigger/Activity/Input/Condition. Палитра шире (AI Agent, Kafka, Subflow, …) — это `subtype`/`key`, family остаётся четырьмя значениями YAML.

## 6.1. workflows (Scenario)

| Колонка | Тип | Правила |
|---------|-----|---------|
| id | UUID PK | |
| workspace_id | UUID FK workspaces | |
| key | TEXT | UNIQUE (workspace_id, key) |
| name | TEXT | NOT NULL |
| description | TEXT | default `''` |
| kind | TEXT | `e2e` \| `stage` |
| segment_id | TEXT | YAML `segmentId`, default `default` |
| status | TEXT | `draft` \| `active` \| `deprecated` \| `archived` (product: draft / published / launched через status+launched) |
| launched | BOOL | агент берёт только `kind=e2e` AND launched |
| version | INT | текущий `version_number` (YAML autoincrement) |
| created_by, updated_by | TEXT | |
| current_published_version_id | UUID | без FK-цикла |
| current_draft_version_id | UUID | |
| revision | INT | optimistic lock канваса |
| created_at, updated_at | TIMESTAMP | |

## 6.2. workflow_versions

| Колонка | Тип | Правила |
|---------|-----|---------|
| id | UUID PK | |
| workflow_id | UUID FK | ON DELETE CASCADE |
| version_number | INT | UNIQUE (workflow_id, version_number) |
| semantic_version | TEXT | `0.1.0` |
| status | TEXT | `DRAFT` \| `PUBLISHED` \| `DEPRECATED` \| `ARCHIVED` |
| dsl | JSONB | полный workflow-документ для round-trip канваса |
| plan | JSONB | Temporal plan; NULL пока DRAFT после правок |
| validation_status, validation_report | TEXT / JSONB | |
| revision | INT | |
| published_at | TIMESTAMP | NULL в draft |

CHECK: `status='PUBLISHED' ⇒ plan IS NOT NULL`.

## 6.3. node_types + temporal_activities

`node_types`: `key`, `type` (Trigger/Activity/Input/Condition), `subtype`, `description`, `dsl` (schema/ports палитры).

`temporal_activities`: `node_type_id`, `worker` (task queue, default `default`), `activity_name` (§6.6).

## 6.4. workflow_stages (YAML Stage)

Инстанс узла на версии. `identifier` = `nodes[].identifier`. `name` = title. `node_type_id` FK. `pos_x`/`pos_y` из `ui.positions`. `dsl` = workflow node object.

UNIQUE (workflow_version_id, identifier).

## 6.5. workflow_connections (YAML Connection)

`source_stage_id` / `target_stage_id` NOT NULL. Outlet/option/fallback — колонки. `dsl` = connection object.

## 6.6. executions (YAML Execution) + execution_steps

Execution: `workflow_id`, `workflow_version_id`, `version` (int), `status`, `mode` live\|test, `started_by`/`ended_by`, `iteration`, `request_id`, `input_json`/`output_json`/`state_json`, **pinned `plan`**, `dsl_snapshot`, `events_json`, `temporal_workflow_id` UNIQUE NULL, `parent_execution_id`, `error`.

ON DELETE RESTRICT с workflows — нельзя удалить сценарий с историей прогонов, пока executions живы.

`execution_steps`: `execution_id`, `stage_id` NULL, `node_identifier`, `step_kind` activity\|condition, `status`, `attempt`, input/output JSON, timestamps. UNIQUE (execution_id, node_identifier).

Индексы: `(workflow_id)`, `(status)`, unique `temporal_workflow_id`.

Retention runs ≥ 90 дней.

## 6.7. dsl / plan / типы узлов

dsl — workflow-документ: `identifier`, `title`, `nodes[]`, `connections[]`, `ui.positions`, `ui.kind`. Нет End. plan — `name`, `version`, `trigger`, `inputs`, `step_order`, `steps`. Без `ui`.

| Canvas | config.type | activity |
|--------|-------------|----------|
| trigger | SELF_SERVE_TRIGGER / EVENT_TRIGGER / SCHEDULE_TRIGGER | нет |
| ai_agent | AI_AGENT | ai_agent_execute |
| ai | AI | ai_generate_summary |
| webhook | WEBHOOK | http_webhook |
| upsert_entity | UPSERT_ENTITY | upsert_entity |
| kafka | KAFKA | kafka_publish |
| integration_action | INTEGRATION_ACTION | integration_action |
| internal_service | INTERNAL_SERVICE | internal_service |
| subflow | SUBFLOW | execute_subflow |
| condition | CONDITION | condition |
| input | INPUT | human_review |

## 6.8. Не хранить как SoT

JSON-файлы `graph_records.json` / `flow_records.json` (только fallback без `PLATFORM_DATABASE_URL`). Секреты в dsl. Авторский CRUD одной ноды.

---

# 7. Алгоритмы

## ALG-IR

Если PUT пришёл как canvas IR (`nodes[].id` + `position`) — сервер пишет dsl. GET отдаёт `canvas` проекцией. Parser IR не видит.

## ALG-SAVE (PUT)

```text
if scenario.status != draft → 409 NOT_DRAFT
if body.revision != scenario.revision → 409 REVISION_CONFLICT
if "plan" in body → 400
dsl ← IR? convert : body.dsl
report ← Parser.validate(dsl)
scenario.dsl ← dsl
scenario.plan ← null          # устарел до следующего published
scenario.validation_* ← report
scenario.revision += 1
commit
```

Runtime не вызывается.

## ALG-STATUS (POST)

```text
if body.revision != scenario.revision → 409
from, to ← scenario.status, body.status

to == from → 200 no-op

from=draft, to=published:
    report ← Parser.validate(dsl)
    if not ok → 400 VALIDATION_FAILED
    scenario.plan ← Parser.parse(normalize(dsl))
    scenario.status ← published

from=published, to=launched:
    if kind != e2e → 400
    scenario.status ← launched

from=launched, to=published:
    scenario.status ← published

from in (published, launched), to=draft:
    scenario.status ← draft
    # plan оставляем; PUT его обнулит

иначе → 400 BAD_TRANSITION
revision += 1
commit
```

Ни один переход кроме `draft→published` не вызывает parser. Ни один не стартует run.

## ALG-START-RUN

```
test:
  validate dsl; parse → plan_copy
  insert Run(mode=test, plan=plan_copy, dsl_snapshot=dsl)
  local interpreter(run_id, plan_copy, input)

live:
  if status != launched → 400 NOT_LAUNCHED
  plan_copy ← scenario.plan
  insert Run(mode=live, plan=plan_copy, dsl_snapshot=dsl)
  Temporal.start(Interpreter, {run_id, plan: plan_copy, input})
```

## ALG-INTERPRET

```text
outputs[trigger] ← input
current ← plan.step_order[0]
пока current:
  activity → execute, outputs[id] ← result
  subflow → child plan из дочернего Scenario (published|launched), nested interpret
  condition → expression → next
  wait_for_signal → status=waiting; ждать signal; next по outlet
  current ← next_step / outlet
  нет ребра → completed
```

## ALG-SIGNAL

status=waiting иначе 400. live → Temporal signal. test → local resume.

## ALG-INGRESS

```
candidates ← Scenario where kind=e2e and status=launched
выбор по scenario_key или единственный кандидат
иначе NO_LAUNCHED / AMBIGUOUS
идемпотентность source+source_id
ALG-START-RUN live
```

## Последовательность

```text
POST /scenarios
PUT  /scenarios/{id}              dsl
POST /scenarios/{id} {published}  plan
POST /scenarios/{id} {launched}   агент
ingress / POST /runs live
poll GET /runs/{id}/state
POST /runs/{id}/signal {approve}
```

---

# 8. Constraints

Temporal — live. Local loop — test. PostgreSQL JSONB. Канвас на клиенте. Имена activity = §6.5.

---

# 9. Traceability

| Goal | Где |
|------|-----|
| Один объект, три статуса | FR-001–006, §5.1 POST |
| Картинка ≠ статус | PUT vs POST, ALG-SAVE / ALG-STATUS |
| Три слоя | FR-004, FR-014, ALG-INTERPRET |
| Правка не бьёт идущий прогон | FR-007 пин на Run |
| Без /draft /publish /launch | §5.1, §5.5 |

---

# 10. Open Questions

1. Несколько launched e2e без key — пока ошибка. Правила маршрутизации — следующий срез.
2. `dsl_snapshot` на Run обязателен с v2 или P1 — default: писать, инспектор не ходит в Scenario.dsl.
3. Stage `launched` запрещён — да.

---

# Приложение. Что выкинули из v1.0 SRS

Таблица Version, указатели draft/published version, URL `/draft` `/publish` `/launch` `/versions`, флаг `launched` отдельно от status, создание нового DRAFT row после publish.
