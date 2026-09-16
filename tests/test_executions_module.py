"""Executions module API — catalog, detail, lifecycle actions."""

from fastapi.testclient import TestClient

from src.workflow_ui.main import app


def test_executions_catalog_and_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.get("/api/v1/executions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["executions"]
    assert payload["metrics"]["running"] >= 1
    assert any("2026" in e["id"] for e in payload["executions"])
    assert all("started_at" in e for e in payload["executions"])
    started = [e["started_at"] for e in payload["executions"] if e.get("started_at")]
    assert started == sorted(started, reverse=True)

    filtered = client.get("/api/v1/executions", params={"status": "RUNNING", "type": "FLOW"})
    assert filtered.status_code == 200
    items = filtered.json()["executions"]
    assert all(e["status"] == "RUNNING" for e in items)
    assert all(e["execution_type"] == "FLOW" for e in items)


def test_executions_detail_and_subresources(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    catalog = client.get("/api/v1/executions").json()["executions"]
    item = catalog[0]
    detail = client.get(f"/api/v1/executions/{item['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["execution"]["id"] == item["id"]
    assert body["execution"]["started_at"]
    assert body["execution"]["stage_runs"]
    assert body["validation"]["valid"] is True

    assert client.get(f"/api/v1/executions/{item['id']}/artifact").json()["facets"]
    assert client.get(f"/api/v1/executions/{item['id']}/skill-runs").json()["skill_runs"]
    assert client.get(f"/api/v1/executions/{item['id']}/contract").json()["contract"]
    assert client.get(f"/api/v1/executions/{item['id']}/evidence").json()["evidence"]


def test_executions_lifecycle_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    eid = client.get("/api/v1/executions").json()["executions"][0]["id"]
    paused = client.post(f"/api/v1/executions/{eid}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "blocked"

    resumed = client.post(f"/api/v1/executions/{eid}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "running"


def test_executions_create(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    created = client.post("/api/v1/executions", json={
        "title": "Payment refund flow",
        "type": "FLOW",
        "flow_name": "Feature Delivery",
        "source_type": "JIRA",
        "source_ref": "PAY-999",
    })
    assert created.status_code == 200
    body = created.json()
    assert body["execution"]["title"] == "Payment refund flow"
    assert body["execution"]["status"] == "RUNNING"
    assert body["execution"]["id"].startswith("EXE-2026-")
