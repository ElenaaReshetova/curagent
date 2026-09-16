"""Product scenario/run API (SCENARIO_SRS)."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from src.workflow_ui.main import app


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("PLATFORM_DATABASE_URL", raising=False)
    monkeypatch.setenv("WORKFLOWS_STORE", "json")
    monkeypatch.setenv("SKILLS_STORE", "json")
    return TestClient(app)


def _key(prefix: str = "scene") -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _dsl(identifier: str) -> dict:
    return {
        "identifier": identifier,
        "title": identifier,
        "nodes": [
            {
                "identifier": "trigger",
                "title": "Trigger",
                "config": {
                    "type": "SELF_SERVE_TRIGGER",
                    "published": True,
                    "userInputs": {"properties": {}, "required": []},
                },
            }
        ],
        "connections": [],
    }


def test_scenario_crud_status_and_runs(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    key = _key()

    created = client.post(
        "/api/v1/scenarios",
        json={"key": key, "name": "Clear handles", "kind": "e2e", "description": "demo"},
    )
    assert created.status_code == 201, created.text
    card = created.json()
    assert card["status"] == "draft"
    assert card["key"].endswith(key)
    assert card["plan"] is None
    scenario_id = card["id"]
    revision = card["revision"]

    listed = client.get("/api/v1/scenarios", params={"kind": "e2e", "q": key})
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert any(item["id"] == scenario_id for item in listed.json()["items"])
    assert "dsl" not in listed.json()["items"][0]
    match = next(item for item in listed.json()["items"] if item["id"] == scenario_id)
    assert match["node_count"] >= 1

    canvas_view = client.get(f"/api/v1/scenarios/{scenario_id}", params={"view": "canvas"})
    assert canvas_view.status_code == 200
    assert canvas_view.json().get("canvas")
    assert "dsl" not in canvas_view.json()

    by_key = client.get(f"/api/v1/scenarios/{key}")
    assert by_key.status_code == 200
    assert by_key.json()["id"] == scenario_id

    saved = client.put(
        f"/api/v1/scenarios/{scenario_id}",
        json={"revision": revision, "name": "Clear handles v2", "dsl": _dsl(key)},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["name"] == "Clear handles v2"
    assert saved.json()["status"] == "draft"
    revision = saved.json()["revision"]

    conflict = client.put(
        f"/api/v1/scenarios/{scenario_id}",
        json={"revision": revision - 1, "dsl": _dsl(key)},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "REVISION_CONFLICT"

    status_on_put = client.put(
        f"/api/v1/scenarios/{scenario_id}",
        json={"revision": revision, "status": "published", "dsl": _dsl(key)},
    )
    assert status_on_put.status_code == 400
    assert status_on_put.json()["error"]["code"] == "BAD_REQUEST"

    live_early = client.post(
        "/api/v1/runs",
        json={"scenario_id": scenario_id, "mode": "live", "input": {"title": "x"}},
    )
    assert live_early.status_code == 400
    assert live_early.json()["error"]["code"] == "NOT_LAUNCHED"

    test_run = client.post(
        "/api/v1/runs",
        json={"scenario_id": scenario_id, "mode": "test", "input": {"title": "test"}},
    )
    assert test_run.status_code == 201, test_run.text
    run = test_run.json()
    assert run["scenario_id"] == scenario_id
    assert run["mode"] == "test"
    run_id = run["id"]

    state = client.get(f"/api/v1/runs/{run_id}/state")
    assert state.status_code == 200
    assert "status" in state.json()

    events = client.get(f"/api/v1/runs/{run_id}/events")
    assert events.status_code == 200
    assert isinstance(events.json()["events"], list)

    cancelled = client.post(f"/api/v1/runs/{run_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    jump = client.post(
        f"/api/v1/scenarios/{scenario_id}",
        json={"revision": revision, "status": "launched"},
    )
    assert jump.status_code == 400
    assert jump.json()["error"]["code"] == "BAD_TRANSITION"

    published = client.post(
        f"/api/v1/scenarios/{scenario_id}",
        json={"revision": revision, "status": "published"},
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert published.json()["plan"]
    revision = published.json()["revision"]

    blocked = client.put(
        f"/api/v1/scenarios/{scenario_id}",
        json={"revision": revision, "dsl": _dsl(key)},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "NOT_DRAFT"

    live_published = client.post(
        "/api/v1/runs",
        json={"scenario_id": scenario_id, "mode": "live", "input": {}},
    )
    assert live_published.status_code == 400
    assert live_published.json()["error"]["code"] == "NOT_LAUNCHED"

    launched = client.post(
        f"/api/v1/scenarios/{scenario_id}",
        json={"revision": revision, "status": "launched"},
    )
    assert launched.status_code == 200, launched.text
    assert launched.json()["status"] == "launched"
    revision = launched.json()["revision"]

    live = client.post(
        "/api/v1/runs",
        json={"scenario_id": scenario_id, "mode": "live", "input": {"title": "live"}},
    )
    assert live.status_code in (201, 503)
    if live.status_code == 503:
        assert live.json()["error"]["code"] == "RUNTIME_UNAVAILABLE"
    else:
        client.post(f"/api/v1/runs/{live.json()['id']}/cancel")

    disarmed = client.post(
        f"/api/v1/scenarios/{scenario_id}",
        json={"revision": revision, "status": "published"},
    )
    assert disarmed.status_code == 200
    assert disarmed.json()["status"] == "published"
    revision = disarmed.json()["revision"]

    draft_again = client.post(
        f"/api/v1/scenarios/{scenario_id}",
        json={"revision": revision, "status": "draft"},
    )
    assert draft_again.status_code == 200
    assert draft_again.json()["status"] == "draft"
    revision = draft_again.json()["revision"]

    saved_again = client.put(
        f"/api/v1/scenarios/{scenario_id}",
        json={"revision": revision, "dsl": _dsl(key)},
    )
    assert saved_again.status_code == 200

    deleted = client.delete(f"/api/v1/scenarios/{scenario_id}")
    assert deleted.status_code == 409
    assert deleted.json()["error"]["code"] == "CONFLICT"
    assert client.get(f"/api/v1/scenarios/{scenario_id}").status_code == 200


def test_stage_cannot_launch_and_duplicate_key(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    key = _key("stage")
    created = client.post("/api/v1/scenarios", json={"key": key, "name": "Stage", "kind": "stage"})
    assert created.status_code == 201
    scenario_id = created.json()["id"]
    revision = created.json()["revision"]

    published = client.post(
        f"/api/v1/scenarios/{scenario_id}",
        json={"revision": revision, "status": "published"},
    )
    assert published.status_code == 200
    launched = client.post(
        f"/api/v1/scenarios/{scenario_id}",
        json={"revision": published.json()["revision"], "status": "launched"},
    )
    assert launched.status_code == 400
    assert launched.json()["error"]["code"] == "BAD_REQUEST"

    dup = client.post("/api/v1/scenarios", json={"key": key, "name": "Stage", "kind": "stage"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "CONFLICT"


def test_node_types_catalog(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    res = client.get("/api/v1/schemas/node-types", params={"kind": "e2e"})
    assert res.status_code == 200
    types = res.json()["node_types"]
    assert types
    assert any(item.get("type") == "trigger" or item.get("type") == "webhook" for item in types)
