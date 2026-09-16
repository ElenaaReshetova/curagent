"""Skills module API — catalog, inheritance, package files, publish."""

from fastapi.testclient import TestClient

from src.platform.db.schema import init_schema
from src.platform.db.session import reset_engine_cache
from src.workflow_ui.main import app


def _json_store(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("PLATFORM_DATABASE_URL", raising=False)
    monkeypatch.setenv("SKILLS_STORE", "json")


def test_skills_catalog_and_metrics(tmp_path, monkeypatch):
    _json_store(tmp_path, monkeypatch)
    client = TestClient(app)

    response = client.get("/api/v1/skills")
    assert response.status_code == 200
    payload = response.json()
    assert payload["skills"]
    assert payload["metrics"]["skills"] >= 1
    assert any(s["key"] == "team-system-requirements" for s in payload["skills"])
    assert any(s["immutable"] for s in payload["skills"] if s["skill_type"] == "CORPORATE")

    filtered = client.get("/api/v1/skills", params={"skillType": "TEAM", "q": "System"})
    assert filtered.status_code == 200
    assert all(s["skill_type"] == "TEAM" for s in filtered.json()["skills"])
    assert any("System Requirements" in s["name"] for s in filtered.json()["skills"])


def test_skills_detail_editor_validate_publish(tmp_path, monkeypatch):
    _json_store(tmp_path, monkeypatch)
    client = TestClient(app)

    catalog = client.get("/api/v1/skills").json()["skills"]
    item = next(s for s in catalog if s["key"] == "team-system-requirements")
    detail = client.get(f"/api/v1/skills/{item['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["skill"]["key"] == "team-system-requirements"
    assert body["skill"]["immutable"] is False
    assert body["published_version"]["interface_key"] == "analysis.system_requirements.generate@1"
    assert "context.read" in body["published_version"]["allowed_capabilities"]
    assert "artifact.patch" in body["published_version"]["allowed_capabilities"]
    assert "mcp://" not in detail.text.lower()
    assert "agent_id" not in detail.text.lower()

    draft_id = body["draft_version"]["id"]
    skill_id = body["skill"]["id"]

    manifest_file = next(
        f for f in body["draft_version"]["files"] if f["path"] == "manifest.yaml"
    )
    assert (manifest_file.get("content_text") or "").strip()
    assert "implements" in manifest_file["content_text"] or "interface_key" in manifest_file["content_text"]

    report = client.post(f"/api/v1/skills/{skill_id}/versions/{draft_id}/validate")
    assert report.status_code == 200
    payload = report.json()
    assert payload["valid"] is True
    assert not any(e.get("code") == "CAPABILITY_EXCEEDS_INTERFACE" for e in payload.get("errors") or [])
    codes = {w.get("code") for w in payload.get("warnings") or []}
    assert "MISSING_EXAMPLE" not in codes
    assert "MISSING_EMPTY_EVIDENCE_TEST" not in codes

    refreshed = client.get(f"/api/v1/skills/{skill_id}").json()
    draft_files = {f["path"] for f in refreshed["draft_version"]["files"]}
    assert any(p.startswith("examples/") for p in draft_files)
    assert any(
        "empty" in (t.get("key") or "").lower() or "empty" in (t.get("name") or "").lower()
        for t in refreshed["draft_version"]["test_cases"]
    )

    saved = client.put(
        f"/api/v1/skills/{skill_id}/versions/{draft_id}/files/SKILL.md",
        json={"content": body["draft_version"]["skill_markdown"] + "\n# Notes\nUpdated.\n", "revision": 1},
    )
    assert saved.status_code == 200
    assert saved.json()["revision"] == 2

    published = client.post(f"/api/v1/skills/{skill_id}/versions/{draft_id}/publish")
    assert published.status_code == 200
    assert published.json()["published_version"]["id"] == draft_id


def test_corporate_skill_is_immutable(tmp_path, monkeypatch):
    _json_store(tmp_path, monkeypatch)
    client = TestClient(app)

    catalog = client.get("/api/v1/skills").json()["skills"]
    corp = next(s for s in catalog if s["key"] == "corporate-requirements-quality")
    assert corp["immutable"] is True

    detail = client.get(f"/api/v1/skills/{corp['id']}").json()
    assert detail["skill"]["immutable"] is True
    published = detail["published_version"]
    assert published is not None

    blocked = client.post(f"/api/v1/skills/{corp['id']}/versions")
    assert blocked.status_code == 403

    create_blocked = client.post("/api/v1/skills", json={
        "name": "Fake Corporate",
        "skill_type": "CORPORATE",
        "interface_key": "analysis.requirements.validate@2",
    })
    assert create_blocked.status_code == 400


def test_inherit_corporate_and_attach_files(tmp_path, monkeypatch):
    _json_store(tmp_path, monkeypatch)
    client = TestClient(app)

    catalog = client.get("/api/v1/skills").json()["skills"]
    corp = next(s for s in catalog if s["key"] == "corporate-requirements-quality")

    inherited = client.post(
        f"/api/v1/skills/{corp['id']}/inherit",
        json={"name": "Payments Quality Review", "description": "Team overlay"},
    )
    assert inherited.status_code == 200
    body = inherited.json()
    assert body["skill"]["skill_type"] == "TEAM"
    assert body["skill"]["immutable"] is False
    assert body["skill"]["parent_skill_id"] == corp["id"]
    assert body["parent"]["key"] == "corporate-requirements-quality"
    assert body["draft_version"] is not None

    skill_id = body["skill"]["id"]
    draft_id = body["draft_version"]["id"]
    rev = body["draft_version"]["revision"]

    folder = client.post(
        f"/api/v1/skills/{skill_id}/versions/{draft_id}/files",
        json={"path": "agents/", "kind": "folder", "revision": rev},
    )
    assert folder.status_code == 200
    rev = folder.json()["revision"]

    agent = client.post(
        f"/api/v1/skills/{skill_id}/versions/{draft_id}/files",
        json={
            "path": "agents/reviewer.md",
            "kind": "file",
            "content": "# Reviewer subagent\nFocus on payments terminology.\n",
            "revision": rev,
        },
    )
    assert agent.status_code == 200
    paths = {f["path"] for f in agent.json()["files"]}
    assert "agents/" in paths
    assert "agents/reviewer.md" in paths
    assert any(f["path"].startswith("templates/") for f in agent.json()["files"])

    listed = client.get(f"/api/v1/skills/{skill_id}/versions/{draft_id}/files")
    assert listed.status_code == 200
    assert any(f["path"] == "agents/reviewer.md" for f in listed.json()["files"])

    rev = agent.json()["revision"]
    updated = client.put(
        f"/api/v1/skills/{skill_id}/versions/{draft_id}/files/scripts/check.py",
        json={"content": "print('ok')\n", "kind": "file", "revision": rev},
    )
    assert updated.status_code == 200
    assert any(f["path"] == "scripts/check.py" for f in updated.json()["files"])

    rev = updated.json()["revision"]
    moved = client.post(
        f"/api/v1/skills/{skill_id}/versions/{draft_id}/files/move",
        json={
            "from_path": "scripts/check.py",
            "to_path": "agents/check.py",
            "revision": rev,
        },
    )
    assert moved.status_code == 200
    moved_paths = {f["path"] for f in moved.json()["files"]}
    assert "agents/check.py" in moved_paths
    assert "scripts/check.py" not in moved_paths


def test_skills_create_rejects_mcp_refs(tmp_path, monkeypatch):
    _json_store(tmp_path, monkeypatch)
    client = TestClient(app)
    iface = client.get("/api/v1/skill-interfaces").json()["skill_interfaces"][0]["key"]

    created = client.post("/api/v1/skills", json={
        "name": "Unsafe Import",
        "skill_type": "IMPORTED",
        "interface_key": iface,
        "skill_markdown": "Call jira_get_issue directly via mcp://server",
    })
    assert created.status_code == 200
    skill_id = created.json()["skill"]["id"]
    version_id = created.json()["draft_version"]["id"]
    report = client.post(f"/api/v1/skills/{skill_id}/versions/{version_id}/validate")
    assert report.status_code == 200
    assert report.json()["valid"] is False
    assert any("prohibited" in e["message"] for e in report.json()["errors"])


def test_versioned_skill_create_and_validate_rejects_tool_refs(tmp_path, monkeypatch):
    _json_store(tmp_path, monkeypatch)
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
    skill_id = skill.json().get("id") or skill.json().get("skill", {}).get("id")
    validation = client.post(f"/api/v1/skills/{skill_id}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is False
    assert "jira_" in validation.json()["errors"][0]


def test_skills_postgres_inherit(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'skills.db'}"
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("PLATFORM_DATABASE_URL", url)
    monkeypatch.setenv("SKILLS_STORE", "postgres")
    reset_engine_cache()
    init_schema(url)

    client = TestClient(app)
    catalog = client.get("/api/v1/skills").json()["skills"]
    assert catalog
    corp = next(s for s in catalog if s["skill_type"] == "CORPORATE")
    inherited = client.post(
        f"/api/v1/skills/{corp['id']}/inherit",
        json={"name": "DB Derived Skill"},
    )
    assert inherited.status_code == 200
    body = inherited.json()
    assert body["skill"]["parent_skill_id"] == corp["id"]
    assert body["skill"]["skill_type"] == "TEAM"

    skill_id = body["skill"]["id"]
    draft_id = body["draft_version"]["id"]
    rev = body["draft_version"]["revision"]
    added = client.post(
        f"/api/v1/skills/{skill_id}/versions/{draft_id}/files",
        json={"path": "templates/extra.md", "content": "# Extra\n", "revision": rev},
    )
    assert added.status_code == 200
    detail = client.get(f"/api/v1/skills/{skill_id}").json()
    paths = {f["path"] for f in detail["draft_version"]["files"]}
    assert "templates/extra.md" in paths
