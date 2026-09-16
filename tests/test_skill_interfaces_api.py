"""Skill interface catalog API — platform read-only vs custom CRUD."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.workflow_ui.main import app


def _json_store(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("PLATFORM_DATABASE_URL", raising=False)
    monkeypatch.setenv("SKILLS_STORE", "json")


def test_skill_interfaces_list_with_source(tmp_path, monkeypatch):
    _json_store(tmp_path, monkeypatch)
    client = TestClient(app)

    listed = client.get("/api/v1/skill-interfaces")
    assert listed.status_code == 200
    body = listed.json()
    assert body["skill_interfaces"]
    assert "counts" in body
    assert any(i["key"] == "analysis.business_requirements.generate@1" for i in body["skill_interfaces"])
    platform = next(
        i for i in body["skill_interfaces"]
        if i["key"] == "analysis.business_requirements.generate@1"
    )
    assert platform["source"] == "platform"


def test_custom_skill_interface_crud(tmp_path, monkeypatch):
    _json_store(tmp_path, monkeypatch)
    client = TestClient(app)

    created = client.post("/api/v1/skill-interfaces", json={
        "key": "analysis.team.custom@1",
        "name": "Team Custom Generator",
        "description": "Team-owned interface",
        "input_contract_key": "WorkItem@1",
        "output_contract_key": "ArtifactPatch@1",
        "required_capabilities": ["context.read"],
    })
    assert created.status_code == 200
    item = created.json()
    assert item["source"] == "custom"
    assert item["key"] == "analysis.team.custom@1"

    updated = client.put(f"/api/v1/skill-interfaces/{item['id']}", json={
        "name": "Team Custom Generator v2 label",
        "description": "Updated",
        "input_contract_key": "WorkItem@1",
        "output_contract_key": "ArtifactPatch@1",
        "required_capabilities": ["context.read", "artifact.patch"],
    })
    assert updated.status_code == 200
    assert updated.json()["name"] == "Team Custom Generator v2 label"

    deleted = client.delete(f"/api/v1/skill-interfaces/{item['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True


def test_platform_skill_interface_is_read_only(tmp_path, monkeypatch):
    _json_store(tmp_path, monkeypatch)
    client = TestClient(app)

    listed = client.get("/api/v1/skill-interfaces").json()["skill_interfaces"]
    platform = next(i for i in listed if i["source"] == "platform")

    blocked = client.put(f"/api/v1/skill-interfaces/{platform['id']}", json={
        "name": "Hacked",
        "input_contract_key": "WorkItem@1",
        "output_contract_key": "ArtifactPatch@1",
    })
    assert blocked.status_code == 403

    blocked_delete = client.delete(f"/api/v1/skill-interfaces/{platform['id']}")
    assert blocked_delete.status_code == 403
