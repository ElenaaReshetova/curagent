"""Relational workflow/scenario schema — topology + executions."""

from sqlalchemy import select

from src.platform.db.models.workflows import (
    ExecutionRow,
    ExecutionStepRow,
    NodeTypeRow,
    TemporalActivityRow,
    WorkflowConnectionRow,
    WorkflowRow,
    WorkflowStageRow,
    WorkflowVersionRow,
)
from src.platform.db.schema import init_schema
from src.platform.db.session import reset_engine_cache, session_scope
from src.platform.graphs.service import create_graph, create_run, save_draft


def _pg(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'workflows.db'}"
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("PLATFORM_DATABASE_URL", url)
    monkeypatch.setenv("WORKFLOWS_STORE", "postgres")
    monkeypatch.setenv("SKILLS_STORE", "json")
    reset_engine_cache()
    init_schema(url)
    return url


def test_workflow_tables_project_dsl_and_run_steps(tmp_path, monkeypatch):
    url = _pg(tmp_path, monkeypatch)

    rec = create_graph(
        key="brd-delivery",
        name="BRD delivery",
        kind="e2e",
        description="test scenario",
        graph={
            "identifier": "brd-delivery",
            "title": "BRD delivery",
            "nodes": [
                {
                    "identifier": "trigger",
                    "title": "Trigger",
                    "config": {"type": "SELF_SERVE_TRIGGER", "published": True},
                },
                {
                    "identifier": "agent",
                    "title": "Write BRD",
                    "config": {
                        "type": "AI_AGENT",
                        "agentIdentifier": "team-business-requirements",
                        "userPrompt": "Write the BRD",
                    },
                },
                {
                    "identifier": "review",
                    "title": "Human review",
                    "config": {"type": "INPUT", "outlets": [{"identifier": "approve"}]},
                },
            ],
            "connections": [
                {"sourceIdentifier": "trigger", "targetIdentifier": "agent"},
                {
                    "sourceIdentifier": "agent",
                    "targetIdentifier": "review",
                },
            ],
            "ui": {
                "kind": "e2e",
                "positions": {
                    "trigger": {"x": 40, "y": 80},
                    "agent": {"x": 240, "y": 80},
                    "review": {"x": 440, "y": 80},
                },
            },
        },
    )
    assert rec.key in ("e2e:brd-delivery", "brd-delivery")

    draft = save_draft(
        rec.id,
        {
            "identifier": "brd-delivery",
            "title": "BRD delivery",
            "nodes": [
                {
                    "identifier": "trigger",
                    "title": "Trigger",
                    "config": {"type": "SELF_SERVE_TRIGGER", "published": True},
                },
                {
                    "identifier": "agent",
                    "title": "Write BRD",
                    "config": {
                        "type": "AI_AGENT",
                        "agentIdentifier": "team-business-requirements",
                        "userPrompt": "Write the BRD",
                    },
                },
            ],
            "connections": [{"sourceIdentifier": "trigger", "targetIdentifier": "agent"}],
            "ui": {"kind": "e2e", "positions": {"trigger": {"x": 1, "y": 2}, "agent": {"x": 3, "y": 4}}},
        },
    )

    run = create_run(
        graph_id=rec.id,
        input_payload={"title": "INC-1", "_source": "TEST"},
        start_temporal=False,
    )

    with session_scope(url) as session:
        types = session.scalars(select(NodeTypeRow)).all()
        assert {t.key for t in types} >= {"trigger", "ai_agent", "input", "condition"}
        assert {t.type for t in types} <= {"Trigger", "Activity", "Input", "Condition"}

        wf = session.get(WorkflowRow, rec.id)
        assert wf is not None
        assert wf.name == "BRD delivery"
        assert wf.kind == "e2e"
        assert wf.segment_id == "default"

        ver = session.get(WorkflowVersionRow, draft.id)
        assert ver is not None
        assert ver.workflow_id == rec.id
        stages = session.scalars(
            select(WorkflowStageRow).where(WorkflowStageRow.workflow_version_id == ver.id)
        ).all()
        ids = {s.identifier for s in stages}
        assert {"trigger", "agent"} <= ids
        agent = next(s for s in stages if s.identifier == "agent")
        assert agent.name == "Write BRD"
        assert agent.pos_x == 3.0
        assert agent.node_type_id is not None

        conns = session.scalars(
            select(WorkflowConnectionRow).where(WorkflowConnectionRow.workflow_version_id == ver.id)
        ).all()
        assert conns
        assert any(c.source_stage_id == next(s.id for s in stages if s.identifier == "trigger") for c in conns)
        assert any(c.target_stage_id == agent.id for c in conns)

        exe = session.get(ExecutionRow, run.id)
        assert exe is not None
        assert exe.workflow_id == rec.id
        assert exe.workflow_version_id == rec.current_draft_version_id or exe.workflow_version_id == ver.id
        steps = session.scalars(
            select(ExecutionStepRow).where(ExecutionStepRow.execution_id == exe.id)
        ).all()
        assert steps
        assert {s.node_identifier for s in steps}


