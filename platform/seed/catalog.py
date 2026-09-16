"""Seed catalog for AI Agent Platform Control Plane entities."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid5, UUID

from src.platform.domain.models import (
    ActivityItem,
    AdaptiveZone,
    ApprovalRecord,
    ArtifactBlueprint,
    ArtifactFacetStatus,
    AuditEvent,
    EvidenceRecord,
    Execution,
    ExecutionContractTemplate,
    ExecutionSummary,
    FacetDefinition,
    MCPIntegrationSummary,
    ModelProfile,
    OperatorDefinition,
    OperatorRunRecord,
    OverviewPayload,
    PlatformEvent,
    PlatformUser,
    Playbook,
    PolicyPack,
    QueueItem,
    ResourceMetric,
    SystemHealthItem,
)

NS = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _id(name: str) -> UUID:
    return uuid5(NS, name)


SYSTEM_REQUIREMENTS_FACETS = [
    FacetDefinition(key="stakeholders", name="Stakeholders"),
    FacetDefinition(key="stakeholder_requirements", name="Stakeholder requirements"),
    FacetDefinition(key="functional_requirements", name="Functional requirements"),
    FacetDefinition(key="constraints", name="Constraints"),
    FacetDefinition(key="adjacent_systems", name="Adjacent systems"),
    FacetDefinition(key="data_model", name="Data model"),
    FacetDefinition(key="integrations", name="Integrations"),
    FacetDefinition(key="security", name="Security"),
    FacetDefinition(key="non_functional_requirements", name="NFR"),
    FacetDefinition(key="open_questions", name="Open questions"),
    FacetDefinition(key="traceability", name="Traceability"),
]


OPERATOR_CATALOG: list[OperatorDefinition] = [
    OperatorDefinition(
        id=_id("op:analyze_external_work_item"),
        key="analyze_external_work_item",
        version="1.2",
        name="Analyze external work item",
        kind="analysis",
        description="Разбор внешней задачи (Jira/Slack) и первичный контекст",
        allowed_capabilities=["tracker.read", "chat.read_thread"],
        risk_level="read",
    ),
    OperatorDefinition(
        id=_id("op:identify_stakeholders"),
        key="identify_stakeholders",
        version="1.0",
        name="Identify stakeholders",
        kind="analysis",
        allowed_capabilities=["tracker.read", "docs.search"],
    ),
    OperatorDefinition(
        id=_id("op:extract_requirements"),
        key="extract_requirements",
        version="2.1",
        name="Extract requirements",
        kind="transformation",
        allowed_capabilities=["tracker.read", "docs.read"],
        risk_level="low",
    ),
    OperatorDefinition(
        id=_id("op:identify_constraints"),
        key="identify_constraints",
        version="1.0",
        name="Identify constraints",
        kind="analysis",
    ),
    OperatorDefinition(
        id=_id("op:identify_adjacent_systems"),
        key="identify_adjacent_systems",
        version="1.1",
        name="Identify adjacent systems",
        kind="analysis",
        allowed_capabilities=["architecture.search", "api_contract.read"],
    ),
    OperatorDefinition(
        id=_id("op:collect_api_contracts"),
        key="collect_api_contracts",
        version="1.1",
        name="Collect API contracts",
        kind="evidence_acquisition",
        allowed_capabilities=["api_contract.read", "repo.search"],
        risk_level="read",
    ),
    OperatorDefinition(
        id=_id("op:analyze_data_impact"),
        key="analyze_data_impact",
        version="1.0",
        name="Analyze data impact",
        kind="analysis",
    ),
    OperatorDefinition(
        id=_id("op:collect_security_context"),
        key="collect_security_context",
        version="1.0",
        name="Collect security context",
        kind="evidence_acquisition",
        risk_level="low",
    ),
    OperatorDefinition(
        id=_id("op:validate_requirements"),
        key="validate_requirements",
        version="1.3",
        name="Validate requirements",
        kind="validation",
        risk_level="low",
    ),
    OperatorDefinition(
        id=_id("op:render_system_requirements"),
        key="render_system_requirements",
        version="1.0",
        name="Render system requirements",
        kind="transformation",
        side_effects="draft",
    ),
    OperatorDefinition(
        id=_id("op:request_human_approval"),
        key="request_human_approval",
        version="1.0",
        name="Request human approval",
        kind="approval",
        risk_level="medium",
        side_effects="none",
    ),
    OperatorDefinition(
        id=_id("op:publish_result"),
        key="publish_result",
        version="1.0",
        name="Publish result",
        kind="publication",
        allowed_capabilities=["publisher.publish", "tracker.comment", "chat.post_message"],
        risk_level="high",
        side_effects="publish",
    ),
]


def build_blueprints() -> list[ArtifactBlueprint]:
    now = datetime.utcnow()
    return [
        ArtifactBlueprint(
            id=_id("bp:system-requirements"),
            key="system-requirements",
            name="System Requirements",
            version="1.0",
            status="active",
            facets=SYSTEM_REQUIREMENTS_FACETS,
            allowed_operator_keys=[o.key for o in OPERATOR_CATALOG],
            updated_at=now - timedelta(days=2),
        ),
        ArtifactBlueprint(
            id=_id("bp:business-requirements"),
            key="business-requirements",
            name="Business Requirements",
            version="1.0",
            status="active",
            facets=[
                FacetDefinition(key="goals", name="Goals"),
                FacetDefinition(key="business_rules", name="Business rules"),
                FacetDefinition(key="acceptance_criteria", name="Acceptance criteria"),
            ],
            updated_at=now - timedelta(days=5),
        ),
    ]


def build_playbooks(flow_template_ids: dict[str, str] | None = None) -> list[Playbook]:
    flow_template_ids = flow_template_ids or {}
    now = datetime.utcnow()
    adaptive = AdaptiveZone(
        id="initial_context",
        name="Initial context & discovery",
        allowed_operator_kinds=["analysis", "evidence_acquisition", "transformation"],
        allowed_capabilities=["tracker.read", "docs.search", "docs.read", "repo.search"],
        maximum_tool_calls=15,
        maximum_operator_runs=20,
        side_effect_limit="draft",
    )
    return [
        Playbook(
            id=_id("pb:system-requirements-standard"),
            key="system-requirements-standard",
            version="3.2",
            name="System Requirements (Standard)",
            description="Стандартный playbook генерации SRS",
            artifact_blueprint_key="system-requirements",
            artifact_blueprint_version="1.0",
            status="active",
            required_outcomes=[
                "stakeholders_confirmed",
                "functional_requirements_partial",
                "security_reviewed",
            ],
            adaptive_zones=[adaptive],
            approvals=[{"type": "architecture_review", "role": "ComplianceApprover"}],
            publication_rules={"targets": ["jira_comment", "confluence"]},
            flow_template_id=flow_template_ids.get("system-requirements"),
            updated_at=now - timedelta(hours=6),
        ),
        Playbook(
            id=_id("pb:system-requirements-arch-review"),
            key="system-requirements-arch-review",
            version="2.0",
            name="System Requirements + Architecture Review",
            description="SRS с обязательным architecture review gate",
            artifact_blueprint_key="system-requirements",
            status="active",
            adaptive_zones=[adaptive],
            approvals=[
                {"type": "architecture_review", "role": "ComplianceApprover"},
                {"type": "security_review", "role": "PolicyAuthor"},
            ],
            updated_at=now - timedelta(days=1),
        ),
        Playbook(
            id=_id("pb:code-review"),
            key="code-review",
            version="1.4",
            name="Code Review",
            description="Анализ кода и technical review",
            artifact_blueprint_key="business-requirements",
            status="draft",
            updated_at=now - timedelta(days=3),
        ),
        Playbook(
            id=_id("pb:test-design"),
            key="test-design",
            version="1.1",
            name="Test Design",
            description="Проектирование тест-кейсов",
            artifact_blueprint_key="business-requirements",
            status="active",
            updated_at=now - timedelta(days=4),
        ),
    ]


def build_policies() -> list[PolicyPack]:
    now = datetime.utcnow()
    return [
        PolicyPack(
            id=_id("pol:corporate-security"),
            key="corporate-security",
            version="1.0",
            name="Corporate Security Policy",
            authority="corporate",
            enforcement="hard",
            status="active",
            rules=[
                {
                    "id": "no-publish-without-approval",
                    "when": {"eq": ["operator.side_effects", "publish"]},
                    "then": {"require_approval": True},
                },
                {
                    "id": "deny-unknown-mcp",
                    "when": {"neq": ["tool.status", "approved"]},
                    "then": {"deny": True},
                },
            ],
            updated_at=now,
        ),
        PolicyPack(
            id=_id("pol:pci"),
            key="pci-dss",
            version="4.0",
            name="PCI Contract Policy",
            authority="regulatory",
            enforcement="hard",
            status="active",
            rules=[{"id": "mask-pan", "then": {"mask_fields": ["card_number", "cvv"]}}],
            updated_at=now - timedelta(days=10),
        ),
    ]


def build_contract_templates() -> list[ExecutionContractTemplate]:
    now = datetime.utcnow()
    return [
        ExecutionContractTemplate(
            id=_id("ct:default"),
            key="default",
            version="5",
            name="Default Contract",
            description="Базовый контракт исполнения",
            status="active",
            defaults_json={
                "budgets": {"max_tool_calls": 50, "max_llm_tokens": 500_000},
                "stop_conditions": ["no_authorized_progress", "budget_exhausted"],
            },
            updated_at=now,
        ),
        ExecutionContractTemplate(
            id=_id("ct:pci"),
            key="pci",
            version="4",
            name="PCI Contract",
            description="Регуляторный контракт для PCI-контекста",
            status="active",
            defaults_json={"policies": ["pci-dss", "corporate-security"]},
            updated_at=now - timedelta(days=7),
        ),
    ]


def build_integrations() -> list[MCPIntegrationSummary]:
    now = datetime.utcnow()
    return [
        MCPIntegrationSummary(
            key="jira",
            name="Jira",
            version="2.4",
            status="online",
            last_check_at=now - timedelta(minutes=2),
            tool_count=3,
            description="Корпоративный трекер задач — чтение эпиков, комментарии, статусы",
            endpoint="mcp://jira.corp.internal:7443",
            capabilities=["tracker.read", "tracker.comment", "tracker.transition"],
        ),
        MCPIntegrationSummary(
            key="sbertrack",
            name="SberTrack",
            version="1.1",
            status="online",
            last_check_at=now - timedelta(minutes=5),
            tool_count=2,
            description="Внутренний трекер Сбера — work items и связи",
            endpoint="mcp://sbertrack.corp.internal:7443",
            capabilities=["tracker.read", "tracker.search"],
        ),
        MCPIntegrationSummary(
            key="slack",
            name="Slack",
            version="3.0",
            status="online",
            last_check_at=now - timedelta(minutes=1),
            tool_count=1,
            description="Корпоративный чат — треды, упоминания, постинг",
            endpoint="mcp://slack-gateway.corp.internal:7443",
            capabilities=["chat.read_thread", "chat.post_message"],
        ),
        MCPIntegrationSummary(
            key="confluence",
            name="Confluence",
            version="1.8",
            status="degraded",
            last_check_at=now - timedelta(minutes=12),
            tool_count=2,
            description="База знаний — страницы, поиск, публикация черновиков",
            endpoint="mcp://confluence.corp.internal:7443",
            capabilities=["docs.read", "docs.search", "publisher.publish"],
        ),
    ]


def build_models() -> list[ModelProfile]:
    now = datetime.utcnow()
    return [
        ModelProfile(
            id=_id("model:lm-studio-local"),
            key="lm-studio-local",
            name="LM Studio (локальный)",
            description="Локальный inference через LM Studio для разработки и отладки операторов",
            provider="lm_studio",
            model_id="qwen2.5-14b-instruct",
            temperature=0.15,
            max_tokens=8192,
            prompt_system="Ты — корпоративный AI-ассистент платформы агентов. Отвечай на русском.",
            status="active",
            updated_at=now - timedelta(days=1),
        ),
        ModelProfile(
            id=_id("model:gigachat-prod"),
            key="gigachat-prod",
            name="GigaChat Production",
            description="Корпоративная LLM для production-исполнений с PCI-контуром",
            provider="gigachat",
            model_id="GigaChat-Pro",
            temperature=0.2,
            max_tokens=4096,
            prompt_system="Следуй политикам corporate-security и pci-dss.",
            status="active",
            updated_at=now - timedelta(hours=8),
        ),
        ModelProfile(
            id=_id("model:qwen-analyst"),
            key="qwen-analyst",
            name="Qwen Analyst",
            description="Модель для аналитических операторов и извлечения требований",
            provider="qwen",
            model_id="qwen2.5-72b-instruct",
            temperature=0.25,
            max_tokens=16384,
            status="active",
            updated_at=now - timedelta(days=3),
        ),
    ]


def build_users() -> list[PlatformUser]:
    now = datetime.utcnow()
    return [
        PlatformUser(
            id=_id("user:admin"),
            username="a.ivanov",
            display_name="Алексей Иванов",
            email="a.ivanov@corp.internal",
            roles=["PlatformAdmin", "ExecutionController"],
            updated_at=now - timedelta(days=30),
        ),
        PlatformUser(
            id=_id("user:designer"),
            username="m.petrova",
            display_name="Мария Петрова",
            email="m.petrova@corp.internal",
            roles=["ProcessDesigner", "OperatorAuthor"],
            updated_at=now - timedelta(days=14),
        ),
        PlatformUser(
            id=_id("user:policy"),
            username="d.sokolov",
            display_name="Дмитрий Соколов",
            email="d.sokolov@corp.internal",
            roles=["PolicyAuthor", "ComplianceApprover"],
            updated_at=now - timedelta(days=7),
        ),
        PlatformUser(
            id=_id("user:integration"),
            username="e.kuznetsova",
            display_name="Елена Кузнецова",
            email="e.kuznetsova@corp.internal",
            roles=["IntegrationAdmin"],
            updated_at=now - timedelta(days=5),
        ),
        PlatformUser(
            id=_id("user:viewer"),
            username="s.volkov",
            display_name="Сергей Волков",
            email="s.volkov@corp.internal",
            roles=["ExecutionViewer", "Approver"],
            updated_at=now - timedelta(days=2),
        ),
    ]


def _facet_statuses(
    overrides: dict[str, tuple[str, str]] | None = None,
) -> list[ArtifactFacetStatus]:
    overrides = overrides or {}
    result: list[ArtifactFacetStatus] = []
    for facet in SYSTEM_REQUIREMENTS_FACETS:
        status, summary = overrides.get(facet.key, ("unknown", ""))
        result.append(ArtifactFacetStatus(key=facet.key, status=status, summary=summary))
    return result


def _default_contract_summary() -> dict[str, Any]:
    return {
        "template_key": "default",
        "policies": ["corporate-security"],
        "budgets": {"max_tool_calls": 50, "max_llm_tokens": 500_000},
        "model_profile_key": "gigachat-prod",
    }


def build_executions() -> list[Execution]:
    now = datetime.utcnow()

    exec_running = Execution(
        id="exec-2026-000145",
        external_source="jira",
        external_work_item_id="PAY-8821",
        external_work_item_url="https://jira.corp.internal/browse/PAY-8821",
        playbook_key="system-requirements-standard",
        playbook_name="System Requirements",
        playbook_version="3.2",
        status="running",
        contract_version=1,
        contract_summary=_default_contract_summary(),
        current_operator_key="extract_requirements",
        next_proposed_action="identify_adjacent_systems",
        reason="Извлечение функциональных требований из эпика PAY-8821",
        budget_usage={"tool_calls": 18, "max_tool_calls": 50, "llm_tokens": 124_500, "max_llm_tokens": 500_000},
        artifact_facets=_facet_statuses({
            "stakeholders": ("confirmed", "5 заинтересованных сторон подтверждены"),
            "stakeholder_requirements": ("supported", "12 требований из Jira"),
            "functional_requirements": ("partial", "8 из ~15 требований извлечено"),
            "constraints": ("partial", "Регуляторные ограничения PCI"),
            "integrations": ("unknown", ""),
        }),
        open_questions=["Нужна ли интеграция с антифрод-сервисом?"],
        operator_runs=[
            OperatorRunRecord(
                id="run-145-01",
                operator_key="analyze_external_work_item",
                status="completed",
                started_at=now - timedelta(minutes=11),
                finished_at=now - timedelta(minutes=10, seconds=20),
                summary="Эпик PAY-8821: платёжный шлюз v2",
            ),
            OperatorRunRecord(
                id="run-145-02",
                operator_key="identify_stakeholders",
                status="completed",
                started_at=now - timedelta(minutes=10),
                finished_at=now - timedelta(minutes=8, seconds=40),
                summary="Product Owner, Архитектор, Security Lead",
            ),
            OperatorRunRecord(
                id="run-145-03",
                operator_key="extract_requirements",
                status="running",
                started_at=now - timedelta(minutes=4),
                summary="Извлечение FR из описания и комментариев",
            ),
        ],
        evidence=[
            EvidenceRecord(
                id="ev-145-01",
                source_type="jira",
                source_ref="PAY-8821",
                trust_class="A",
                summary="Описание эпика и acceptance criteria",
                retrieved_at=now - timedelta(minutes=11),
            ),
            EvidenceRecord(
                id="ev-145-02",
                source_type="confluence",
                source_ref="PAGE-3201",
                trust_class="B",
                summary="Архитектурный контекст платёжного контура",
                retrieved_at=now - timedelta(minutes=9),
            ),
        ],
        plan=[
            {"step": 1, "operator_key": "analyze_external_work_item", "status": "done"},
            {"step": 2, "operator_key": "identify_stakeholders", "status": "done"},
            {"step": 3, "operator_key": "extract_requirements", "status": "running"},
            {"step": 4, "operator_key": "identify_adjacent_systems", "status": "pending"},
            {"step": 5, "operator_key": "validate_requirements", "status": "pending"},
        ],
        audit_trail=[
            {"at": (now - timedelta(minutes=12)).isoformat(), "event": "execution.started", "actor": "system"},
            {"at": (now - timedelta(minutes=4)).isoformat(), "event": "operator.started", "operator": "extract_requirements"},
        ],
        started_at=now - timedelta(minutes=12),
        updated_at=now - timedelta(minutes=1),
    )

    exec_waiting = Execution(
        id="exec-2026-000144",
        external_source="slack",
        external_work_item_id="C0ABCD:1710",
        external_work_item_url="https://slack.corp.internal/archives/C0ABCD/p1710",
        playbook_key="system-requirements-arch-review",
        playbook_name="Architecture Review",
        playbook_version="2.0",
        status="waiting_approval",
        contract_version=2,
        contract_summary={
            **_default_contract_summary(),
            "template_key": "pci",
            "policies": ["pci-dss", "corporate-security"],
        },
        reason="Ожидание architecture review перед публикацией черновика SRS",
        budget_usage={"tool_calls": 42, "max_tool_calls": 50, "llm_tokens": 380_000, "max_llm_tokens": 500_000},
        artifact_facets=_facet_statuses({
            "stakeholders": ("confirmed", "Согласованы на встрече 14.07"),
            "functional_requirements": ("confirmed", "18 требований валидированы"),
            "security": ("supported", "Чеклист PCI пройден"),
            "integrations": ("confirmed", "3 смежные системы"),
            "open_questions": ("partial", "1 открытый вопрос по SLA"),
        }),
        approvals=[
            ApprovalRecord(
                id="apr-144-01",
                type="architecture_review",
                status="pending",
                requested_role="ComplianceApprover",
                subject="Публикация черновика SRS в Confluence (PAGE-4418)",
            ),
        ],
        operator_runs=[
            OperatorRunRecord(
                id="run-144-01",
                operator_key="analyze_external_work_item",
                status="completed",
                started_at=now - timedelta(minutes=27),
                finished_at=now - timedelta(minutes=26),
                summary="Тред Slack: рефакторинг API шлюза",
            ),
            OperatorRunRecord(
                id="run-144-02",
                operator_key="render_system_requirements",
                status="completed",
                started_at=now - timedelta(minutes=8),
                finished_at=now - timedelta(minutes=5),
                summary="Черновик SRS сформирован",
            ),
            OperatorRunRecord(
                id="run-144-03",
                operator_key="request_human_approval",
                status="completed",
                started_at=now - timedelta(minutes=5),
                finished_at=now - timedelta(minutes=4, seconds=30),
                summary="Запрошено согласование ComplianceApprover",
            ),
        ],
        evidence=[
            EvidenceRecord(
                id="ev-144-01",
                source_type="slack",
                source_ref="C0ABCD:1710",
                trust_class="B",
                summary="Обсуждение архитектурных изменений",
                retrieved_at=now - timedelta(minutes=27),
            ),
        ],
        plan=[
            {"step": 1, "operator_key": "analyze_external_work_item", "status": "done"},
            {"step": 2, "operator_key": "render_system_requirements", "status": "done"},
            {"step": 3, "operator_key": "request_human_approval", "status": "done"},
            {"step": 4, "operator_key": "publish_result", "status": "blocked", "reason": "approval_pending"},
        ],
        audit_trail=[
            {"at": (now - timedelta(minutes=28)).isoformat(), "event": "execution.started", "actor": "system"},
            {"at": (now - timedelta(minutes=4)).isoformat(), "event": "approval.requested", "type": "architecture_review"},
        ],
        started_at=now - timedelta(minutes=28),
        updated_at=now - timedelta(minutes=3),
    )

    exec_completed_recent = Execution(
        id="exec-2026-000143",
        external_source="jira",
        external_work_item_id="PAY-8799",
        external_work_item_url="https://jira.corp.internal/browse/PAY-8799",
        playbook_key="code-review",
        playbook_name="Code Review",
        playbook_version="1.4",
        status="completed",
        contract_summary=_default_contract_summary(),
        reason="Code review завершён, комментарий опубликован в Jira",
        budget_usage={"tool_calls": 24, "max_tool_calls": 50, "llm_tokens": 210_000, "max_llm_tokens": 500_000},
        artifact_facets=[
            ArtifactFacetStatus(key="goals", status="confirmed", summary="Цели ревью достигнуты"),
            ArtifactFacetStatus(key="business_rules", status="supported", summary="5 правил проверены"),
            ArtifactFacetStatus(key="acceptance_criteria", status="confirmed", summary="Критерии приёмки согласованы"),
        ],
        operator_runs=[
            OperatorRunRecord(
                id="run-143-01",
                operator_key="analyze_external_work_item",
                status="completed",
                started_at=now - timedelta(hours=1, minutes=5),
                finished_at=now - timedelta(hours=1, minutes=2),
                summary="PR #412: рефакторинг валидации",
            ),
            OperatorRunRecord(
                id="run-143-02",
                operator_key="publish_result",
                status="completed",
                started_at=now - timedelta(minutes=55),
                finished_at=now - timedelta(minutes=52),
                summary="Комментарий опубликован в Jira PAY-8799",
            ),
        ],
        evidence=[
            EvidenceRecord(
                id="ev-143-01",
                source_type="repo",
                source_ref="payments-service#412",
                trust_class="A",
                summary="Diff pull request #412",
                retrieved_at=now - timedelta(hours=1, minutes=4),
            ),
        ],
        plan=[{"step": 1, "operator_key": "analyze_external_work_item", "status": "done"}],
        audit_trail=[
            {"at": (now - timedelta(hours=1)).isoformat(), "event": "execution.completed", "actor": "system"},
        ],
        started_at=now - timedelta(hours=1),
        updated_at=now - timedelta(minutes=52),
    )

    exec_failed = Execution(
        id="exec-2026-000142",
        external_source="confluence",
        external_work_item_id="PAGE-4412",
        external_work_item_url="https://confluence.corp.internal/pages/PAGE-4412",
        playbook_key="test-design",
        playbook_name="Test Design",
        playbook_version="1.1",
        status="failed",
        contract_summary=_default_contract_summary(),
        reason="MCP Confluence timeout при чтении PAGE-4412 (3 попытки)",
        budget_usage={"tool_calls": 12, "max_tool_calls": 50, "llm_tokens": 45_000, "max_llm_tokens": 500_000},
        artifact_facets=[
            ArtifactFacetStatus(key="goals", status="partial", summary="Цели частично определены"),
            ArtifactFacetStatus(key="acceptance_criteria", status="unknown", summary=""),
        ],
        conflicts=["Confluence MCP degraded — невозможно получить тестовые сценарии"],
        operator_runs=[
            OperatorRunRecord(
                id="run-142-01",
                operator_key="analyze_external_work_item",
                status="failed",
                started_at=now - timedelta(hours=2, minutes=3),
                finished_at=now - timedelta(hours=2),
                summary="Timeout: confluence.docs.read после 3 retry",
            ),
        ],
        evidence=[],
        plan=[{"step": 1, "operator_key": "analyze_external_work_item", "status": "failed"}],
        audit_trail=[
            {"at": (now - timedelta(hours=2)).isoformat(), "event": "execution.failed", "error": "mcp_timeout"},
        ],
        started_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=2),
    )

    exec_completed_old = Execution(
        id="exec-2026-000141",
        external_source="jira",
        external_work_item_id="PAY-8710",
        external_work_item_url="https://jira.corp.internal/browse/PAY-8710",
        playbook_key="system-requirements-standard",
        playbook_name="System Requirements",
        playbook_version="3.2",
        status="completed",
        contract_summary=_default_contract_summary(),
        reason="SRS опубликован в Confluence и Jira",
        budget_usage={"tool_calls": 47, "max_tool_calls": 50, "llm_tokens": 465_000, "max_llm_tokens": 500_000},
        artifact_facets=_facet_statuses({
            facet.key: ("confirmed", "Завершено")
            for facet in SYSTEM_REQUIREMENTS_FACETS
        }),
        operator_runs=[
            OperatorRunRecord(
                id="run-141-01",
                operator_key="render_system_requirements",
                status="completed",
                started_at=now - timedelta(hours=3, minutes=20),
                finished_at=now - timedelta(hours=3, minutes=10),
                summary="SRS v1.0 сформирован",
            ),
            OperatorRunRecord(
                id="run-141-02",
                operator_key="publish_result",
                status="completed",
                started_at=now - timedelta(hours=3, minutes=8),
                finished_at=now - timedelta(hours=3, minutes=5),
                summary="Опубликовано: Jira PAY-8710 + Confluence PAGE-4390",
            ),
        ],
        evidence=[
            EvidenceRecord(
                id="ev-141-01",
                source_type="jira",
                source_ref="PAY-8710",
                trust_class="A",
                summary="Полное описание эпика",
                retrieved_at=now - timedelta(hours=3, minutes=30),
            ),
        ],
        approvals=[
            ApprovalRecord(
                id="apr-141-01",
                type="architecture_review",
                status="approved",
                requested_role="ComplianceApprover",
                subject="Публикация SRS PAY-8710",
                decision_comment="Согласовано без замечаний",
            ),
        ],
        plan=[
            {"step": 1, "operator_key": "render_system_requirements", "status": "done"},
            {"step": 2, "operator_key": "publish_result", "status": "done"},
        ],
        audit_trail=[
            {"at": (now - timedelta(hours=3)).isoformat(), "event": "execution.completed", "actor": "system"},
        ],
        started_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=3, minutes=5),
    )

    return [exec_running, exec_waiting, exec_completed_recent, exec_failed, exec_completed_old]


def build_activity() -> list[ActivityItem]:
    now = datetime.utcnow()
    return [
        ActivityItem(
            id="act-001",
            occurred_at=now - timedelta(minutes=1),
            execution_id="exec-2026-000145",
            kind="operator.progress",
            message="extract_requirements: извлечено 8 функциональных требований",
            severity="info",
        ),
        ActivityItem(
            id="act-002",
            occurred_at=now - timedelta(minutes=3),
            execution_id="exec-2026-000144",
            kind="approval.requested",
            message="Запрошено согласование architecture_review (ComplianceApprover)",
            severity="warn",
        ),
        ActivityItem(
            id="act-003",
            occurred_at=now - timedelta(minutes=8),
            execution_id="exec-2026-000145",
            kind="evidence.acquired",
            message="Получен контекст из Confluence PAGE-3201 (trust B)",
            severity="info",
        ),
        ActivityItem(
            id="act-004",
            occurred_at=now - timedelta(minutes=52),
            execution_id="exec-2026-000143",
            kind="execution.completed",
            message="Code Review PAY-8799 завершён — комментарий в Jira",
            severity="info",
        ),
        ActivityItem(
            id="act-005",
            occurred_at=now - timedelta(hours=2),
            execution_id="exec-2026-000142",
            kind="execution.failed",
            message="Test Design PAGE-4412: Confluence MCP timeout",
            severity="error",
        ),
        ActivityItem(
            id="act-006",
            occurred_at=now - timedelta(hours=3, minutes=5),
            execution_id="exec-2026-000141",
            kind="publication.done",
            message="SRS PAY-8710 опубликован в Confluence PAGE-4390",
            severity="info",
        ),
        ActivityItem(
            id="act-007",
            occurred_at=now - timedelta(minutes=15),
            execution_id="exec-2026-000145",
            kind="policy.check",
            message="Проверка corporate-security: publish заблокирован до approval",
            severity="info",
        ),
        ActivityItem(
            id="act-008",
            occurred_at=now - timedelta(minutes=20),
            execution_id="",
            kind="integration.degraded",
            message="Confluence MCP: latency 4.2s (порог 2s)",
            severity="warn",
        ),
    ]


def build_queue() -> list[QueueItem]:
    now = datetime.utcnow()
    return [
        QueueItem(
            id="q-001",
            execution_id="exec-2026-000146",
            external_work_item_id="PAY-8830",
            playbook_name="System Requirements",
            priority=80,
            status="queued",
            enqueued_at=now - timedelta(minutes=2),
            eta_seconds=45,
        ),
        QueueItem(
            id="q-002",
            execution_id="exec-2026-000147",
            external_work_item_id="C0ABCD:1722",
            playbook_name="Architecture Review",
            priority=60,
            status="queued",
            enqueued_at=now - timedelta(minutes=5),
            eta_seconds=120,
        ),
        QueueItem(
            id="q-003",
            execution_id="exec-2026-000148",
            external_work_item_id="PAY-8835",
            playbook_name="Test Design",
            priority=40,
            status="delayed",
            enqueued_at=now - timedelta(minutes=10),
            eta_seconds=600,
        ),
        QueueItem(
            id="q-004",
            execution_id="exec-2026-000149",
            external_work_item_id="PAGE-4420",
            playbook_name="Code Review",
            priority=70,
            status="claimed",
            enqueued_at=now - timedelta(minutes=1),
            eta_seconds=30,
        ),
    ]


def build_events() -> list[PlatformEvent]:
    now = datetime.utcnow()
    return [
        PlatformEvent(
            id="evt-kafka-001",
            event_type="platform.execution.started",
            occurred_at=now - timedelta(minutes=12),
            correlation_id="exec-2026-000145",
            producer="temporal-worker-03",
            payload={
                "execution_id": "exec-2026-000145",
                "playbook_key": "system-requirements-standard",
                "external_source": "jira",
                "external_work_item_id": "PAY-8821",
            },
        ),
        PlatformEvent(
            id="evt-kafka-002",
            event_type="platform.operator.completed",
            occurred_at=now - timedelta(minutes=8, seconds=40),
            correlation_id="exec-2026-000145",
            producer="operator-runtime",
            payload={
                "execution_id": "exec-2026-000145",
                "operator_key": "identify_stakeholders",
                "run_id": "run-145-02",
                "duration_ms": 80400,
            },
        ),
        PlatformEvent(
            id="evt-kafka-003",
            event_type="platform.approval.requested",
            occurred_at=now - timedelta(minutes=4, seconds=30),
            correlation_id="exec-2026-000144",
            producer="approval-service",
            payload={
                "execution_id": "exec-2026-000144",
                "approval_id": "apr-144-01",
                "type": "architecture_review",
                "requested_role": "ComplianceApprover",
            },
        ),
        PlatformEvent(
            id="evt-kafka-004",
            event_type="platform.execution.failed",
            occurred_at=now - timedelta(hours=2),
            correlation_id="exec-2026-000142",
            producer="temporal-worker-07",
            payload={
                "execution_id": "exec-2026-000142",
                "reason": "mcp_timeout",
                "integration_key": "confluence",
            },
        ),
        PlatformEvent(
            id="evt-kafka-005",
            event_type="platform.execution.completed",
            occurred_at=now - timedelta(hours=3, minutes=5),
            correlation_id="exec-2026-000141",
            producer="temporal-worker-01",
            payload={
                "execution_id": "exec-2026-000141",
                "playbook_key": "system-requirements-standard",
                "publication_targets": ["jira_comment", "confluence"],
            },
        ),
        PlatformEvent(
            id="evt-kafka-006",
            event_type="platform.integration.health_changed",
            occurred_at=now - timedelta(minutes=12),
            correlation_id="integration:confluence",
            producer="mcp-gateway",
            payload={
                "integration_key": "confluence",
                "previous_status": "online",
                "current_status": "degraded",
                "latency_p95_ms": 4200,
            },
        ),
        PlatformEvent(
            id="evt-kafka-007",
            event_type="platform.queue.enqueued",
            occurred_at=now - timedelta(minutes=2),
            correlation_id="exec-2026-000146",
            producer="ingress-api",
            payload={
                "queue_item_id": "q-001",
                "execution_id": "exec-2026-000146",
                "priority": 80,
            },
        ),
    ]


def seed_audit_events() -> list[AuditEvent]:
    now = datetime.utcnow()
    return [
        AuditEvent(
            id=_id("audit:seed-01"),
            occurred_at=now - timedelta(days=30),
            actor="a.ivanov",
            action="bootstrap",
            entity_type="platform",
            entity_id="control-plane",
            summary="Первичная инициализация платформы и seed-каталога",
        ),
        AuditEvent(
            id=_id("audit:seed-02"),
            occurred_at=now - timedelta(days=14),
            actor="m.petrova",
            action="publish",
            entity_type="playbook",
            entity_id="system-requirements-standard",
            summary="Опубликован playbook System Requirements v3.2",
        ),
        AuditEvent(
            id=_id("audit:seed-03"),
            occurred_at=now - timedelta(days=10),
            actor="d.sokolov",
            action="activate",
            entity_type="policy",
            entity_id="pci-dss",
            summary="Активирована политика PCI DSS v4.0 (four-eyes)",
            details={"approver": "a.ivanov"},
        ),
        AuditEvent(
            id=_id("audit:seed-04"),
            occurred_at=now - timedelta(days=5),
            actor="e.kuznetsova",
            action="save",
            entity_type="integration",
            entity_id="confluence",
            summary="Обновлена конфигурация MCP Confluence",
        ),
        AuditEvent(
            id=_id("audit:seed-05"),
            occurred_at=now - timedelta(hours=3, minutes=5),
            actor="system",
            action="complete",
            entity_type="execution",
            entity_id="exec-2026-000141",
            summary="Исполнение PAY-8710 завершено успешно",
        ),
        AuditEvent(
            id=_id("audit:seed-06"),
            occurred_at=now - timedelta(minutes=4),
            actor="system",
            action="request_approval",
            entity_type="execution",
            entity_id="exec-2026-000144",
            summary="Запрошено architecture review для Slack C0ABCD:1710",
            details={"approval_id": "apr-144-01", "role": "ComplianceApprover"},
        ),
    ]


def build_recent_executions() -> list[ExecutionSummary]:
    now = datetime.utcnow()
    return [
        ExecutionSummary(
            id="exec-2026-000145",
            external_source="jira",
            external_work_item_id="PAY-8821",
            playbook_name="System Requirements",
            status="running",
            started_at=now - timedelta(minutes=12),
            current_operator_key="extract_requirements",
        ),
        ExecutionSummary(
            id="exec-2026-000144",
            external_source="slack",
            external_work_item_id="C0ABCD:1710",
            playbook_name="Architecture Review",
            status="waiting_approval",
            started_at=now - timedelta(minutes=28),
        ),
        ExecutionSummary(
            id="exec-2026-000143",
            external_source="jira",
            external_work_item_id="PAY-8799",
            playbook_name="Code Review",
            status="completed",
            started_at=now - timedelta(hours=1),
        ),
        ExecutionSummary(
            id="exec-2026-000142",
            external_source="confluence",
            external_work_item_id="PAGE-4412",
            playbook_name="Test Design",
            status="failed",
            started_at=now - timedelta(hours=2),
        ),
        ExecutionSummary(
            id="exec-2026-000141",
            external_source="jira",
            external_work_item_id="PAY-8710",
            playbook_name="System Requirements",
            status="completed",
            started_at=now - timedelta(hours=3),
        ),
    ]


def build_system_health() -> list[SystemHealthItem]:
    return [
        SystemHealthItem(
            key="temporal",
            label="Runtime workers (Temporal)",
            status="ok",
            detail="12/12 active",
        ),
        SystemHealthItem(
            key="mcp_gateway",
            label="MCP Gateway",
            status="warn",
            detail="21/23 online",
        ),
        SystemHealthItem(
            key="kafka",
            label="Kafka clusters",
            status="ok",
            detail="3/3 online",
        ),
        SystemHealthItem(
            key="integrations",
            label="Integrations",
            status="warn",
            detail="7/8 active",
        ),
        SystemHealthItem(
            key="storage",
            label="Storages",
            status="ok",
            detail="Healthy",
        ),
    ]


def build_resource_usage() -> list[ResourceMetric]:
    return [
        ResourceMetric(
            key="executions",
            label="Executions",
            value="1,247",
            delta_pct=12.3,
            series=[40, 48, 45, 52, 60, 58, 72, 80, 76, 90],
        ),
        ResourceMetric(
            key="llm_tokens",
            label="LLM Tokens",
            value="24.8M",
            delta_pct=8.7,
            series=[30, 35, 40, 38, 50, 55, 48, 62, 70, 68],
        ),
        ResourceMetric(
            key="tool_calls",
            label="Tool Calls",
            value="8,932",
            delta_pct=15.1,
            series=[20, 28, 26, 40, 35, 48, 52, 60, 58, 74],
        ),
        ResourceMetric(
            key="errors",
            label="Errors",
            value="23",
            delta_pct=-4.2,
            series=[12, 14, 11, 10, 9, 11, 8, 7, 8, 6],
        ),
    ]


def build_overview(flow_template_ids: dict[str, str] | None = None) -> OverviewPayload:
    from src.platform.seed.governed_catalog import (
        build_agents,
        build_controls,
        build_knowledge_spaces,
        build_skills,
    )

    return OverviewPayload(
        agents=build_agents(),
        playbooks=[],
        skills=[item.model_dump(mode="json") for item in build_skills()],
        controls=build_controls(),
        knowledge_spaces=build_knowledge_spaces(),
        operators=list(OPERATOR_CATALOG),
        blueprints=build_blueprints(),
        policies=build_policies(),
        contract_templates=build_contract_templates(),
        integrations=build_integrations(),
        recent_executions=build_recent_executions(),
        system_health=build_system_health(),
        resource_usage=build_resource_usage(),
        waiting_approvals_count=1,
    )


def dump_seed_json(path: Path) -> dict[str, Any]:
    payload = build_overview()
    data = payload.model_dump(mode="json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        __import__("json").dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return data
