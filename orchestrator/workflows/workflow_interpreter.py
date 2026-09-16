"""Temporal interpreter for workflows (via TemporalPlan steps)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.orchestrator.activities_workflow import (
        ai_agent_execute,
        ai_generate_summary,
        graph_record_event,
        graph_update_run_state,
        http_webhook,
        human_review,
        execute_subflow,
        integration_action,
        internal_service,
        kafka_publish,
        upsert_entity,
    )
    from src.platform.graphs.expressions import normalize_hitl_decision
    from src.platform.graphs.governance import next_from_gate_outlets
    from src.platform.graphs.step_runtime import (
        ACTIVITY_FNS,
        eval_condition_step,
        map_step_outputs,
        render_activity_input,
        route_hitl_outlets,
    )
    from src.platform.graphs.temporal_steps import ActivityStep, ConditionStep, TemporalPlan

_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=3,
)
_NO_RETRY = RetryPolicy(maximum_attempts=1)
_NON_IDEMPOTENT_ACTIVITIES = frozenset({
    "http_webhook",
    "human_review",
    "integration_action",
    "internal_service",
    "kafka_publish",
    "upsert_entity",
})
_MAX_INTERPRETER_STEPS = 10_000
_MAX_VISITS_PER_NODE = 25


def _activity_retry_policy(activity_name: str) -> RetryPolicy:
    """Only retry activities whose contract is safe to invoke repeatedly."""
    return _NO_RETRY if activity_name in _NON_IDEMPOTENT_ACTIVITIES else _RETRY


def _deterministic_run_input(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize ingress fields without consulting worker environment state."""
    inputs = dict(raw or {})
    source_id = str(inputs.get("source_id") or "").strip()
    if source_id.startswith("slack:"):
        parts = source_id.split(":", 2)
        if len(parts) == 3:
            inputs.setdefault("channel", parts[1])
            inputs.setdefault("thread_ts", parts[2])
    if not str(inputs.get("text") or "").strip():
        for key in ("description", "title"):
            value = str(inputs.get(key) or "").strip()
            if value:
                inputs["text"] = value
                break
    return inputs


