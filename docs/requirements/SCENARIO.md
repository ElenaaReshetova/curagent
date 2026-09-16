# Сценарий: три слоя

Норматив данных/API: [SCENARIO_SRS.md](SCENARIO_SRS.md) **v2.1**.

Один сценарий, три статуса (`draft` | `published` | `launched`). Картинку меняет `PUT`. Статус — `POST { status }` на тот же id. Нет `/draft`, `/publish`, `/launch`.

```text
UI  ──PUT dsl──►  картинка
POST status=published ──► Parser ──► plan
POST status=launched  ──► агент берёт этот plan
Runtime ──идёт──► по копии plan на Run
```

## Слои

**UI** — каталог и канвас. Не знает Temporal.

**Parser** — только на переход в `published`: dsl → plan.

**Temporal runtime** — только plan с Run (пин при старте). Local test — тот же цикл.

## Сущность

Карточка Scenario: `key`, `kind`, `status`, `dsl`, `plan`. В БД это `workflows` + `workflow_versions` (dsl/plan) + нормализованные `workflow_stages` / `workflow_connections`.  
Прогон (`executions`) копирует `plan` в момент старта и пишет `execution_steps` — возврат в draft не ломает уже идущее.
