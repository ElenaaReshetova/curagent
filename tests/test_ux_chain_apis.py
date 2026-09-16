"""Platform UX chain API smoke tests."""

import pytest
from fastapi.testclient import TestClient

from src.workflow_ui.main import app

LEGACY_API_RETIRED = pytest.mark.skip(reason="/flows product API was retired")


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("PLATFORM_DATABASE_URL", raising=False)
    monkeypatch.setenv("SKILLS_STORE", "json")
    return TestClient(app)


def test_mcp_and_capability_manifests_are_exposed(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    servers = client.get("/api/v1/mcp/servers")
    assert servers.status_code == 200
    assert servers.json()["servers"]

    manifests = client.get("/api/v1/capability-manifests")
    assert manifests.status_code == 200
    assert any(item["implementations"] for item in manifests.json()["manifests"])


@LEGACY_API_RETIRED
def test_flow_graph_save_and_publish(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    created = client.post("/api/v1/flows", json={"name": "UX chain flow", "key": "ux-chain-flow"})
    assert created.status_code == 200
    flow = created.json()
    flow_id = flow["flow"]["id"]
    version = flow["current_version"]
    graph = {
        "stages": [
            {"key": "start", "name": "Start", "type": "START"},
            {"key": "review", "name": "Review", "type": "SUBFLOW", "flow_key": "system-requirements"},
            {"key": "end", "name": "End", "type": "END"},
        ],
        "edges": [
            {"key": "e1", "source": "start", "target": "review"},
            {"key": "e2", "source": "review", "target": "end"},
        ],
        "revision": version["revision"],
    }
    saved = client.put(f"/api/v1/flows/{flow_id}/versions/{version['id']}/graph", json=graph)
    assert saved.status_code == 200
    assert saved.json()["revision"] == version["revision"] + 1

    published = client.post(f"/api/v1/flows/{flow_id}/versions/{version['id']}/publish")
    assert published.status_code == 200
    assert published.json()["published_version"]["id"] == version["id"]
    assert published.json()["draft_version"]["status"] == "DRAFT"


@LEGACY_API_RETIRED
def test_flow_graph_save_keeps_canvas_positions(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    created = client.post("/api/v1/flows", json={"name": "Layout flow", "key": "layout-flow"})
    assert created.status_code == 200
    flow = created.json()["flow"]
    version = created.json()["current_version"]
    graph = {
        "stages": [
            {
                "key": "start",
                "name": "Start",
                "type": "START",
                "x": 40,
                "y": 120,
                "config": {"type": "SELF_SERVE_TRIGGER", "position": {"x": 40, "y": 120}},
            },
            {
                "key": "agent",
                "name": "Agent",
                "type": "AI_AGENT",
                "x": 320,
                "y": 120,
                "config": {"type": "AI_AGENT", "agentIdentifier": "business-requirements", "position": {"x": 320, "y": 120}},
            },
        ],
        "edges": [{"key": "e1", "source": "start", "target": "agent"}],
        "revision": version["revision"],
    }
    saved = client.put(f"/api/v1/flows/{flow['id']}/versions/{version['id']}/graph", json=graph)
    assert saved.status_code == 200
    graph_id = saved.json().get("graph_id")
    assert graph_id
    detail = client.get(f"/api/v1/graphs/{graph_id}")
    assert detail.status_code == 200
    canvas = detail.json().get("canvas") or {}
    by_id = {n["id"]: n for n in canvas.get("nodes") or []}
    assert by_id["start"]["position"] == {"x": 40, "y": 120}
    assert by_id["agent"]["position"] == {"x": 320, "y": 120}

    # Second save without x/y must not wipe the stored layout.
    again = {
        "stages": [
            {"key": "start", "name": "Start", "type": "START", "config": {"type": "SELF_SERVE_TRIGGER"}},
            {"key": "agent", "name": "Agent", "type": "AI_AGENT", "config": {"type": "AI_AGENT", "agentIdentifier": "business-requirements"}},
        ],
        "edges": [{"key": "e1", "source": "start", "target": "agent"}],
        "revision": saved.json()["revision"],
    }
    saved2 = client.put(f"/api/v1/flows/{flow['id']}/versions/{version['id']}/graph", json=again)
    assert saved2.status_code == 200
    detail2 = client.get(f"/api/v1/graphs/{graph_id}")
    canvas2 = detail2.json().get("canvas") or {}
    by_id2 = {n["id"]: n for n in canvas2.get("nodes") or []}
    assert by_id2["start"]["position"] == {"x": 40, "y": 120}
    assert by_id2["agent"]["position"] == {"x": 320, "y": 120}


def test_skill_inherit_clones_published_package(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    source = next(skill for skill in client.get("/api/v1/skills").json()["skills"] if skill["status"] == "PUBLISHED")
    response = client.post(
        f"/api/v1/skills/{source['id']}/inherit",
        json={"key": "derived-ux-skill", "name": "Derived UX Skill"},
    )
    assert response.status_code == 200
    assert response.json()["skill"]["key"] == "derived-ux-skill"
    assert response.json()["draft_version"]["status"] == "DRAFT"
