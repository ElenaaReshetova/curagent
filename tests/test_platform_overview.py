"""Platform seed / overview unit tests."""

from src.platform.seed.catalog import OPERATOR_CATALOG, build_overview


def test_operator_catalog_covers_mvp_keys():
    keys = {o.key for o in OPERATOR_CATALOG}
    required = {
        "analyze_external_work_item",
        "identify_stakeholders",
        "extract_requirements",
        "validate_requirements",
        "request_human_approval",
        "publish_result",
    }
    assert required.issubset(keys)
    assert 8 <= len(OPERATOR_CATALOG) <= 12


def test_overview_payload_shape():
    overview = build_overview()
    assert overview.agents[0].key == "requirements-agent"
    assert overview.playbooks == []
    assert overview.skills
    assert overview.controls
    assert overview.knowledge_spaces
    assert overview.blueprints[0].key == "system-requirements"
    assert overview.contract_templates
    assert overview.integrations
    assert overview.recent_executions
    data = overview.model_dump(mode="json")
    assert "playbooks" in data
    assert data["operators"][0]["key"]
    assert data["waiting_approvals_count"] == 1