def test_parser_resolves_temporal_worker_from_node_types(tmp_path, monkeypatch):
    from src.platform.graphs.activity_catalog import reset_activity_catalog_cache
    from src.platform.graphs.normalize import normalize_workflow_dsl
    from src.platform.graphs.parse import parse_workflow_to_temporal
    from src.platform.graphs.service import ensure_graphs_seeded

    url = _pg(tmp_path, monkeypatch)
    ensure_graphs_seeded()
    reset_activity_catalog_cache()

    doc = normalize_workflow_dsl({
        "identifier": "map-test",
        "title": "map",
        "nodes": [
            {"identifier": "t", "title": "T", "config": {"type": "SELF_SERVE_TRIGGER"}},
            {"identifier": "w", "title": "W", "config": {"type": "WEBHOOK", "url": "https://x"}},
            {"identifier": "a", "title": "A", "config": {"type": "AI_AGENT", "agentIdentifier": "x", "userPrompt": "p"}},
        ],
        "connections": [
            {"sourceIdentifier": "t", "targetIdentifier": "w"},
            {"sourceIdentifier": "w", "targetIdentifier": "a"},
        ],
    })
    plan = parse_workflow_to_temporal(doc)
    assert plan.steps["w"].activity_name == "http_webhook"
    assert plan.steps["w"].worker == "http_webhook"
    assert plan.steps["a"].worker == "ai_agent_execute"

    with session_scope(url) as session:
        webhook_type = session.scalar(select(NodeTypeRow).where(NodeTypeRow.key == "webhook"))
        assert webhook_type is not None
        act = session.scalar(
            select(TemporalActivityRow).where(TemporalActivityRow.node_type_id == webhook_type.id)
        )
        assert act is not None
        assert act.worker == "http_webhook"
        act.worker = "custom_http_worker"
        act.activity_name = "custom_http_worker"

    reset_activity_catalog_cache()
    remapped = parse_workflow_to_temporal(doc)
    assert remapped.steps["w"].worker == "custom_http_worker"
    assert remapped.steps["w"].activity_name == "custom_http_worker"
    assert remapped.steps["a"].worker == "ai_agent_execute"


def test_workflow_record_revision_compare_and_swap(tmp_path, monkeypatch):
    from src.platform.graphs import service as graphs_svc

    _pg(tmp_path, monkeypatch)
    record = create_graph(key="cas", name="CAS", kind="e2e")
    first = graphs_svc.get_graph(record.id)
    stale = first.model_copy(deep=True)

    first.revision += 1
    first.name = "First"
    graphs_svc.save_record(first, expected_revision=record.revision)

    stale.revision += 1
    stale.name = "Stale"
    try:
        graphs_svc.save_record(stale, expected_revision=record.revision)
    except ValueError as exc:
        assert "revision conflict" in str(exc)
    else:
        raise AssertionError("stale workflow update overwrote a newer revision")

