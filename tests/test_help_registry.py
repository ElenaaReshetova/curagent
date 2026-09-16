"""Contextual help registry API."""

from fastapi.testclient import TestClient

from src.platform.help import clear_help_cache
from src.workflow_ui.main import app


def test_help_catalog_ru_contains_skill_slot():
    clear_help_cache()
    client = TestClient(app)
    response = client.get("/api/v1/help", params={"locale": "ru-RU", "prefix": "skill-slot"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["locale"] == "ru-RU"
    keys = {c["conceptKey"] for c in payload["concepts"]}
    assert "skill-slot" in keys
    assert "skill-slot.version-policy" in keys
    assert "skill-slot.runtime-profile" in keys
    slot = next(c for c in payload["concepts"] if c["conceptKey"] == "skill-slot")
    desc = slot["shortDescription"] or ""
    assert "playbook" in desc.lower() or "skill" in desc.lower()
    assert slot["title"]


def test_help_catalog_ru_contains_knowledge_space_fields():
    clear_help_cache()
    client = TestClient(app)
    response = client.get("/api/v1/help", params={"locale": "ru-RU", "prefix": "knowledge-space"})
    assert response.status_code == 200
    keys = {c["conceptKey"] for c in response.json()["concepts"]}
    assert "knowledge-space" in keys
    assert "knowledge-space.name" in keys
    assert "knowledge-space.key" in keys
    assert "knowledge-space.type" in keys
    assert "knowledge-space.classification" in keys
    assert "knowledge-space.purpose" in keys
    key_help = client.get("/api/v1/help/knowledge-space.key", params={"locale": "ru-RU"})
    assert key_help.status_code == 200
    body = key_help.json()
    assert "slug" in (body["shortDescription"] or "").lower() or "payments" in (body["shortDescription"] or "").lower()


def test_help_concept_get_and_en_fallback():
    clear_help_cache()
    client = TestClient(app)
    ru = client.get("/api/v1/help/skill-slot.version-policy", params={"locale": "ru-RU"})
    assert ru.status_code == 200
    assert "PINNED" in ru.json()["fullDescription"] or "верси" in ru.json()["fullDescription"].lower()

    en = client.get("/api/v1/help/skill-slot", params={"locale": "en-US"})
    assert en.status_code == 200
    assert en.json()["conceptKey"] == "skill-slot"

    missing = client.get("/api/v1/help/does-not-exist-xyz")
    assert missing.status_code == 404
