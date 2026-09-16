"""In-process Test run engine (no Temporal)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from src.platform.graphs import local_run
from src.platform.graphs.models import GraphRun
from src.platform.graphs.temporal_steps import ActivityStep, TemporalPlan


def test_local_tick_pauses_on_input_then_completes(monkeypatch):
    rid = uuid4()
    store: dict = {}
    run = GraphRun(
        id=rid,
        graph_id=uuid4(),
        version_id=uuid4(),
        status="running",
        input={"text": "hi"},
        state={"outputs": {}, "engine": "local"},
    )
    store[rid] = run

    def get_run(i):
        return store[i]

    def update_run(r):
        store[r.id] = r
        return r

    monkeypatch.setattr("src.platform.graphs.service.get_run", get_run)
    monkeypatch.setattr("src.platform.graphs.service.update_run", update_run)
    monkeypatch.setattr("src.platform.graphs.service.append_run_event", lambda *a, **k: None)

    async def fake_http(_payload):
        return {"ok": True, "status_code": 200, "body": {"ok": True}}

    async def fake_review(_payload):
        return {"ok": True, "signal": {}}

    async def noop_event(_payload):
        return {"ok": True}

    monkeypatch.setitem(local_run.ACTIVITY_FNS, "http_webhook", fake_http)
    monkeypatch.setitem(local_run.ACTIVITY_FNS, "human_review", fake_review)
    monkeypatch.setattr(local_run, "graph_record_event", noop_event)

    plan = TemporalPlan(
        name="t",
        version="1",
        description="",
        trigger={},
        inputs=[],
        step_order=["wh", "rev"],
        steps={
            "wh": ActivityStep(
                id="wh",
                name="wh",
                activity_name="http_webhook",
                input={"url": "https://example.com"},
                next_step="rev",
            ),
            "rev": ActivityStep(
                id="rev",
                name="rev",
                activity_name="human_review",
                input={},
                wait_for_signal=True,
                output_mapping=[{"name": "decision", "path": "signal.decision"}],
                outlets=[
                    {"sourceHandle": "approve", "target": None},
                    {"sourceHandle": "decline", "target": None},
                ],
            ),
        },
    )

    asyncio.run(local_run.tick(rid, plan.to_dict()))
    assert store[rid].status == "waiting"
    assert store[rid].state["pending_approval"]["node_id"] == "rev"

    store[rid].state["resume_signal"] = {"decision": "approve"}
    asyncio.run(local_run.tick(rid, plan.to_dict()))
    assert store[rid].status == "completed"
    assert store[rid].state["outputs"]["rev"]["decision"] == "approve"
