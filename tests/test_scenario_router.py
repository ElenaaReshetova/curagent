"""Pre-scenario classify → template selection."""

from src.orchestrator.classifier import classify_task
from src.orchestrator.scenario_router import resolve_scenario_template, template_for_skill


def test_template_for_system_requirements():
    assert template_for_skill("system-requirements") == "generate-system-requirements"


def test_template_for_business_requirements():
    assert template_for_skill("business-requirements") == "generate-business-requirements-slack"


def test_template_for_code_analysis_security_policy():
    assert template_for_skill("code-analysis") == "generate-security-policy-review"
    assert template_for_skill("normalize-task") == "generate-security-policy-review"


def test_resolve_from_classify_system_query():
    text = (
        "Сгенерируй системные требования для функции: онбординг нового сотрудника "
        "с SSO и чеклистом первых 30 дней. Нужны user stories, P0/P1 требования "
        "и метрики успеха."
    )
    routing = classify_task(text)
    assert routing.primary_skill == "system-requirements"
    template_id, reason = resolve_scenario_template(
        primary_skill=routing.primary_skill,
        requested_template_id="generate-brd-srd-slack",  # must be ignored
    )
    assert template_id == "generate-system-requirements"
    assert reason.startswith("classify:")


def test_resolve_from_classify_business_query():
    routing = classify_task("Сгенерируй бизнес-требования: user stories и метрики")
    assert routing.primary_skill == "business-requirements"
    template_id, reason = resolve_scenario_template(primary_skill=routing.primary_skill)
    assert template_id == "generate-business-requirements-slack"
    assert reason.startswith("classify:")
