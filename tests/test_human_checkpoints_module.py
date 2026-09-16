"""Human Checkpoints module API and state machine tests."""

from fastapi.testclient import TestClient

from src.platform.human_checkpoints.validation import can_transition
from src.workflow_ui.main import app


def test_human_checkpoints_catalog_and_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.get("/api/v1/human-checkpoints")
    assert response.status_code == 200
    payload = response.json()
    assert payload["checkpoints"]
    assert payload["metrics"]["my_open"] >= 1

    filtered = client.get("/api/v1/human-checkpoints", params={"view": "unassigned", "type": "PUBLICATION_APPROVAL"})
    assert filtered.status_code == 200
    items = filtered.json()["checkpoints"]
    assert items
    assert all(item["assignee"] == "Unassigned" for item in items)
    assert all(item["checkpoint_type"] == "PUBLICATION_APPROVAL" for item in items)


def test_human_checkpoints_detail_and_context_tabs(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    checkpoint = client.get("/api/v1/human-checkpoints").json()["checkpoints"][0]
    detail = client.get(f"/api/v1/human-checkpoints/{checkpoint['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["checkpoint"]["id"] == checkpoint["id"]
    assert body["validation"]["valid"] is True

    assert client.get(f"/api/v1/human-checkpoints/{checkpoint['id']}/artifact").json()["artifact"]["preview"]
    assert client.get(f"/api/v1/human-checkpoints/{checkpoint['id']}/diff").json()["changes"]
    assert client.get(f"/api/v1/human-checkpoints/{checkpoint['id']}/evidence").json()["evidence"]
    assert client.get(f"/api/v1/human-checkpoints/{checkpoint['id']}/controls").json()["controls"]
    assert client.get(f"/api/v1/human-checkpoints/{checkpoint['id']}/activity").json()["activity"]


def test_human_checkpoints_claim_and_decide(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    unassigned = client.get("/api/v1/human-checkpoints", params={"view": "unassigned"}).json()["checkpoints"][0]
    claimed = client.post(f"/api/v1/human-checkpoints/{unassigned['id']}/claim", json={"reviewer": "Alexey Khromov"})
    assert claimed.status_code == 200
    assert claimed.json()["checkpoint"]["assignee"] == "Alexey Khromov"

    reviewed = client.post(f"/api/v1/human-checkpoints/{unassigned['id']}/start-review")
    assert reviewed.status_code == 200
    assert reviewed.json()["checkpoint"]["status"] == "IN_REVIEW"

    decided = client.post(
        f"/api/v1/human-checkpoints/{unassigned['id']}/decisions",
        json={"decision": "APPROVE", "comment": "Looks good"},
    )
    assert decided.status_code == 200
    assert decided.json()["checkpoint"]["status"] == "APPROVED"
    assert decided.json()["checkpoint"]["selected_decision"] == "APPROVE"


def test_human_checkpoints_state_machine_rules():
    assert can_transition("OPEN", "ASSIGNED") is True
    assert can_transition("IN_REVIEW", "APPROVED") is True
    assert can_transition("APPROVED", "OPEN") is False
    assert can_transition("APPROVED", "APPROVED") is False


def test_human_checkpoints_reject_second_decision(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    unassigned = client.get("/api/v1/human-checkpoints", params={"view": "unassigned"}).json()["checkpoints"][0]
    client.post(f"/api/v1/human-checkpoints/{unassigned['id']}/claim", json={"reviewer": "Alexey Khromov"})
    client.post(f"/api/v1/human-checkpoints/{unassigned['id']}/start-review")
    first = client.post(
        f"/api/v1/human-checkpoints/{unassigned['id']}/decisions",
        json={"decision": "APPROVE", "comment": "Looks good"},
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/v1/human-checkpoints/{unassigned['id']}/decisions",
        json={"decision": "APPROVE", "comment": "again"},
    )
    assert second.status_code == 400
