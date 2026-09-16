"""Knowledge Spaces module API — catalog, detail, search playground."""

from fastapi.testclient import TestClient

from src.workflow_ui.main import app


def test_knowledge_catalog_and_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.get("/api/v1/knowledge-spaces")
    assert response.status_code == 200
    payload = response.json()
    assert payload["knowledge_spaces"]
    assert payload["metrics"]["active_spaces"] >= 1
    assert any(s["key"] == "payments" for s in payload["knowledge_spaces"])

    filtered = client.get("/api/v1/knowledge-spaces", params={"type": "DOMAIN", "status": "ACTIVE"})
    assert filtered.status_code == 200
    assert all(s["space_type"] == "DOMAIN" for s in filtered.json()["knowledge_spaces"])


def test_knowledge_detail_and_search(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    catalog = client.get("/api/v1/knowledge-spaces").json()["knowledge_spaces"]
    item = next(s for s in catalog if s["key"] == "payments")
    detail = client.get(f"/api/v1/knowledge-spaces/{item['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["space"]["space_type"] == "DOMAIN"
    assert len(body["sources"]) >= 3
    assert "mcp://" not in detail.text.lower()

    search = client.post(
        f"/api/v1/knowledge-spaces/{item['id']}/search",
        json={"query": "отмена платежа", "information_need": "Architecture context"},
    )
    assert search.status_code == 200
    data = search.json()
    assert data["evidence_count"] >= 1
    assert data["evidence"][0]["score"] >= data["evidence"][-1]["score"]

    health = client.get(f"/api/v1/knowledge-spaces/{item['id']}/health")
    assert health.status_code == 200
    assert "overall_pct" in health.json()


def test_knowledge_create_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    created = client.post("/api/v1/knowledge-spaces", json={
        "name": "Lending Domain",
        "type": "DOMAIN",
        "classification": "CONFIDENTIAL",
        "purpose": "Trusted lending context without direct MCP tool refs.",
        "project_areas": ["lending", "risk"],
        "team_names": ["Lending squad", "Risk"],
        "additional_context": "Prioritize underwriting and affordability policies.",
    })
    assert created.status_code == 200
    assert created.json()["space"]["status"] == "DRAFT"
    assert created.json()["space"]["key"] == "lending-domain"
    assert created.json()["space"]["project_areas"] == ["lending", "risk"]
    assert created.json()["space"]["team_names"] == ["Lending squad", "Risk"]
    assert created.json()["space"]["additional_context"] == "Prioritize underwriting and affordability policies."


def test_knowledge_activate_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    created = client.post("/api/v1/knowledge-spaces", json={
        "name": "Onboarding Domain",
        "key": "onboarding",
        "type": "DOMAIN",
        "purpose": "Trusted onboarding context for KYC and account opening.",
    })
    assert created.status_code == 200
    space_id = created.json()["space"]["id"]
    assert created.json()["space"]["status"] == "DRAFT"

    blocked = client.post(f"/api/v1/knowledge-spaces/{space_id}/activate")
    assert blocked.status_code == 400
    assert "source" in blocked.json()["detail"].lower()

    client.post(f"/api/v1/knowledge-spaces/{space_id}/sources", json={
        "name": "Jira ONB",
        "provider": "jira",
        "priority": 80,
        "status": "ACTIVE",
        "selector": {"project": "ONB"},
    })

    activated = client.post(f"/api/v1/knowledge-spaces/{space_id}/activate")
    assert activated.status_code == 200
    assert activated.json()["space"]["status"] == "ACTIVE"

    again = client.post(f"/api/v1/knowledge-spaces/{space_id}/activate")
    assert again.status_code == 200
    assert again.json()["space"]["status"] == "ACTIVE"


def test_knowledge_disable_active(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    created = client.post("/api/v1/knowledge-spaces", json={
        "name": "Billing Domain",
        "key": "billing",
        "type": "DOMAIN",
        "purpose": "Trusted billing context for invoices and settlements.",
    }).json()["space"]
    space_id = created["id"]

    client.post(f"/api/v1/knowledge-spaces/{space_id}/sources", json={
        "name": "Jira BILL",
        "provider": "jira",
        "priority": 70,
        "status": "ACTIVE",
        "selector": {"project": "BILL"},
    })
    assert client.post(f"/api/v1/knowledge-spaces/{space_id}/activate").status_code == 200

    disabled = client.post(f"/api/v1/knowledge-spaces/{space_id}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["space"]["status"] == "DISABLED"

    again = client.post(f"/api/v1/knowledge-spaces/{space_id}/disable")
    assert again.status_code == 200
    assert again.json()["space"]["status"] == "DISABLED"

    draft_block = client.post("/api/v1/knowledge-spaces", json={
        "name": "Draft Only",
        "key": "draft-only",
        "purpose": "Cannot disable while still draft.",
    }).json()["space"]
    blocked = client.post(f"/api/v1/knowledge-spaces/{draft_block['id']}/disable")
    assert blocked.status_code == 400

    reactivated = client.post(f"/api/v1/knowledge-spaces/{space_id}/activate")
    assert reactivated.status_code == 200
    assert reactivated.json()["space"]["status"] == "ACTIVE"


def test_knowledge_update_context_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    item = next(
        space for space in client.get("/api/v1/knowledge-spaces").json()["knowledge_spaces"]
        if space["key"] == "payments"
    )
    updated = client.put(f"/api/v1/knowledge-spaces/{item['id']}", json={
        "description": "Context for payment processing and fraud review.",
        "project_areas": ["payments", "fraud"],
        "team_names": ["PAY squad", "Risk"],
        "additional_context": "Escalate PCI-sensitive questions to the payments security owner.",
    })

    assert updated.status_code == 200
    space = updated.json()["space"]
    assert space["purpose"] == "Context for payment processing and fraud review."
    assert space["project_areas"] == ["payments", "fraud"]
    assert space["team_names"] == ["PAY squad", "Risk"]
    assert space["additional_context"].startswith("Escalate PCI-sensitive")
    assert space["sources"]

    detail = client.get(f"/api/v1/knowledge-spaces/{item['id']}")
    assert detail.json()["space"]["project_areas"] == ["payments", "fraud"]


def test_knowledge_source_crud(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    item = next(
        space for space in client.get("/api/v1/knowledge-spaces").json()["knowledge_spaces"]
        if space["key"] == "payments"
    )
    before = client.get(f"/api/v1/knowledge-spaces/{item['id']}").json()
    before_count = len(before["sources"])

    created = client.post(f"/api/v1/knowledge-spaces/{item['id']}/sources", json={
        "name": "Git payments-docs",
        "provider": "git",
        "priority": 65,
        "status": "ACTIVE",
        "selector": {"repos": ["payments-docs"]},
    })
    assert created.status_code == 200
    sources = created.json()["sources"]
    assert len(sources) == before_count + 1
    new_src = next(s for s in sources if s["name"] == "Git payments-docs")
    assert new_src["provider"] == "git"
    assert new_src["selector"]["repos"] == ["payments-docs"]

    updated = client.put(
        f"/api/v1/knowledge-spaces/{item['id']}/sources/{new_src['id']}",
        json={
            "name": "Git payments-docs (updated)",
            "priority": 90,
            "status": "DISABLED",
            "selector": {"repos": ["payments-docs", "pay-handbook"]},
        },
    )
    assert updated.status_code == 200
    edited = next(s for s in updated.json()["sources"] if s["id"] == new_src["id"])
    assert edited["name"] == "Git payments-docs (updated)"
    assert edited["priority"] == 90
    assert edited["status"] == "DISABLED"
    assert edited["selector"]["repos"] == ["payments-docs", "pay-handbook"]

    deleted = client.delete(f"/api/v1/knowledge-spaces/{item['id']}/sources/{new_src['id']}")
    assert deleted.status_code == 200
    assert all(s["id"] != new_src["id"] for s in deleted.json()["sources"])
    assert len(deleted.json()["sources"]) == before_count


def test_governed_catalog_still_lists_knowledge_key(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    response = client.get("/api/v1/knowledge-spaces")
    assert response.status_code == 200
    assert response.json()["knowledge_spaces"]
