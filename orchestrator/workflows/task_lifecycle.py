"""TaskLifecycleWorkflow — E2E if launched, else classify → playbook template."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.orchestrator.activities import (
        classify_task_activity,
        load_workflow_template_activity,
        normalize_task,
        record_execution_progress_activity,
        resolve_flow_template_activity,
    )
    from src.orchestrator.models import RoutingDecision, WorkflowInput, WorkflowResult
    from src.orchestrator.pipeline_runner import run_configurable_pipeline
    from src.orchestrator.workflow_config.models import WorkflowTemplate
    from src.orchestrator.workflows.workflow_interpreter import WorkflowInterpreter

_DEFAULT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    maximum_attempts=3,
)


@workflow.defn(name="TaskLifecycleWorkflow")
class TaskLifecycleWorkflow:
    """Ingress → launched graph, or classify → legacy playbook template."""

    def __init__(self) -> None:
        self._human_decision: Optional[dict[str, Any]] = None

    @workflow.signal(name="human_decision")
    def human_decision(self, payload: dict[str, Any]) -> None:
        """Receive approval decision from platform UI / Slack bridge."""
        self._human_decision = payload or {}

    def take_human_decision(self) -> Optional[dict[str, Any]]:
        return self._human_decision

    def clear_human_decision(self) -> None:
        self._human_decision = None

    @workflow.run
    async def run(self, raw: WorkflowInput) -> WorkflowResult:
        workflow.logger.info("Starting TaskLifecycleWorkflow task_id=%s", raw.task_id)

        # 1) Normalize intake (shared for all scenarios)
        spec = await workflow.execute_activity(
            normalize_task,
            raw,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )

        # Launched E2E (AI PDLC) replaces pre-scenario classify + old playbooks.
        port_route = await workflow.execute_activity(
            resolve_flow_template_activity,
            {
                "primary_skill": "general",
                "workflow_template_id": raw.workflow_template_id,
                "flow_key": raw.flow_key,
                "source": spec.source,
                "graph_only": True,
            },
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=_DEFAULT_RETRY,
        )
        if (port_route.get("use_graph_interpreter") or port_route.get("use_workflow_interpreter")) and port_route.get("plan"):
            return await self._run_port_child(raw, spec, port_route)

        # 2) Classify BEFORE choosing a legacy playbook scenario
        routing_raw = await workflow.execute_activity(
            classify_task_activity,
            spec,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )
        routing = (
            routing_raw
            if isinstance(routing_raw, RoutingDecision)
            else RoutingDecision.model_validate(routing_raw)
        )

        route_payload = await workflow.execute_activity(
            resolve_flow_template_activity,
            {
                "primary_skill": routing.primary_skill,
                "workflow_template_id": raw.workflow_template_id,
                "flow_key": raw.flow_key,
                "source": spec.source,
            },
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=_DEFAULT_RETRY,
        )
        template_id = route_payload["template_id"]
        reason = route_payload.get("reason", "unknown")
        flow_key = route_payload.get("flow_key")
        workflow.logger.info(
            "Pre-scenario route task=%s skill=%s → template=%s (%s)",
            raw.task_id,
            routing.primary_skill,
            template_id,
            reason,
        )

        await workflow.execute_activity(
            record_execution_progress_activity,
            {
                "task_id": raw.task_id,
                "status": "RUNNING",
                "stage": "Classify",
                "activity": f"Selected scenario {template_id}",
                "progress_pct": 15,
                "skill": routing.primary_skill,
                "stage_key": "classify",
                "stage_status": "COMPLETED",
                "detail": f"reason={reason} confidence={routing.confidence}",
                "flow_key": flow_key,
                "playbook_chain": route_payload.get("playbook_chain"),
            },
            start_to_close_timeout=timedelta(minutes=1),
        )

        # 3) Published graph (if classify-time resolve still points at it)
        if (route_payload.get("use_graph_interpreter") or route_payload.get("use_workflow_interpreter")) and route_payload.get("plan"):
            return await self._run_port_child(raw, spec, route_payload)

        template_data = await workflow.execute_activity(
            load_workflow_template_activity,
            template_id,
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=_DEFAULT_RETRY,
        )
        template = WorkflowTemplate.model_validate(template_data)

        return await run_configurable_pipeline(
            raw,
            template,
            workflow_ref=self,
            initial_routing=routing,
            initial_spec=spec,
        )

    async def _run_port_child(self, raw, spec, route_payload: dict[str, Any]) -> WorkflowResult:
        flow_name = str(route_payload.get("flow_name") or route_payload.get("flow_key") or "сценарий")
        workflow.logger.info(
            "Delegating to graph interpreter task=%s graph=%s flow=%s",
            raw.task_id,
            route_payload.get("graph_id"),
            route_payload.get("flow_key"),
        )
        await workflow.execute_activity(
            record_execution_progress_activity,
            {
                "task_id": raw.task_id,
                "status": "RUNNING",
                "stage": flow_name,
                "activity": f"Сценарий {flow_name}".strip(),
                "progress_pct": 12,
                "flow_key": route_payload.get("flow_key"),
                "flow_name": route_payload.get("flow_name"),
                "detail": "запущен опубликованный сценарий",
                "graph_id": route_payload.get("graph_id"),
                "graph_version_id": route_payload.get("version_id"),
            },
            start_to_close_timeout=timedelta(minutes=1),
        )
        child_id = f"{workflow.info().workflow_id}:graph"
        child = await workflow.execute_child_workflow(
            WorkflowInterpreter.run,
            args=[{
                "run_id": raw.task_id,
                "plan": route_payload.get("plan"),
                "input": {
                    "task_id": raw.task_id,
                    "title": spec.title,
                    "description": spec.description,
                    "text": spec.description,
                    "source": spec.source,
                    "source_id": spec.source_id,
                    "trace_id": spec.trace_id,
                },
                "secrets": route_payload.get("secrets") or {},
            }],
            id=child_id,
        )

        ok = bool(child.get("ok"))
        await workflow.execute_activity(
            record_execution_progress_activity,
            {
                "task_id": raw.task_id,
                "status": "COMPLETED" if ok else "FAILED",
                "stage": "Completed" if ok else "Failed",
                "activity": "Completed" if ok else "Failed",
                "progress_pct": 100,
                "detail": "" if ok else str(child.get("error") or child),
            },
            start_to_close_timeout=timedelta(minutes=1),
        )
        return WorkflowResult(
            task_id=raw.task_id,
            trace_id=spec.trace_id or raw.task_id,
            status="delivered" if ok else "failed",
            error=None if ok else str(child.get("error") or child),
        )
