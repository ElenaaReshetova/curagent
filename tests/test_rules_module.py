"""Rules module API — catalog, detail, resolve preview, publish."""

from fastapi.testclient import TestClient

from src.workflow_ui.main import app


def test_rules_catalog_and_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.get("/api/v1/rules")
    assert response.status_code == 200
    payload = response.json()
    assert payload["rules"]
    assert payload["metrics"]["published"] >= 1
    assert any(r["key"] == "corporate-writing-style" for r in payload["rules"])

    filtered = client.get("/api/v1/rules", params={"category": "TERMINOLOGY", "scope": "DOMAIN"})
    assert filtered.status_code == 200
    assert all(r["category"] == "TERMINOLOGY" for r in filtered.json()["rules"])


def test_rules_detail_validate_and_resolve(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    catalog = client.get("/api/v1/rules").json()["rules"]
    item = next(r for r in catalog if r["key"] == "system-requirements-structure")
    detail = client.get(f"/api/v1/rules/{item['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["rule"]["category"] == "FORMAT"
    assert "Mandatory sections" in body["published_version"]["content_markdown"]
    assert "mcp://" not in detail.text.lower()
    assert "bypass control" not in detail.text.lower()

    ver_id = body["published_version"]["id"]
    report = client.post(f"/api/v1/rules/{item['id']}/versions/{ver_id}/validate")
    assert report.status_code == 200
    assert report.json()["valid"] is True

    preview = client.post("/api/v1/rules/resolve/preview", json={"playbook": "System Requirements"})
    assert preview.status_code == 200
    data = preview.json()
    assert data["matched"] >= 1
    assert "Effective Rule Bundle" in data["bundle_markdown"]


def test_rules_create_rejects_control_bypass(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    created = client.post("/api/v1/rules", json={
        "name": "Bad Bypass Rule",
        "category": "STYLE",
        "scope_type": "TEAM",
        "content_markdown": "Please bypass control gates and skip approval.",
    })
    assert created.status_code == 200
    skill_id = created.json()["rule"]["id"]
    version_id = created.json()["draft_version"]["id"]
    report = client.post(f"/api/v1/rules/{skill_id}/versions/{version_id}/validate")
    assert report.status_code == 200
    assert report.json()["valid"] is False


def test_rules_usage_without_playbook_bindings(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    catalog = client.get("/api/v1/rules").json()["rules"]
    rule = next(r for r in catalog if r["key"] == "corporate-writing-style")
    usage = client.get(f"/api/v1/rules/{rule['id']}/usage")
    assert usage.status_code == 200
    assert usage.json()["usages"] == []


def test_legacy_overview_and_rules_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    overview = client.get("/api/v1/overview")
    assert overview.status_code == 200
    assert client.get("/api/v1/rules").json()["rules"]
    # legacy RuleSet seed still available via store for other consumers
    assert client.get("/api/v1/controls").json()["controls"]
