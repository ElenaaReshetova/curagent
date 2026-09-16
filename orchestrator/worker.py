"""Temporal worker — workflow interpreter + task lifecycle ingress."""

from __future__ import annotations

import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from src.orchestrator.activities import (
    check_compliance_activity,
    classify_task_activity,
    collect_evidence,
    execute_skill_activity,
    execute_skill_step_activity,
    execute_tool_activity,
    load_workflow_template_activity,
    normalize_task,
    notify_escalation_activity,
    open_human_checkpoint_activity,
    plan_task,
    publish_artifact_activity,
    record_execution_progress_activity,
    resolve_flow_template_activity,
    verify_artifact_activity,
)
from src.orchestrator.activities_workflow import (
    ai_agent_execute,
    ai_generate_summary,
    execute_subflow,
    graph_record_event,
    graph_update_run_state,
    http_webhook,
    human_review,
    integration_action,
    internal_service,
    kafka_publish,
    upsert_entity,
)
from src.orchestrator.workflows.workflow_interpreter import WorkflowInterpreter
from src.orchestrator.workflows.task_lifecycle import TaskLifecycleWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "agent-task-queue")


async def run_worker() -> None:
    temporal_host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    logger.info("Connecting to Temporal at %s, queue=%s", temporal_host, TASK_QUEUE)

    client = await Client.connect(temporal_host)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TaskLifecycleWorkflow, WorkflowInterpreter],
        max_concurrent_activities=int(os.environ.get("ORCHESTRATOR_MAX_CONCURRENT_ACTIVITIES", "1")),
        max_concurrent_workflow_tasks=int(os.environ.get("ORCHESTRATOR_MAX_CONCURRENT_WORKFLOWS", "2")),
        activities=[
            load_workflow_template_activity,
            resolve_flow_template_activity,
            normalize_task,
            classify_task_activity,
            plan_task,
            collect_evidence,
            execute_skill_activity,
            execute_skill_step_activity,
            execute_tool_activity,
            verify_artifact_activity,
            check_compliance_activity,
            publish_artifact_activity,
            notify_escalation_activity,
            record_execution_progress_activity,
            open_human_checkpoint_activity,
            http_webhook,
            ai_generate_summary,
            ai_agent_execute,
            human_review,
            internal_service,
            execute_subflow,
            kafka_publish,
            upsert_entity,
            integration_action,
            graph_record_event,
            graph_update_run_state,
        ],
    )
    logger.info("Temporal worker started on queue %s", TASK_QUEUE)
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