@workflow.defn(name="WorkflowInterpreter")
class WorkflowInterpreter:
    def __init__(self) -> None:
        self._status = "running"
        self._current: Optional[str] = None
        self._outputs: dict[str, Any] = {}
        self._approvals: dict[str, Any] = {}
        self._pending: Optional[dict[str, Any]] = None
        self._run_id = ""
        self._error: Optional[str] = None

    @workflow.signal(name="approve")
    def approve(self, payload: dict[str, Any]) -> None:
        self._apply(payload or {}, "approve")

    @workflow.signal(name="reject")
    def reject(self, payload: dict[str, Any]) -> None:
        self._apply(payload or {}, "reject")

    @workflow.signal(name="decline")
    def decline(self, payload: dict[str, Any]) -> None:
        self._apply(payload or {}, "decline")

    @workflow.signal(name="request_changes")
    def request_changes(self, payload: dict[str, Any]) -> None:
        self._apply(payload or {}, "request_changes")

    @workflow.signal(name="human_decision")
    def human_decision(self, payload: dict[str, Any]) -> None:
        self._apply(payload or {}, str((payload or {}).get("decision") or "approve"))

    @workflow.signal(name="review_decision")
    def review_decision(self, payload: dict[str, Any]) -> None:
        self._apply(payload or {}, str((payload or {}).get("decision") or "approve"))

    @workflow.update(name="resume")
    async def resume(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._apply(payload or {}, str((payload or {}).get("decision") or "resume"))
        return self.get_run_state()

    @workflow.query(name="getRunState")
    def get_run_state(self) -> dict[str, Any]:
        return {
            "status": self._status,
            "current_node_id": self._current,
            "outputs": dict(self._outputs),
            "pending_approval": self._pending,
            "approvals": dict(self._approvals),
            "run_id": self._run_id,
            "error": self._error,
        }

    def _apply(self, payload: dict[str, Any], decision: str) -> None:
        nested = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        signal_payload = {**nested, **payload}
        signal_payload.pop("payload", None)
        node_id = str(signal_payload.get("node_id") or signal_payload.get("nodeId") or self._current or "")
        mapped = normalize_hitl_decision(str(signal_payload.get("decision") or decision))
        signal = {
            "decision": mapped,
            "node_id": node_id,
            "nodeId": node_id,
            "changeText": signal_payload.get("changeText") or signal_payload.get("comment") or "",
            "rejectionReason": signal_payload.get("rejectionReason") or signal_payload.get("reason") or "",
            "comment": signal_payload.get("comment") or "",
            "reason": signal_payload.get("reason") or signal_payload.get("comment") or "",
            **signal_payload,
        }
        signal["decision"] = mapped
        if node_id:
            self._approvals[node_id] = {"resolved": True, "decision": mapped, "payload": signal}

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._run_id = str(payload.get("run_id") or "")
        plan = TemporalPlan.from_dict(payload.get("plan") or payload.get("dsl") or {})
        inputs = _deterministic_run_input(payload.get("input") or {})
        secrets = dict(payload.get("secrets") or {})
        self._outputs["trigger"] = dict(inputs)
        context = {
            "inputs": inputs,
            "input": inputs,
            "outputs": self._outputs,
            "secrets": secrets,
            "workflow": {"name": plan.name, "version": plan.version},
        }

        start = payload.get("resume_from") or (plan.step_order[0] if plan.step_order else None)
        if not start:
            self._status = "completed"
            return {"ok": True, "outputs": {}, "run_id": self._run_id}

        await workflow.execute_activity(
            graph_record_event,
            {"run_id": self._run_id, "event": {"type": "started", "entrypoint": start, "event_id": "started"}},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY,
        )

        current: Optional[str] = str(start)
        n = 0
        visits: dict[str, int] = {}
        while current and n < _MAX_INTERPRETER_STEPS:
            n += 1
            visits[current] = visits.get(current, 0) + 1
            if visits[current] > _MAX_VISITS_PER_NODE:
                self._error = f"interpreter cycle guard exceeded at {current}"
                break
            step = plan.steps.get(current)
            if step is None:
                self._error = f"unknown step {current}"
                break
            self._current = current
            await workflow.execute_activity(
                graph_record_event,
                {"run_id": self._run_id, "event": {"type": "step", "node": current, "title": getattr(step, "name", current), "event_id": f"step:{n}:{current}"}},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=_RETRY,
            )
            if isinstance(step, ActivityStep):
                current = await self._activity(step, context)
            else:
                current = eval_condition_step(step, context, approvals=self._approvals)
            if self._error:
                break

        if current and not self._error and n >= _MAX_INTERPRETER_STEPS:
            self._error = (
                f"interpreter cycle guard exceeded after {_MAX_INTERPRETER_STEPS} steps "
                f"at {current}"
            )

        self._status = "failed" if self._error else "completed"
        await workflow.execute_activity(
            graph_update_run_state,
            {
                "run_id": self._run_id,
                "status": self._status,
                "state": {"outputs": self._outputs, "approvals": self._approvals, "current_node_id": self._current},
                "output": self._outputs,
                "error": self._error,
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY,
        )
        return {"ok": not bool(self._error), "outputs": self._outputs, "run_id": self._run_id, "error": self._error}

    async def _activity(self, step: ActivityStep, context: dict[str, Any]) -> Optional[str]:
        rendered = render_activity_input(step, context, run_id=self._run_id)
        activity_name = step.worker or step.activity_name
        fn = ACTIVITY_FNS.get(activity_name)
        if fn is None:
            self._error = f"unknown activity {activity_name}"
            return None
        if isinstance(rendered, dict):
            rendered.setdefault("idempotency_key", f"{self._run_id}:{step.id}")
        try:
            result = await workflow.execute_activity(
                fn,
                rendered,
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=_activity_retry_policy(activity_name),
            )
            if activity_name == "execute_subflow" and isinstance(result, dict) and result.get("plan"):
                child_input = result.get("input") if isinstance(result.get("input"), dict) else {}
                if isinstance(rendered, dict) and isinstance(rendered.get("input"), dict):
                    child_input = {**child_input, **rendered["input"]}
                result = await workflow.execute_child_workflow(
                    WorkflowInterpreter.run,
                    {
                        "run_id": result.get("child_run_id") or f"{self._run_id}:{step.id}",
                        "plan": result["plan"],
                        "input": child_input,
                        "secrets": dict(context.get("secrets") or {}),
                    },
                    id=f"{self._run_id}-sub-{step.id}",
                )
        except Exception as exc:
            if step.on_failure == "continue":
                result = {"ok": False, "continued": True, "error": str(exc), "response": {"body": None}, "signal": {}}
            else:
                self._error = str(exc)
                return None

        if step.wait_for_signal:
            result = await self._wait(step, result if isinstance(result, dict) else {"response": result})

        outputs = map_step_outputs(step, result if isinstance(result, dict) else {"response": result})
        self._outputs[step.id] = outputs
        context["outputs"] = self._outputs

        if step.wait_for_signal:
            next_step = route_hitl_outlets(step, outputs)
            decision = normalize_hitl_decision(
                str(outputs.get("decision") or (outputs.get("signal") or {}).get("decision") or "")
            )
            if next_step is None and decision in {"reject", "decline"}:
                self._error = f"human review rejected at {step.id} without a rejection outlet"
            return next_step
        if step.outlets:
            return next_from_gate_outlets(step.outlets, outputs, step.next_step)
        return step.next_step

    async def _wait(self, step: ActivityStep, result: dict[str, Any]) -> dict[str, Any]:
        self._status = "waiting"
        self._pending = {"node_id": step.id, "nodeId": step.id}
        await workflow.execute_activity(
            graph_update_run_state,
            {"run_id": self._run_id, "status": "waiting", "state": {"pending_approval": self._pending, "current_node_id": step.id}},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY,
        )
        await workflow.wait_condition(
            lambda: step.id in self._approvals and self._approvals[step.id].get("resolved")
        )
        signal = dict(self._approvals[step.id].get("payload") or {})
        signal.setdefault("decision", self._approvals[step.id].get("decision"))
        self._status = "running"
        self._pending = None
        return {**result, "signal": signal}
