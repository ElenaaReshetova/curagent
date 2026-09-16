from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from src.platform.graphs import service as graphs_svc
from src.orchestrator.activities_workflow import execute_subflow
from src.workflow_ui.main import app


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("PLATFORM_DATABASE_URL", raising=False)
    monkeypatch.setenv("WORKFLOWS_STORE", "json")
    monkeypatch.setenv("SKILLS_STORE", "json")
    graphs_svc.reset_graphs_seed_cache()
    return TestClient(app)


def _dsl(identifier: str, *, title: str = "Scenario") -> dict:
    return {
        "identifier": identifier,
        "title": title,
        "nodes": [
            {
                "identifier": "trigger",
                "title": "Trigger",
                "config": {"type": "SELF_SERVE_TRIGGER"},
            },
            {
                "identifier": "webhook",
                "title": "Webhook",
                "config": {"type": "WEBHOOK", "url": "https://example.invalid"},
            },
        ],
        "connections": [{"sourceIdentifier": "trigger", "targetIdentifier": "webhook"}],
    }


def test_published_version_remains_immutable_after_new_draft(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    key = f"immutable-{uuid4().hex[:8]}"
    created = client.post(
        "/api/v1/scenarios",
        json={"key": key, "name": "Immutable", "kind": "e2e", "dsl": _dsl(key)},
    ).json()
    published = client.post(
        f"/api/v1/scenarios/{created['id']}",
        json={"revision": created["revision"], "status": "published"},
    )
    assert published.status_code == 200, published.text

    versions = client.get(f"/api/v1/graphs/{created['id']}/versions").json()["versions"]
    frozen = next(version for version in versions if version["status"] == "PUBLISHED")
    frozen_dsl = frozen["dsl"]

    draft = client.post(
        f"/api/v1/scenarios/{created['id']}",
        json={"revision": published.json()["revision"], "status": "draft"},
    )
    assert draft.status_code == 200, draft.text
    versions = client.get(f"/api/v1/graphs/{created['id']}/versions").json()["versions"]
    assert len([version for version in versions if version["status"] == "PUBLISHED"]) == 1
    assert len([version for version in versions if version["status"] == "DRAFT"]) == 1

    saved = client.put(
        f"/api/v1/scenarios/{created['id']}",
        json={"revision": draft.json()["revision"], "dsl": _dsl(key, title="Changed")},
    )
    assert saved.status_code == 200, saved.text
    versions = client.get(f"/api/v1/graphs/{created['id']}/versions").json()["versions"]
    assert next(version for version in versions if version["id"] == frozen["id"])["dsl"] == frozen_dsl


def test_live_run_uses_frozen_plan_without_reparse(tmp_path, monkeypatch):
    _client(tmp_path, monkeypatch)
    key = f"pinned-{uuid4().hex[:8]}"
    record = graphs_svc.create_graph(key=key, name="Pinned", kind="e2e", graph=_dsl(key))
    published = graphs_svc.publish_version(record.id)
    frozen_plan = dict(published.temporal_plan or {})

    def fail_parse(*args, **kwargs):
        raise AssertionError("live run must not invoke the parser")

    monkeypatch.setattr(graphs_svc, "parse_workflow_to_temporal", fail_parse)
    run = graphs_svc.create_run(graph_id=record.id, input_payload={}, start_temporal=False)
    assert run.version_id == published.id
    assert run.state["plan"] == frozen_plan
    assert run.state["engine"] == "temporal"


def test_validation_rejects_unsupported_nodes_and_unconditional_cycles(tmp_path, monkeypatch):
    _client(tmp_path, monkeypatch)
    unsupported = _dsl("unsupported")
    unsupported["nodes"][1]["config"] = {"type": "KAFKA", "payload": {}}
    report = graphs_svc.validate_only(unsupported)
    assert {issue.code for issue in report.issues} >= {"UNSUPPORTED_NODE"}

    cyclic = _dsl("cyclic")
    cyclic["connections"].append({"sourceIdentifier": "webhook", "targetIdentifier": "webhook"})
    report = graphs_svc.validate_only(cyclic)
    assert {issue.code for issue in report.issues} >= {"UNCONDITIONAL_CYCLE"}


def test_live_start_failure_is_awaited_and_reported(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    key = f"start-failure-{uuid4().hex[:8]}"
    created = client.post(
        "/api/v1/scenarios",
        json={"key": key, "name": "Start failure", "kind": "e2e", "dsl": _dsl(key)},
    ).json()
    published = client.post(
        f"/api/v1/scenarios/{created['id']}",
        json={"revision": created["revision"], "status": "published"},
    ).json()
    launched = client.post(
        f"/api/v1/scenarios/{created['id']}",
        json={"revision": published["revision"], "status": "launched"},
    )
    assert launched.status_code == 200

    async def fail_start(*args, **kwargs):
        raise ConnectionError("temporal unavailable")

    monkeypatch.setattr(graphs_svc, "_start_interpreter_async", fail_start)
    response = client.post(
        "/api/v1/runs",
        json={"scenario_id": created["id"], "mode": "live", "input": {}},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "RUNTIME_UNAVAILABLE"


def test_subflow_requires_and_uses_published_child_plan(tmp_path, monkeypatch):
    import asyncio

    _client(tmp_path, monkeypatch)
    key = f"child-{uuid4().hex[:8]}"
    record = graphs_svc.create_graph(key=key, name="Child", kind="stage", graph=_dsl(key))
    try:
        asyncio.run(execute_subflow({"graph_id": str(record.id), "run_id": "parent"}))
    except RuntimeError as exc:
        assert "published version" in str(exc)
    else:
        raise AssertionError("unpublished subflow was accepted")

    published = graphs_svc.publish_version(record.id)
    result = asyncio.run(execute_subflow({"graph_id": str(record.id), "run_id": "parent"}))
    assert result["plan"] == published.temporal_plan
    assert result["parent_execution_id"] == "parent"
