"""Runtime Profiles module API — catalog, detail, validate, test, resolve, mutations."""

from fastapi.testclient import TestClient

from src.workflow_ui.main import app


def test_runtime_profiles_catalog_and_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.get("/api/v1/runtime-profiles")
    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime_profiles"]
    assert payload["metrics"]["active_profiles"] >= 1
    assert any(p["key"] == "qwen-production" for p in payload["runtime_profiles"])

    filtered = client.get("/api/v1/runtime-profiles", params={"type": "PRODUCTION", "provider": "QWEN_CODE_CLI"})
    assert filtered.status_code == 200
    items = filtered.json()["runtime_profiles"]
    assert all(p["profile_type"] == "PRODUCTION" for p in items)
    assert all(p["provider"] == "QWEN_CODE_CLI" for p in items)


def test_runtime_profiles_detail_validate_test_resolve(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    catalog = client.get("/api/v1/runtime-profiles").json()["runtime_profiles"]
    item = next(p for p in catalog if p["key"] == "qwen-production")
    detail = client.get(f"/api/v1/runtime-profiles/{item['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["current_version"]["provider"] == "QWEN_CODE_CLI"
    assert body["effective_runtime"]["sandbox"] == "CONTAINER"
    assert "sk-" not in detail.text.lower()

    validation = client.post(f"/api/v1/runtime-profiles/{item['id']}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    test = client.post(f"/api/v1/runtime-profiles/{item['id']}/test")
    assert test.status_code == 200
    assert test.json()["ok"] is True

    resolve = client.post("/api/v1/runtime-profiles/resolve", json={
        "flow_key": "feature-delivery",
        "graph_key": "system-requirements",
        "skill_key": "generate-requirements",
    })
    assert resolve.status_code == 200
    assert resolve.json()["matched"] is True
    assert resolve.json()["profile_key"] == "qwen-production"


def test_runtime_profiles_create_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    created = client.post("/api/v1/runtime-profiles", json={
        "name": "Staging Runtime",
        "type": "TEST",
        "provider": "OPENAI_API",
    })
    assert created.status_code == 200
    assert created.json()["profile"]["status"] == "draft"
    assert created.json()["profile"]["key"] == "staging-runtime"
    assert created.json()["current_version"]["status"] == "DRAFT"
    assert created.json()["draft_version"]["status"] == "DRAFT"


def test_runtime_profiles_patch_and_activate(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    created = client.post("/api/v1/runtime-profiles", json={
        "name": "Editable Runtime",
        "type": "DEVELOPMENT",
        "provider": "LOCAL_VLLM",
    }).json()
    profile_id = created["profile"]["id"]

    patched = client.patch(f"/api/v1/runtime-profiles/{profile_id}", json={
        "name": "Editable Runtime v2",
        "model": "qwen-local-32b",
        "sandbox": "CONTAINER",
        "temperature": 0.4,
        "limits": {
            "maxExecutionSeconds": 600,
            "maxOutputTokens": 8000,
            "maxRetries": 2,
            "maxConcurrentRuns": 2,
        },
        "capabilities": {
            "allow": ["context.search", "repository.read"],
            "deny": [],
            "approval_required": ["artifact.publish"],
        },
        "secret_ref": "vault://ai/editable",
    })
    assert patched.status_code == 200
    body = patched.json()
    assert body["profile"]["name"] == "Editable Runtime v2"
    assert body["draft_version"]["model"] == "qwen-local-32b"
    assert body["draft_version"]["generation_config"]["temperature"] == 0.4
    assert body["draft_version"]["limits"]["maxExecutionSeconds"] == 600
    assert "repository.read" in body["draft_version"]["capabilities"]["allow"]

    validation = client.post(f"/api/v1/runtime-profiles/{profile_id}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    activated = client.post(f"/api/v1/runtime-profiles/{profile_id}/activate")
    assert activated.status_code == 200
    active = activated.json()
    assert active["profile"]["status"] == "active"
    assert active["current_version"]["status"] == "ACTIVE"
    assert active["current_version"]["model"] == "qwen-local-32b"
    assert active["draft_version"] is None


def test_runtime_profiles_create_draft_from_active(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    catalog = client.get("/api/v1/runtime-profiles").json()["runtime_profiles"]
    item = next(p for p in catalog if p["key"] == "qwen-production")
    profile_id = item["id"]

    before = client.get(f"/api/v1/runtime-profiles/{profile_id}").json()
    assert before["current_version"]["status"] == "ACTIVE"
    assert before["draft_version"] is None

    draft = client.post(f"/api/v1/runtime-profiles/{profile_id}/draft")
    assert draft.status_code == 200
    body = draft.json()
    assert body["draft_version"]["status"] == "DRAFT"
    assert body["draft_version"]["semantic_version"] != before["current_version"]["semantic_version"]
    assert body["current_version"]["status"] == "ACTIVE"

    # Idempotent: existing draft is reused
    again = client.post(f"/api/v1/runtime-profiles/{profile_id}/draft")
    assert again.status_code == 200
    assert again.json()["draft_version"]["id"] == body["draft_version"]["id"]


def test_runtime_profiles_activate_invalid_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)

    created = client.post("/api/v1/runtime-profiles", json={
        "name": "Invalid Production",
        "type": "PRODUCTION",
        "provider": "QWEN_CODE_CLI",
    }).json()
    profile_id = created["profile"]["id"]

    patched = client.patch(f"/api/v1/runtime-profiles/{profile_id}", json={
        "sandbox": "NONE",
        "model": "",
    })
    assert patched.status_code == 200
    assert patched.json()["draft_version"]["validation_status"] == "invalid"

    activate = client.post(f"/api/v1/runtime-profiles/{profile_id}/activate")
    assert activate.status_code == 400
    assert "invalid" in activate.json()["detail"].lower()


def test_governed_catalog_still_lists_runtime_profiles(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    response = client.get("/api/v1/runtime-profiles")
    assert response.status_code == 200
    assert response.json()["runtime_profiles"]
