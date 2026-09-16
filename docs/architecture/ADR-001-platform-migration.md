# ADR-001: Миграция на AI Agent Platform

**Статус:** Accepted  
**Дата:** 2026-07-15  
**Контекст:** ветка `experiment`  
**Спека:** [CURSOR_AI_AGENT_PLATFORM_SPEC.md](../requirements/CURSOR_AI_AGENT_PLATFORM_SPEC.md)

## Решение

Эволюционируем текущий `auto_agent` в корпоративную **AI Agent Platform** с разделением **Control Plane** и **Runtime Plane**, без greenfield-rewrite всего runtime в одной итерации.

## Маппинг сущностей

| Было | Стало |
|------|--------|
| WorkflowTemplate / playbook JSON | Playbook (+ Flow graph) |
| Skill / skill manifest | Operator |
| Capability manifest | Capability |
| Tool Gateway | MCP Gateway |
| TaskLifecycleWorkflow | CaseWorkflow (целевой) |
| Task run / Temporal workflow | Execution |
| Artifact text в skill output | Artifact + ArtifactVersion + Evidence |
| Policy JSON (tool gateway) | Policy Pack + Execution Contract |

## Принципы

1. Платформа **не таск-трекер**: задачи приходят из Jira/Slack/SberTrack.
2. LLM предлагает действия; **Policy Engine + Contract + MCP Gateway** — hard gates.
3. MCP вызывается **только** через Gateway (существующий `tool_gateway` — база).
4. UI явно разделяет Control Plane и Runtime Plane.
5. Сначала vertical slice и UI shell, затем полная реструктуризация `apps/`/`core/` по спеке.

## Совместимость

- Kafka + Temporal + FastAPI + MCP Jira/Slack сохраняются.
- Текущие workflow JSON и skill manifests остаются источником seed/переходных данных.
- Flow Studio MVP опирается на существующий visual editor; типы узлов постепенно сходятся к спеке (Adaptive Zone, Approval, Publish).

## Out of scope этой итерации

- Полный BPMN / React Flow rewrite
- Multi-agent swarm
- Marketplace operators
- Qwen Code CLI subprocess (позже; сейчас LM Studio / GigaChat)
