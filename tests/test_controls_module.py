"""Controls module API — catalog, detail, validate, test, resolve."""

from fastapi.testclient import TestClient

from src.workflow_ui.main import app


def test_controls_catalog_and_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.get("/api/v1/controls")
    assert response.status_code == 200
    payload = response.json()
    assert payload["controls"]
    metrics = payload["metrics"]
    assert metrics["active"] >= 1
    assert metrics["evaluations_today"] != 8412
    assert metrics["open_violations"] == sum(c["violations_count"] for c in payload["controls"])
    assert any(c["key"] == "human-approval-before-publication" for c in payload["controls"])
    assert any(c["violations_count"] > 0 for c in payload["controls"])

    filtered = client.get("/api/v1/controls", params={"type": "PUBLICATION_GATE", "severity": "HIGH", "status": "ACTIVE"})
    assert filtered.status_code == 200
    items = filtered.json()["controls"]
    assert items
    assert all(c["control_type"] == "PUBLICATION_GATE" for c in items)
    assert all(c["severity"] == "HIGH" for c in items)


def test_controls_detail_validate_test_and_resolve(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    catalog = client.get("/api/v1/controls").json()["controls"]
    item = next(c for c in catalog if c["key"] == "human-approval-before-publication")
    detail = client.get(f"/api/v1/controls/{item['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["control"]["key"] == "human-approval-before-publication"
    assert body["current_version"]["expression"]
    assert body["violations"]

    validation = client.post(f"/api/v1/controls/{item['id']}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    test = client.post(
        f"/api/v1/controls/{item['id']}/test",
        json={"context": {"checkpoint": {"status": "PENDING"}}, "execution_id": "EXE-TEST-001"},
    )
    assert test.status_code == 200
    assert test.json()["ok"] is False

    metrics_after = client.get("/api/v1/controls").json()["metrics"]
    assert metrics_after["evaluations_today"] >= 1

    resolve = client.post("/api/v1/controls/resolve", json={
        "environment": "PRODUCTION",
        "flow": "Feature Delivery",
        "artifact": "SYSTEM_REQUIREMENTS",
        "risk": "HIGH",
    })
    assert resolve.status_code == 200
    assert resolve.json()["matched"] >= 1
    assert resolve.json()["controls"]


def test_controls_create_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    created = client.post("/api/v1/controls", json={
        "name": "Rollback plan required",
        "type": "QUALITY_GATE",
        "severity": "HIGH",
        "description": "Artifacts must document rollback behavior.",
    })
    assert created.status_code == 200
    body = created.json()
    assert body["control"]["status"] == "draft"
    assert body["control"]["key"] == "rollback-plan-required"
    assert body["current_version"]["status"] == "DRAFT"
    assert body["editable_version"]["status"] == "DRAFT"


def test_controls_edit_active_creates_draft_and_saves(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    catalog = client.get("/api/v1/controls").json()["controls"]
    item = next(c for c in catalog if c["key"] == "human-approval-before-publication")
    assert item["status"] == "ACTIVE"

    drafted = client.post(f"/api/v1/controls/{item['id']}/draft")
    assert drafted.status_code == 200
    assert drafted.json()["draft_version"]["status"] == "DRAFT"
    assert drafted.json()["draft_version"]["semantic_version"] != item.get("version")

    updated = client.put(f"/api/v1/controls/{item['id']}", json={
        "name": "Human approval before publication (edited)",
        "expression": 'context.checkpoint.status == "APPROVED"',
        "severity": "CRITICAL",
        "evaluation_point": "BEFORE_ARTIFACT_PUBLICATION",
        "enforcement_on_failed": "REQUIRE_HUMAN_APPROVAL",
        "applicability": "artifact.type=SYSTEM_REQUIREMENTS\nenvironment=PRODUCTION",
        "remediation_steps": "Request checkpoint approval\nAttach decision record",
    })
    assert updated.status_code == 200
    draft = updated.json()["draft_version"]
    assert updated.json()["control"]["name"] == "Human approval before publication (edited)"
    assert draft["severity"] == "CRITICAL"
    assert draft["status"] == "DRAFT"
    assert len(draft["applicability"]) == 2
    assert draft["remediation_steps"] == ["Request checkpoint approval", "Attach decision record"]

    activated = client.post(f"/api/v1/controls/{item['id']}/activate")
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    detail = client.get(f"/api/v1/controls/{item['id']}").json()
    assert detail["current_version"]["status"] == "ACTIVE"
    assert detail["current_version"]["severity"] == "CRITICAL"
    assert detail["draft_version"] is None


def test_controls_cyrillic_name_gets_nonempty_key(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    created = client.post("/api/v1/controls", json={
        "name": "Проверка персональных данных",
        "type": "COMPLIANCE",
        "severity": "CRITICAL",
        "description": "Не допускать PII в артефакте.",
    })
    assert created.status_code == 200
    key = created.json()["control"]["key"]
    assert key
    assert key == "proverka-personalnyh-dannyh"


def test_controls_detail_tolerates_list_violations(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    catalog = client.get("/api/v1/controls").json()["controls"]
    item = next(c for c in catalog if c["key"] == "human-approval-before-publication")
    # Break storage into legacy list shape, then ensure detail still works.
    from pathlib import Path
    import json
    path = Path(tmp_path) / "control_violations.json"
    path.write_text(json.dumps({"violations": []}), encoding="utf-8")
    detail = client.get(f"/api/v1/controls/{item['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert "violations" in body
    assert body["violations"] == []
    assert body["control"]["key"] == "human-approval-before-publication"


def test_governed_catalog_still_lists_controls(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    response = client.get("/api/v1/controls")
    assert response.status_code == 200
    assert response.json()["controls"]
