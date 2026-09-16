"""Platform store + API smoke tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.platform.policy_eval import evaluate_rule, validate_policy_pack
from src.platform.store import (
    build_overview_from_store,
    get_execution,
    list_executions,
)
from src.workflow_ui.main import app


def test_policy_eq_resolves_path():
    ctx = {"operator": {"side_effects": "publish"}}
    assert evaluate_rule({"eq": ["operator.side_effects", "publish"]}, ctx) is True
    assert evaluate_rule({"neq": ["operator.side_effects", "none"]}, ctx) is True


def test_validate_policy_pack_ok():
    errors = validate_policy_pack([
        {"id": "x", "when": {"eq": ["tool.status", "approved"]}, "then": {"ok": True}},
    ])
    assert errors == []


def test_store_overview_and_executions(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    overview = build_overview_from_store()
    assert overview.agents
    assert overview.skills
    assert overview.controls
    assert overview.knowledge_spaces
    executions = list_executions()
    assert len(executions) >= 1
    detail = get_execution(executions[0].id)
    assert detail is not None
    assert detail.artifact_facets is not None
    assert detail.agent_key
    assert detail.case_context
    assert detail.skill_runs


def test_api_execution_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    items = client.get("/api/v1/executions").json()["executions"]
    assert items
    eid = items[0]["id"]
    paused = client.post(f"/api/v1/executions/{eid}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "blocked"
    resumed = client.post(f"/api/v1/executions/{eid}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "running"
    art = client.get(f"/api/v1/executions/{eid}/artifact")
    assert art.status_code == 200
    assert "facets" in art.json()


def test_api_runtime_lists(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    for path in ("/api/v1/audit", "/api/v1/integrations", "/api/v1/approvals", "/api/v1/agents"):
        r = client.get(path)
        assert r.status_code == 200, path


def test_governed_catalog_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    expected = {
        "/api/v1/agents": "agents",
        "/api/v1/skill-interfaces": "skill_interfaces",
        "/api/v1/skills": "skills",
        "/api/v1/rules": "rules",
        "/api/v1/controls": "controls",
        "/api/v1/knowledge-spaces": "knowledge_spaces",
        "/api/v1/capabilities": "capabilities",
    }
    for path, key in expected.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.json()[key], path

    overview = client.get("/api/v1/overview").json()
    assert overview["agents"][0]["key"] == "requirements-agent"
    assert overview["waiting_approvals_count"] >= 1
    assert client.get("/api/v1/playbooks").status_code == 404
    assert client.get("/api/v1/flows").status_code == 404
    assert client.get("/api/v1/launches").status_code == 404


def test_agents_are_read_only(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    assert client.get("/api/v1/agents").status_code == 200
    assert client.post("/api/v1/agents", json={"key": "x", "name": "X"}).status_code == 405


def test_skill_validation_rejects_direct_tool_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("SKILLS_STORE", "json")
    client = TestClient(app)
    interface_key = client.get("/api/v1/skill-interfaces").json()["skill_interfaces"][0]["key"]
    skill = client.post("/api/v1/skills", json={
        "key": "imported-unsafe",
        "interface_key": interface_key,
        "name": "Unsafe imported skill",
        "skill_type": "IMPORTED",
        "skill_markdown": "Call jira_get_issue directly.",
    })
    assert skill.status_code == 200
    body = skill.json()
    skill_id = body.get("id") or body.get("skill", {}).get("id")
    validation = client.post(f"/api/v1/skills/{skill_id}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is False
    assert "jira_" in validation.json()["errors"][0]


def test_controls_validate_and_execution_governed_views(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    control = client.get("/api/v1/controls").json()["controls"][0]
    validation = client.post(f"/api/v1/controls/{control['id']}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    execution = client.get("/api/v1/executions").json()["executions"][0]
    assert "run_contract" not in execution
    assert client.get(f"/api/v1/executions/{execution['id']}/contract").json()["contract"]
    assert client.get(f"/api/v1/executions/{execution['id']}/case-context").json()["case_context"]
    assert client.get(f"/api/v1/executions/{execution['id']}/skill-runs").json()["skill_runs"]
