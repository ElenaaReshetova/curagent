"""Classifier routing and playbook skill-branch helpers."""

from types import SimpleNamespace

from src.orchestrator.classifier import classify_task
from src.orchestrator.models import ArtifactType, RoutingDecision
from src.orchestrator.routing_graph import (
    edge_matches_branch,
    next_step_id,
    resolve_skill_id,
)
from src.orchestrator.workflow_config.models import (
    StepType,
    WorkflowEdge,
    WorkflowStepConfig,
    WorkflowTemplate,
)


def test_classify_brd_keywords():
    r = classify_task("Нужно написать BRD и user stories для фичи SSO", "BRD SSO")
    assert r.primary_skill == "business-requirements"
    assert r.confidence >= 0.3


def test_classify_srs_keywords():
    r = classify_task("Prepare SRS and NFR for the payment API", "System requirements")
    assert r.primary_skill == "system-requirements"


def test_classify_system_requirements_over_brd_section_keywords():
    """Explicit SRD ask must win even when user stories / P0 / metrics are listed."""
    r = classify_task(
        "Сгенерируй системные требования для функции: онбординг нового сотрудника "
        "с SSO и чеклистом первых 30 дней. Нужны user stories, P0/P1 требования "
        "и метрики успеха.",
        "",
    )
    assert r.primary_skill == "system-requirements"
    assert r.confidence >= 0.5


def test_classify_business_requirements_explicit():
    r = classify_task(
        "Сгенерируй бизнес-требования для онбординга: user stories и метрики успеха",
        "",
    )
    assert r.primary_skill == "business-requirements"


def test_classify_tests_keywords():
    r = classify_task("Составь тест-кейсы и план тестирования для логина", "")
    assert r.primary_skill == "test-case-design"


def test_classify_code_keywords():
    r = classify_task("Please do a code review and security scan of auth module", "")
    assert r.primary_skill == "code-analysis"


def test_classify_fallback_general():
    r = classify_task("привет, как дела?", "")
    assert r.primary_skill == "general"


def test_edge_matches_skill_and_yes_no():
    assert edge_matches_branch("business-requirements", "business-requirements")
    assert edge_matches_branch("yes", "yes")
    assert edge_matches_branch("да", "yes")
    assert edge_matches_branch("default", "general")
    assert not edge_matches_branch("no", "yes")
    assert edge_matches_branch("approve", "approve")
    assert edge_matches_branch("yes", "approve")
    assert edge_matches_branch("request_changes", "request_changes")
    assert edge_matches_branch("clarify", "request_changes")
    assert not edge_matches_branch("no", "request_changes")
    assert edge_matches_branch("reject", "reject")
    assert edge_matches_branch("no", "reject")


def test_next_step_id_human_triad_does_not_fallback_unlabeled():
    template = WorkflowTemplate(
        id="t1",
        name="t",
        steps=[
            WorkflowStepConfig(id="approval", type=StepType.APPROVAL, label="Review"),
            WorkflowStepConfig(id="publish", type=StepType.PUBLICATION, label="Publish"),
            WorkflowStepConfig(id="work", type=StepType.SKILL, label="Work", skill_id="business-requirements"),
            WorkflowStepConfig(id="end", type=StepType.END, label="End"),
        ],
        edges=[
            WorkflowEdge(id="a1", from_step="approval", to_step="publish", label="approve"),
            WorkflowEdge(id="a2", from_step="approval", to_step="work", label="request_changes"),
            WorkflowEdge(id="a3", from_step="approval", to_step="end", label="reject"),
            WorkflowEdge(id="a4", from_step="publish", to_step="end", label=None),
        ],
    )
    assert next_step_id(template, "approval", "approve") == "publish"
    assert next_step_id(template, "approval", "request_changes") == "work"
    assert next_step_id(template, "approval", "reject") == "end"

    legacy = WorkflowTemplate(
        id="t2",
        name="t2",
        steps=template.steps,
        edges=[
            WorkflowEdge(id="b1", from_step="approval", to_step="publish", label=None),
            WorkflowEdge(id="b2", from_step="publish", to_step="end", label=None),
        ],
    )
    assert next_step_id(legacy, "approval", "approve") == "publish"
    assert next_step_id(legacy, "approval", "request_changes") is None
    assert next_step_id(legacy, "approval", "reject") is None


def test_next_step_routes_by_skill_label():
    t = WorkflowTemplate(
        id="t",
        name="t",
        steps=[
            WorkflowStepConfig(id="route", type=StepType.GATEWAY_OR, label="R", config={"mode": "route_skill"}),
            WorkflowStepConfig(id="brd", type=StepType.SKILL, label="BRD", skill_id="business-requirements"),
            WorkflowStepConfig(id="srs", type=StepType.SKILL, label="SRS", skill_id="system-requirements"),
            WorkflowStepConfig(id="gen", type=StepType.SKILL, label="G", skill_id="general"),
        ],
        edges=[
            WorkflowEdge(id="e1", from_step="route", to_step="brd", label="business-requirements"),
            WorkflowEdge(id="e2", from_step="route", to_step="srs", label="system-requirements"),
            WorkflowEdge(id="e3", from_step="route", to_step="gen", label="general"),
        ],
    )
    assert next_step_id(t, "route", "system-requirements") == "srs"
    assert next_step_id(t, "route", "business-requirements") == "brd"
    # Unknown skill must NOT silently fall through to the first labeled edge (was BRD).
    assert next_step_id(t, "route", "unknown-skill") is None


def test_next_step_default_fallback():
    t = WorkflowTemplate(
        id="t",
        name="t",
        steps=[
            WorkflowStepConfig(id="route", type=StepType.GATEWAY_OR, label="R"),
            WorkflowStepConfig(id="brd", type=StepType.SKILL, label="BRD", skill_id="business-requirements"),
            WorkflowStepConfig(id="gen", type=StepType.SKILL, label="G", skill_id="general"),
        ],
        edges=[
            WorkflowEdge(id="e1", from_step="route", to_step="brd", label="business-requirements"),
            WorkflowEdge(id="e2", from_step="route", to_step="gen", label="default"),
        ],
    )
    assert next_step_id(t, "route", "code-analysis") == "gen"


def test_resolve_routing_skill_id():
    ctx = SimpleNamespace(
        routing=RoutingDecision(
            primary_skill="test-case-design",
            artifact_type=ArtifactType.TEST_CASE_PACK,
            complexity="low",
            confidence=0.8,
            verifier_rubric_id="rubric_test-case-design",
            requires_planning=False,
        )
    )
    step = WorkflowStepConfig(id="r", type=StepType.SKILL, label="Refine", skill_id="$routing")
    assert resolve_skill_id(step, ctx) == "test-case-design"
    step2 = WorkflowStepConfig(id="b", type=StepType.SKILL, label="BRD", skill_id="business-requirements")
    assert resolve_skill_id(step2, ctx) == "business-requirements"


def test_system_requirements_template_routes_request_changes_to_refine():
    """Regression: REQUEST_CHANGES must refine, not silently follow approve→publish."""
    from src.orchestrator.workflow_config.store import get_template

    template = get_template("generate-system-requirements")
    assert template is not None
    assert next_step_id(template, "step-approval", "approve") == "step-publish"
    assert next_step_id(template, "step-approval", "request_changes") == "step-refine"
    assert next_step_id(template, "step-approval", "reject") is None
