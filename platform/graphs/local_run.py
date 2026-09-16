"""In-process workflow runner for designer Test run (no Temporal)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional
from uuid import UUID

from src.orchestrator.activities_workflow import graph_record_event
from src.platform.graphs.expressions import enrich_run_input, normalize_hitl_decision, workflow_secrets
from src.platform.graphs.step_runtime import (
    ACTIVITY_FNS,
    eval_condition_step,
    map_step_outputs,
    render_activity_input,
    route_hitl_outlets,
)
from src.platform.graphs.temporal_steps import ActivityStep, ConditionStep, TemporalPlan

logger = logging.getLogger(__name__)


def spawn(run_id: UUID, plan: dict[str, Any]) -> None:
    """Start (or resume) a local run on the API event loop / a daemon thread."""

    async def _go() -> None:
        try:
            await tick(run_id, plan)
        except Exception:
            logger.exception("local run %s failed", run_id)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_go())
    except RuntimeError:
        import threading

        threading.Thread(target=lambda: asyncio.run(_go()), daemon=True).start()


async def tick(run_id: UUID, plan_dict: dict[str, Any] | None = None, *, signal: dict[str, Any] | None = None) -> None:
    from src.platform.graphs import service as graphs_svc

    run = graphs_svc.get_run(run_id)
    plan = TemporalPlan.from_dict(plan_dict or (run.state or {}).get("plan") or {})
    inputs = enrich_run_input(run.input or {})
    outputs: dict[str, Any] = dict((run.state or {}).get("outputs") or {})
    outputs.setdefault("trigger", dict(inputs))
    secrets = dict((run.state or {}).get("secrets") or {}) or workflow_secrets()
    context = {"inputs": inputs, "input": inputs, "outputs": outputs, "secrets": secrets}
    incoming = signal or (run.state or {}).get("resume_signal")
    if incoming:
        run.state = {**(run.state or {}), "resume_signal": None}
        graphs_svc.update_run(run)
    cursor = (run.state or {}).get("cursor") or (plan.step_order[0] if plan.step_order else None)
    if not cursor:
        _persist(run_id, status="completed", outputs=outputs, cursor=None, pending=None, error=None)
        return

    try:
        await graph_record_event({"run_id": str(run_id), "event": {"type": "local_tick", "cursor": cursor}})
    except Exception:
        logger.debug("local tick event skipped", exc_info=True)

    n = 0
    visits: dict[str, int] = {}
    while cursor and n < 10_000:
        n += 1
        visits[str(cursor)] = visits.get(str(cursor), 0) + 1
        if visits[str(cursor)] > 25:
            _persist(
                run_id,
                status="failed",
                outputs=outputs,
                cursor=cursor,
                pending=None,
                error=f"interpreter cycle guard exceeded at {cursor}",
            )
            return
        step = plan.steps.get(str(cursor))
        if step is None:
            _persist(run_id, status="failed", outputs=outputs, cursor=cursor, pending=None, error=f"unknown step {cursor}")
            return
        _persist(run_id, status="running", outputs=outputs, cursor=cursor, pending=None, error=None)
        if isinstance(step, ConditionStep):
            cursor = eval_condition_step(step, context)
            continue
        nxt, outputs, waiting = await _activity(step, context, run_id, incoming if n == 1 else None)
        context["outputs"] = outputs
        if waiting:
            _persist(
                run_id,
                status="waiting",
                outputs=outputs,
                cursor=step.id,
                pending={"node_id": step.id},
                error=None,
            )
            return
        if nxt is None:
            latest = graphs_svc.get_run(run_id)
            if latest.status == "failed" or latest.error:
                return
            _persist(run_id, status="completed", outputs=outputs, cursor=None, pending=None, error=None)
            return
        cursor = nxt
        incoming = None

    _persist(run_id, status="completed", outputs=outputs, cursor=None, pending=None, error=None)


async def _activity(
    step: ActivityStep,
    context: dict[str, Any],
    run_id: UUID,
    signal: dict[str, Any] | None,
) -> tuple[Optional[str], dict[str, Any], bool]:
    from src.platform.graphs import service as graphs_svc

    outputs: dict[str, Any] = dict(context.get("outputs") or {})
    if step.wait_for_signal and signal:
        prev = dict(outputs.get(step.id) or {})
        result = {**prev, "ok": True, "signal": dict(signal)}
        mapped = map_step_outputs(step, result)
        outputs[step.id] = mapped
        next_step = route_hitl_outlets(step, mapped)
        decision = normalize_hitl_decision(str((mapped.get("signal") or {}).get("decision") or ""))
        if next_step is None and decision in {"reject", "decline"}:
            _persist(
                run_id,
                status="failed",
                outputs=outputs,
                cursor=step.id,
                pending=None,
                error=f"human review rejected at {step.id} without a rejection outlet",
            )
        return next_step, outputs, False

    rendered = render_activity_input(step, context, run_id=str(run_id))
    fn = ACTIVITY_FNS.get(step.worker or step.activity_name)
    if fn is None:
        _persist(run_id, status="failed", outputs=outputs, cursor=step.id, pending=None, error=f"unknown activity {step.worker or step.activity_name}")
        return None, outputs, False
    try:
        result = await fn(rendered)
    except Exception as exc:
        if step.on_failure == "continue":
            result = {"ok": False, "continued": True, "error": str(exc), "response": {"body": None}, "signal": {}}
        else:
            _persist(run_id, status="failed", outputs=outputs, cursor=step.id, pending=None, error=str(exc))
            graphs_svc.append_run_event(run_id, {"type": "failed", "node": step.id, "error": str(exc)})
            return None, outputs, False

    if step.wait_for_signal:
        mapped = map_step_outputs(step, result if isinstance(result, dict) else {"response": result})
        outputs[step.id] = mapped
        return None, outputs, True

    mapped = map_step_outputs(step, result if isinstance(result, dict) else {"response": result})
    outputs[step.id] = mapped
    if step.outlets:
        from src.platform.graphs.governance import next_from_gate_outlets

        return next_from_gate_outlets(step.outlets, mapped, step.next_step), outputs, False
    return step.next_step, outputs, False


def _persist(
    run_id: UUID,
    *,
    status: str,
    outputs: dict[str, Any],
    cursor: Optional[str],
    pending: Optional[dict[str, Any]],
    error: Optional[str],
) -> None:
    from src.platform.graphs import service as graphs_svc

    try:
        run = graphs_svc.get_run(run_id)
        run.status = status  # type: ignore[assignment]
        run.state = {
            **(run.state or {}),
            "outputs": outputs,
            "cursor": cursor,
            "current_node_id": cursor,
            "pending_approval": pending,
            "engine": "local",
        }
        if error is not None:
            run.error = error
        graphs_svc.update_run(run)
    except Exception:
        logger.exception("persist local run %s", run_id)
