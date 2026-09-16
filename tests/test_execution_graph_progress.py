"""Inspector stages, labels, and completion for live graph runs."""

from __future__ import annotations

from src.platform.executions.models import StageRun
from src.platform.executions.service import (
    LEGACY_PLAYBOOK_STAGE_KEYS,
    _apply_stage_status,
    _finalize_stages,
)
from src.platform.runtime_bridge import (
    GRAPH_WORKFLOW_TEMPLATE,
    record_execution_started,
    stage_runs_from_plan,
    update_execution_progress,
)


def test_stage_runs_from_plan_skips_playbook_spine():
    plan = {
        "trigger": {"identifier": "trigger", "title": "Trigger"},
        "step_order": ["context_collection", "routing", "route", "brd_agent", "review", "publish"],
        "steps": {
            "context_collection": {"name": "Context collection"},
            "routing": {"name": "Routing"},
            "route": {"name": "Condition"},
            "brd_agent": {"name": "BRD agent"},
            "review": {"name": "Review"},
            "publish": {"name": "Publishing"},
        },
    }
    stages = stage_runs_from_plan(plan)
    keys = [s.key for s in stages]
    assert "classify" not in keys
    assert "intake" not in keys
    assert keys == [
        "trigger",
        "context_collection",
        "routing",
        "route",
        "brd_agent",
        "review",
        "publish",
    ]
    assert stages[0].status == "COMPLETED"
    assert stages[1].name == "Context collection"


def test_patch_drops_legacy_when_graph_node_arrives():
    stages = [
        StageRun(key="intake", name="Slack Intake", status="RUNNING"),
        StageRun(key="classify", name="Classify", status="SKIPPED"),
        StageRun(key="brd", name="Business Requirements", status="NOT_STARTED"),
        StageRun(key="srd", name="System Requirements", status="NOT_STARTED"),
        StageRun(key="approval", name="Human Approval", status="NOT_STARTED"),
        StageRun(key="publish", name="Publish Artifact", status="NOT_STARTED"),
    ]
    stages = _apply_stage_status(stages, "context_collection", "RUNNING", stage_name="Context collection")
    keys = [s.key for s in stages]
    assert not (set(keys) & (LEGACY_PLAYBOOK_STAGE_KEYS - {"publish"}))
    assert "context_collection" in keys
    assert "publish" in keys
    running = [s for s in stages if s.status == "RUNNING"]
    assert [s.key for s in running] == ["context_collection"]


def test_approval_review_maps_to_review_node():
    stages = [
        StageRun(key="review", name="Review", status="NOT_STARTED"),
        StageRun(key="publish", name="Publishing", status="NOT_STARTED"),
    ]
    stages = _apply_stage_status(stages, "approval-review", "RUNNING")
    assert [s.key for s in stages] == ["review", "publish"]
    assert stages[0].status == "RUNNING"


def test_finalize_sets_skipped_and_completed():
    stages = [
        StageRun(key="brd_agent", name="BRD agent", status="COMPLETED"),
        StageRun(key="srd_agent", name="SRD agent", status="NOT_STARTED"),
        StageRun(key="review", name="Review", status="COMPLETED"),
        StageRun(key="publish", name="Publishing", status="RUNNING"),
    ]
    _finalize_stages(stages, "COMPLETED")
    by = {s.key: s.status for s in stages}
    assert by["publish"] == "COMPLETED"
    assert by["srd_agent"] == "SKIPPED"


def test_record_started_uses_graph_nodes_not_classify(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    plan = {
        "trigger": {"identifier": "trigger"},
        "step_order": ["context_collection", "routing", "brd_agent", "review", "publish"],
        "steps": {
            "context_collection": {"name": "Context collection"},
            "routing": {"name": "Routing"},
            "brd_agent": {"name": "BRD agent"},
            "review": {"name": "Review"},
            "publish": {"name": "Publishing"},
        },
    }
    monkeypatch.setattr(
        "src.platform.runtime_bridge._published_graph_context",
        lambda **_kw: {
            "plan": plan,
            "flow_key": "ai-pdlc-flow",
            "flow_name": "AI PDLC",
            "graph_id": "11111111-1111-1111-1111-111111111111",
            "version_id": "22222222-2222-2222-2222-222222222222",
        },
    )
    from src.platform.executions import service as executions_svc

    eid = record_execution_started(
        task_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        source="slack",
        source_id="slack:C1:1.1",
        description="напиши бизнес-требования",
        workflow_id="task-slack-test",
        flow_key="ai-pdlc-flow",
    )
    rec = executions_svc.get_record(eid)
    assert rec is not None
    keys = [s.key for s in rec.stage_runs]
    assert "classify" not in keys
    assert "intake" not in keys
    assert "context_collection" in keys
    assert rec.snapshot.get("workflow_template_id") == GRAPH_WORKFLOW_TEMPLATE
    assert rec.execution_type == "FLOW"


def test_complete_marks_100_percent(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    from src.platform.executions import service as executions_svc
    from src.platform.executions.models import ExecutionRecord, StageRun, TimelineEvent
    from datetime import datetime

    now = datetime.utcnow()
    rec = ExecutionRecord(
        id="EXE-SLACK-AABBCCDD",
        title="t",
        execution_type="FLOW",
        source_type="SLACK",
        source_ref="x",
        flow_key="ai-pdlc-flow",
        flow_name="AI PDLC",
        current_stage="Publishing",
        progress_pct=75,
        status="RUNNING",
        stage_runs=[
            StageRun(key="review", name="Review", status="COMPLETED"),
            StageRun(key="publish", name="Publishing", status="RUNNING"),
        ],
        timeline=[TimelineEvent(at="00:00:00", title="start")],
        started_at=now,
        updated_at=now,
    )
    executions_svc.save_record(rec)
    update_execution_progress(
        "aabbccdd-0000-0000-0000-000000000000",
        status="COMPLETED",
        stage="Completed",
        activity="Completed",
        progress_pct=100,
    )
    got = executions_svc.get_record("EXE-SLACK-AABBCCDD")
    assert got.status == "COMPLETED"
    assert got.progress_pct == 100
    assert all(s.status in {"COMPLETED", "SKIPPED"} for s in got.stage_runs)
    titles = " ".join(e.title for e in got.timeline)
    assert "Port" not in titles
    assert "workflow platform" not in titles
