# Implementation Plan: Visual Agent Workflow Builder Foundation

**Дата:** 2026-08-08  
**Обновлено:** 2026-08-08 (decision: Temporal остаётся на **Python SDK**)  
**Статус:** Stage 2 skeleton реализован (Temporal = Python SDK)  
**Цель:** архитектурный skeleton visual workflow builder (n8n / Langflow стиль) с исполнением через **Temporal Python SDK** (`temporalio`), typed Graph IR, compiler → ExecutablePlan, generic interpreter.

---

## 0. Решение по Temporal SDK

Требование исходного брифа упоминало Temporal TypeScript SDK.  
**Утверждённое отклонение:** в этом репозитории runtime **не мигрируем** на TypeScript.

- Temporal workflows / activities / worker остаются в `src/orchestrator/` на `temporalio`.
- Frontend остаётся на TypeScript/React только как UI.
- Не создаём `packages/temporal-runtime` (TS) и не вводим второй Temporal worker.

---

## 1. Исследование: текущее состояние репозитория

### 1.1 Структура (фактически)

| Область | Путь | Назначение |
|--------|------|------------|
| Platform API | `src/platform/` | FastAPI domain services, JSON store |
| Graphs domain | `src/platform/graphs/` | models, registry, compiler, service, policies |
| Graphs API | `src/platform/api_routes/graphs.py` | draft / publish / run / signals |
| Temporal (Python) | `src/orchestrator/` | `temporalio` worker, workflows, activities |
| Graph interpreter | `src/orchestrator/workflows/graph_interpreter.py` | generic plan interpreter |
| Graph activities | `src/orchestrator/activities_graph.py` | agent/tool/approval stubs+adapters |
| Legacy UI | `src/workflow_ui/` | static HTML/JS + React bridge embed |
| React builder | `frontend/` | Vite + React Flow (`@xyflow/react`) |
| Tests | `tests/test_graphs_*.py`, `tests/test_graph_interpreter.py` | compiler / smoke / thin interpreter |

Структура `apps/` + `packages/` **не вводится** — границы модулей сохраняем внутри существующих `src/platform/graphs`, `src/orchestrator`, `frontend`.

### 1.2 Что уже реализовано

1. Graph schema / ExecutablePlan — `src/platform/graphs/models.py`
2. Node registry — `registry.py`
3. Compiler — `compiler.py`
4. Temporal interpreter — `graph_interpreter.py`
5. Activities — `activities_graph.py`
6. API — `api_routes/graphs.py`
7. Frontend IR-driven designer — `frontend/src/`
8. Tests — domain / smoke / thin interpreter

---

## 2. Gap analysis (после решения про Python Temporal)

| Требование | Сейчас | Действие Stage 2 |
|------------|--------|------------------|
| Temporal Python SDK | уже есть | **оставить**, допилить skeleton |
| Shared contracts | Pydantic + frontend types | Выделить чёткие contracts-модули; frontend types mirror IR |
| `ExecutableNode` | `ExecutablePlanNode` | Alias `ExecutableNode = ExecutablePlanNode` |
| Signals `approve` / `reject` | один `human_decision` | Добавить отдельные signals (+ сохранить human_decision для compat) |
| `resume` как **Update** | signal `resume` | Добавить `@workflow.update`; API → execute_update |
| Query `getRunState` | query `state` | Добавить `getRunState` (readonly); `state` alias optional |
| Activity names | `graph_run_*` | Typed stubs + aliases `run_agent_activity` / names |
| Compiler error codes | частично | Унифицировать: EMPTY_GRAPH, MISSING_ENTRYPOINT, MISSING_NODE_REFERENCE, UNSUPPORTED_NODE_TYPE |
| Frontend run mode shell | нет | Добавить `RunModeShell` |
| `apps/packages` monorepo | нет | **не делать** — адаптируемся к `src/` |

### Не трогаем

- Playbooks/Flows/Skills CRUD, auth, billing, websockets, full DB migration
- Production agent logic
- Переписывание `TaskLifecycleWorkflow` / unrelated orchestrator
- Миграция Temporal на TypeScript

---

## 3. Архитектура (утверждено)

```text
frontend builder (React Flow)     — UI only, Graph IR SoT
        ↓
src/platform/graphs/              — contracts, registry, compiler, service
        ↓ ExecutablePlan
src/orchestrator/workflows/       — GraphInterpreterWorkflow (Python temporalio)
src/orchestrator/activities_graph.py
        ↑
src/platform/api_routes/graphs.py — draft / publish / run / HITL
```

