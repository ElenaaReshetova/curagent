"""Node presets: save a configured step and reuse it."""

from fastapi.testclient import TestClient

from src.workflow_ui.main import app


def test_node_preset_crud(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    created = client.post("/api/v1/node-presets", json={
        "name": "Slack publish",
        "node_type": "webhook",
        "label": "Publishing",
        "config": {
            "type": "WEBHOOK",
            "url": "https://slack.com/api/chat.postMessage",
            "method": "POST",
            "position": {"x": 1, "y": 2},
            "headers": {"Authorization": "Bearer {{ .secrets.slack_bot_token }}"},
        },
    })
    assert created.status_code == 200
    body = created.json()
    assert body["name"] == "Slack publish"
    assert body["node_type"] == "webhook"
    assert "position" not in (body.get("config") or {})
    assert body["config"]["url"] == "https://slack.com/api/chat.postMessage"
    preset_id = body["id"]

    listed = client.get("/api/v1/node-presets").json()["presets"]
    assert any(p["id"] == preset_id for p in listed)

    again = client.post("/api/v1/node-presets", json={
        "name": "Slack publish",
        "node_type": "webhook",
        "label": "Publishing v2",
        "config": {"type": "WEBHOOK", "url": "https://slack.com/api/chat.update"},
    })
    assert again.status_code == 200
    assert again.json()["id"] == preset_id
    assert again.json()["label"] == "Publishing v2"
    assert again.json()["config"]["url"].endswith("chat.update")
    assert len(client.get("/api/v1/node-presets").json()["presets"]) == 1

    deleted = client.delete(f"/api/v1/node-presets/{preset_id}")
    assert deleted.status_code == 200
    assert client.get("/api/v1/node-presets").json()["presets"] == []
    assert client.delete(f"/api/v1/node-presets/{preset_id}").status_code == 404
