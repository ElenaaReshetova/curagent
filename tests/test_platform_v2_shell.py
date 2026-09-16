"""V2 Phase 1: Runtime Profiles + dashboard + nav contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.platform.seed.governed_catalog import build_runtime_profiles
from src.platform.store import ensure_seeded, list_runtime_profiles
from src.workflow_ui.main import app


def test_runtime_profiles_seeded(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    ensure_seeded()
    profiles = list_runtime_profiles()
    assert len(profiles) >= 2
    assert any(p.migrated_from_agent_key == "requirements-agent" for p in profiles)
    keys = {p.key for p in build_runtime_profiles()}
    assert "default-gigachat" in keys


def test_runtime_profiles_api_crud(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    listed = client.get("/api/v1/runtime-profiles")
    assert listed.status_code == 200
    assert len(listed.json()["runtime_profiles"]) >= 1

    created = client.post("/api/v1/runtime-profiles", json={
        "key": "test-profile",
        "name": "Test Profile",
        "provider": "lm_studio",
        "model": "test-model",
        "status": "draft",
    })
    assert created.status_code == 200
    pid = created.json()["id"]

    validated = client.post(f"/api/v1/runtime-profiles/{pid}/validate")
    assert validated.status_code == 200
    assert validated.json()["valid"] is True

    tested = client.post(f"/api/v1/runtime-profiles/{pid}/test")
    assert tested.status_code == 200
    assert tested.json()["ok"] is True


def test_dashboard_summary_api(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    r = client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    assert "scenarios_published" in body
    assert "runtime_profiles" in body
    assert "pending_approvals" in body
    assert "capabilities_total" in body
    assert "integrations_total" in body
    assert "audit_events" in body
    assert "rules_total" in body
    assert client.get("/api/v1/dashboard/pending-actions").status_code == 200


def test_agents_legacy_still_readable(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    r = client.get("/api/v1/agents")
    assert r.status_code == 200
    assert "agents" in r.json()


def test_ui_index_has_v2_nav_sections():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "src/workflow_ui/static/index.html").read_text(
        encoding="utf-8"
    )
    assert "СБОРКА" in html
    assert "ЗАПУСК" in html
    assert "УПРАВЛЕНИЕ" in html
    assert "Профили исполнения" in html
    assert 'data-view="runtime-profiles"' in html
    assert 'data-view="agents"' not in html.split("nav-menu")[1].split("</ul>")[0]
    assert "Реестр способностей" in html
    assert "Инспектор запуска" in html