Слои: frontend → graph contracts → compiler → temporal runtime (Python) → activities → API.

---

## 4. Файлы Stage 2

### Создать
- `src/platform/graphs/contracts.py` — re-exports + messaging payload models (или `messaging.py`)
- `src/platform/graphs/messaging.py` — Approve/Reject/Resume/GetRunState contracts
- `src/orchestrator/workflows/graph_messaging.py` — optional helpers (если нужно тонко)
- `frontend/src/shells/RunModeShell.tsx`
- `frontend/src/shells/BuilderShell.tsx` (тонкая обёртка, если полезно)
- доп. тесты в `tests/test_graphs_domain.py` / `tests/test_graph_interpreter.py`

### Изменить
- `src/platform/graphs/models.py` — `ExecutableNode` alias
- `src/platform/graphs/compiler.py` — единые коды ошибок + missing entrypoint на structural level
- `src/orchestrator/workflows/graph_interpreter.py` — approve/reject signals, resume update, getRunState
- `src/orchestrator/activities_graph.py` — typed stubs / aliases
- `src/platform/graphs/service.py` — signal→approve/reject; resume via update
- `src/platform/api_routes/graphs.py` — при необходимости выровнять контракты
- `frontend/src/types.ts` — run state types
- `frontend/src/main.tsx` / mounts — wire run shell if needed

### Не создавать
- `packages/temporal-runtime` (TS)
- `apps/temporal-worker` (TS)

---

## 5. Порядок реализации

1. Contracts + `ExecutableNode` + messaging models  
2. Compiler error code parity + tests  
3. Interpreter: signals / update / query + activity aliases  
4. Service/API wiring  
5. Frontend RunModeShell  
6. Tests + pytest green  

---

## 6. Messaging contracts (целевые, Python)

```python
class ApproveSignal(BaseModel):
    node_id: str
    comment: str | None = None
    actor_id: str | None = None

class RejectSignal(BaseModel):
    node_id: str
    reason: str | None = None
    actor_id: str | None = None

class ResumeUpdate(BaseModel):
    node_id: str | None = None
    payload: dict[str, Any] = {}

class RunStateSnapshot(BaseModel):
    status: str
    current_node_id: str | None = None
    outputs: dict[str, Any] = {}
    pending_approval: dict[str, Any] | None = None
    approvals: dict[str, Any] = {}
```

Workflow:
- `@workflow.signal(name="approve")`
- `@workflow.signal(name="reject")`
- `@workflow.update(name="resume")`
- `@workflow.query(name="getRunState")` — readonly
- legacy `human_decision` / `state` можно оставить как aliases

---

## 7. Compiler errors (structural)

| Code | Когда |
|------|-------|
| `EMPTY_GRAPH` | нет nodes |
| `MISSING_ENTRYPOINT` | нет entrypoints и нет trigger |
| `MISSING_NODE_REFERENCE` | edge source/target отсутствует |
| `UNSUPPORTED_NODE_TYPE` | type не в registry |

(Policy-specific codes e2e/stage остаются отдельно.)

---

## 8. Тесты

- Compiler happy path
- Compiler validation errors (4 кода выше)
- Registry resolution
- Branch / approval handle helpers
- Interpreter messaging unit tests (signals/update/query shape)
- Существующий smoke не ломать

---

## 9. Risks

| Риск | Митигация |
|------|-----------|
| Temporal Update API version | использовать `temporalio` workflow.update; fallback document if env old |
| Compat с уже запущенными workflows | сохранить `human_decision` signal |
| Frontend types drift | держать mirror рядом с Python contracts; документировать |

---

## 10. Done when

- [x] Plan file (updated; Temporal остаётся Python)
- [x] Typed contracts + ExecutableNode
- [x] Node registry (existing, verified)
- [x] Compiler skeleton + unified errors + tests
- [x] Temporal Python workflow: approve/reject/resume update/getRunState
- [x] Activity stubs/aliases
- [x] API wiring
- [x] Frontend run mode shell
- [x] pytest green for relevant suites

---

## 11. Команды проверки

```bash
python -m pytest tests/test_graphs_domain.py tests/test_graphs_smoke.py tests/test_graph_interpreter.py -q
cd frontend && npx tsc --noEmit
```
