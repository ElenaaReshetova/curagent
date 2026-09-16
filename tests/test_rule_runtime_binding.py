"""Runtime rule binding: resolve bound keys and inject into skill executor prompt."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.agent.core.executor_prompt import build_executor_system_prompt
from src.platform.graphs.bindings import bound_rule_keys_for_skill
from src.platform.rules import service as rules_svc
from src.workflow_ui.main import app


def test_resolve_bound_bundle_includes_russian_output(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    assert client.get("/api/v1/rules").status_code == 200

    bundle = rules_svc.resolve_bound_bundle(["ru-output-language"])
    assert bundle["matched"] == 1
    assert bundle["effective_rule_keys"] == ["ru-output-language"]
    assert "Bound Rule Bundle" in bundle["bundle_markdown"]
    assert "русск" in bundle["bundle_markdown"].lower()


def test_resolve_preview_honors_bound_rule_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    client = TestClient(app)
    assert client.get("/api/v1/rules").status_code == 200

    preview = client.post(
        "/api/v1/rules/resolve/preview",
        json={"rule_keys": ["ru-output-language"]},
    )
    assert preview.status_code == 200
    data = preview.json()
    assert data["effective_rule_keys"] == ["ru-output-language"]
    assert "русск" in data["bundle_markdown"].lower()


def test_bound_rule_keys_without_graph_bindings(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    assert bound_rule_keys_for_skill("business-requirements") == []


def test_executor_prompt_injects_bound_rules():
    prompt = build_executor_system_prompt(
        "# Skill\nWrite a BRD. Language: English headings.",
        (
            "# Bound Rule Bundle\n\n"
            "## Russian Output Language (`ru-output-language`)\n"
            "Все пользовательские артефакты должны быть написаны на русском языке.\n"
        ),
    )
    assert "Bound Rules (MUST APPLY" in prompt
    assert "ru-output-language" in prompt
    assert "OUTPUT LANGUAGE — HARD CONSTRAINT" in prompt
    assert "русском" in prompt.lower()
    # Bound rules must appear before the skill template so language wins.
    assert prompt.find("Bound Rules") < prompt.find("Assigned Skill")


def test_forces_russian_hard_constraint():
    from src.agent.core.executor_prompt import forces_russian_output, language_hard_constraint

    md = "## Russian Output Language (`ru-output-language`)\nПиши на русском.\n"
    assert forces_russian_output(md) is True
    assert "HARD CONSTRAINT" in language_hard_constraint(md)
