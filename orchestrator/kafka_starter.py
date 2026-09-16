"""Kafka consumer → starts Temporal TaskLifecycleWorkflow."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid

from aiokafka import AIOKafkaConsumer, TopicPartition
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from src.orchestrator.models import WorkflowInput
from src.orchestrator.workflows.task_lifecycle import TaskLifecycleWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TASKS_TOPIC", "tasks")
TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")
TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "agent-task-queue")
POLL_INTERVAL_SEC = float(os.environ.get("WORKFLOW_STARTER_POLL_INTERVAL", "2"))


def _workflow_id_for_task(task: dict) -> str:
    """Stable workflow id from source_id to avoid duplicate Slack/Kafka storms."""
    source_id = task.get("source_id")
    if source_id:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "-", str(source_id))[:200]
        return f"task-{safe}"
    return f"task-{task['task_id']}"


async def start_workflow(client: Client, task: dict) -> None:
    """Start TaskLifecycleWorkflow with stable id per source (idempotent)."""
    workflow_id = _workflow_id_for_task(task)
    wf_input = WorkflowInput(
        task_id=task["task_id"],
        source=task["source"],
        source_id=task["source_id"],
        description=task["description"],
        created_at=task.get("created_at", ""),
        callback_url=task.get("callback_url"),
        trace_id=task.get("trace_id") or task["task_id"],
        workflow_template_id=task.get("workflow_template_id"),
        flow_key=task.get("flow_key"),
    )

    try:
        handle = await client.start_workflow(
            TaskLifecycleWorkflow.run,
            wf_input,
            id=workflow_id,
            task_queue=TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
        logger.info("Started workflow %s for task %s", handle.id, task["task_id"])
        try:
            from src.platform.runtime_bridge import record_execution_started

            record_execution_started(
                task_id=task["task_id"],
                source=task.get("source") or "slack",
                source_id=task.get("source_id") or "",
                description=task.get("description") or "",
                workflow_id=handle.id,
                workflow_template_id=task.get("workflow_template_id"),
                flow_key=task.get("flow_key"),
            )
        except Exception as exc:
            logger.warning("Could not record platform execution for %s: %s", task["task_id"], exc)
    except WorkflowAlreadyStartedError:
        logger.info("Workflow %s already exists (idempotent skip)", workflow_id)


async def run_loop() -> None:
    """Consume Kafka tasks and start Temporal workflows."""
    client = await Client.connect(TEMPORAL_HOST)
    logger.info("Connected to Temporal at %s", TEMPORAL_HOST)

    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="workflow-starter",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
    )

    for attempt in range(12):
        try:
            await consumer.start()
            break
        except Exception as e:
            if attempt < 11:
                delay = min(2 ** attempt, 10)
                logger.warning("Kafka start attempt %d failed: %s, retry in %ds", attempt + 1, e, delay)
                await asyncio.sleep(delay)
            else:
                raise

    logger.info("Workflow starter listening on Kafka topic %s", KAFKA_TOPIC)
    pending_msg = None

    try:
        while True:
            if pending_msg is None:
                try:
                    msg = await asyncio.wait_for(consumer.getone(), timeout=POLL_INTERVAL_SEC)
                    pending_msg = msg
                except asyncio.TimeoutError:
                    continue

            task = pending_msg.value
            if not task.get("task_id"):
                task["task_id"] = str(uuid.uuid4())

            try:
                await start_workflow(client, task)
                tp = TopicPartition(pending_msg.topic, pending_msg.partition)
                await consumer.commit({tp: pending_msg.offset + 1})
                pending_msg = None
            except Exception as e:
                logger.exception("Failed to start workflow for task %s: %s", task.get("task_id"), e)
                await asyncio.sleep(5)
    finally:
        await consumer.stop()


def main() -> None:
    asyncio.run(run_loop())


if __name__ == "__main__":
    main()
