from __future__ import annotations

import asyncio

from temporalio.client import Client

from src.orchestrator.workflows import workflow_interpreter as runtime
from src.orchestrator.workflows.workflow_interpreter import WorkflowInterpreter
from src.platform import runtime_bridge
from src.platform.graphs.temporal_steps import ActivityStep, ConditionBranch, ConditionStep, TemporalPlan


def test_hitl_signals_are_node_scoped_and_accept_aliases():
    interpreter = WorkflowInterpreter()
    interpreter._current = "review-a"

    interpreter.approve({"nodeId": "review-b", "comment": "looks good"})
    interpreter.request_changes({"node_id": "review-a", "reason": "add evidence"})

    assert interpreter._approvals["review-b"]["decision"] == "approve"
    assert interpreter._approvals["review-a"]["decision"] == "decline"
    assert interpreter._approvals["review-a"]["payload"]["node_id"] == "review-a"


def test_resume_accepts_nested_payload_and_targets_node():
    interpreter = WorkflowInterpreter()
    interpreter._current = "review-a"

    state = asyncio.run(
        interpreter.resume(
            {
                "node_id": "review-b",
                "payload": {"decision": "REJECTED", "reason": "not safe"},
            }
        )
    )

    assert state["approvals"]["review-b"]["decision"] == "reject"
    assert "review-a" not in state["approvals"]


def test_cycle_guard_fails_instead_of_completing(monkeypatch):
    async def fake_execute_activity(*_args, **_kwargs):
        return {"ok": True}

    monkeypatch.setattr(runtime.workflow, "execute_activity", fake_execute_activity)
    monkeypatch.setattr(runtime, "_MAX_INTERPRETER_STEPS", 2)
    plan = TemporalPlan(
        name="cycle",
        version="1",
        description="",
        trigger={},
        inputs=[],
        step_order=["loop"],
        steps={
            "loop": ConditionStep(
                id="loop",
                name="loop",
                branches=[ConditionBranch(id="again", expression="", next_step="loop")],
            )
        },
    )

    result = asyncio.run(WorkflowInterpreter().run({"run_id": "run-1", "plan": plan.to_dict()}))

    assert result["ok"] is False
    assert "cycle guard exceeded" in result["error"]


def test_subflow_propagates_secrets_and_uses_stable_idempotency_key(monkeypatch):
    activity_inputs = []
    child_inputs = []

    async def fake_activity(payload):
        activity_inputs.append(payload)
        return {
            "plan": TemporalPlan(
                name="child",
                version="1",
                description="",
                trigger={},
                inputs=[],
                steps={},
            ).to_dict(),
            "input": {"from_resolver": True},
        }

    async def fake_execute_activity(_fn, payload, **_kwargs):
        return await fake_activity(payload)

    async def fake_execute_child_workflow(_fn, payload, **kwargs):
        child_inputs.append((payload, kwargs))
        return {"ok": True}

    monkeypatch.setitem(runtime.ACTIVITY_FNS, "execute_subflow", fake_activity)
    monkeypatch.setattr(runtime.workflow, "execute_activity", fake_execute_activity)
    monkeypatch.setattr(runtime.workflow, "execute_child_workflow", fake_execute_child_workflow)
    interpreter = WorkflowInterpreter()
    interpreter._run_id = "parent"
    step = ActivityStep(
        id="child-node",
        name="child",
        activity_name="execute_subflow",
        input={"input": {"from_node": True}},
    )

    asyncio.run(
        interpreter._activity(
            step,
            {"inputs": {}, "outputs": {}, "secrets": {"slack-bot-token": "secret"}},
        )
    )

    assert activity_inputs[0]["idempotency_key"] == "parent:child-node"
    assert child_inputs[0][0]["secrets"] == {"slack-bot-token": "secret"}
    assert child_inputs[0][0]["input"] == {"from_resolver": True, "from_node": True}
    assert child_inputs[0][1]["id"] == "parent-sub-child-node"


def test_non_idempotent_activities_are_not_retried():
    assert runtime._activity_retry_policy("http_webhook").maximum_attempts == 1
    assert runtime._activity_retry_policy("integration_action").maximum_attempts == 1
    assert runtime._activity_retry_policy("ai_agent_execute").maximum_attempts == 3


def test_workflow_input_normalization_is_deterministic(monkeypatch):
    monkeypatch.setenv("SLACK_CHANNEL_IDS", "environment-channel")

    inputs = runtime._deterministic_run_input(
        {
            "source_id": "slack:source-channel:171234.5",
            "description": "Create a BRD",
        }
    )

    assert inputs["channel"] == "source-channel"
    assert inputs["thread_ts"] == "171234.5"
    assert inputs["text"] == "Create a BRD"


def test_checkpoint_signal_targets_slack_graph_child_without_port_alias(monkeypatch):
    signaled = []

    class Handle:
        def __init__(self, workflow_id):
            self.workflow_id = workflow_id

        async def signal(self, name, payload):
            signaled.append((self.workflow_id, name, payload))

    class FakeClient:
        def get_workflow_handle(self, workflow_id):
            return Handle(workflow_id)

    async def fake_connect(_host):
        return FakeClient()

    monkeypatch.setattr(Client, "connect", fake_connect)

    asyncio.run(runtime_bridge.signal_temporal_decision("task-slack-thread", "APPROVE", "ok"))

    assert [item[0] for item in signaled] == ["task-slack-thread:graph"]
    assert all(":port" not in item[0] for item in signaled)
