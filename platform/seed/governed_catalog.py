"""Seed catalog for the governed PDLC configuration core."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

from src.platform.domain.models import (
    Agent,
    CapabilityDef,
    ControlPack,
    Execution,
    KnowledgeSpace,
    PlaybookDefinition,
    RuleSet,
    RuntimeProfile,
    SkillImplementation,
    SkillInterface,
)
from src.platform.seed.catalog import build_executions as build_legacy_executions

NS = UUID("4d28d4b5-cb06-4c7c-9aba-040c8f7b5579")


def _id(kind: str, key: str) -> UUID:
    return uuid5(NS, f"{kind}:{key}")


INTERFACE_SPECS: list[tuple[str, str, list[str]]] = [
    ("research.problem.investigate@1", "Investigate problem", ["work_item.read", "context.search", "context.read"]),
    ("analysis.problem.understand@1", "Understand problem", ["context.read"]),
    ("analysis.stakeholders.identify@1", "Identify stakeholders", ["work_item.read", "context.search"]),
    ("analysis.business_requirements.generate@1", "Generate business requirements", ["context.read", "chat.read_thread", "artifact.patch", "chat.reply"]),
    ("analysis.system_requirements.generate@1", "Generate system requirements", ["context.read", "chat.read_thread", "artifact.patch", "chat.reply"]),
    ("analysis.code_analysis.generate@1", "Generate code analysis report", ["context.read", "repo.search", "repo.read_file"]),
    ("analysis.requirements.improve@1", "Improve requirements", ["artifact.read", "artifact.patch"]),
    ("analysis.requirements.validate@2", "Validate requirements", ["artifact.read", "context.read"]),
    ("analysis.data_impact.analyze@1", "Analyze data impact", ["context.search", "artifact.patch"]),
    ("analysis.integration_impact.analyze@1", "Analyze integration impact", ["context.search", "context.read"]),
    ("architecture.solution.design@1", "Design solution", ["repo.read", "artifact.patch"]),
    ("architecture.review@1", "Review architecture", ["artifact.read", "repo.read"]),
    ("development.change.plan@1", "Plan code change", ["repo.search", "repo.read"]),
    ("development.code.implement@1", "Implement code", ["repo.read", "repo.propose_patch"]),
    ("development.code.review@1", "Review code", ["repo.read", "artifact.patch"]),
    ("testing.conditions.derive@1", "Derive test conditions", ["artifact.read", "artifact.patch"]),
    ("testing.cases.generate@1", "Generate test cases", ["artifact.read", "artifact.patch"]),
    ("testing.tests.execute@1", "Execute tests", ["tests.run"]),
    ("testing.results.analyze@1", "Analyze test results", ["tests.read_results", "artifact.patch"]),
    ("devops.release.plan@1", "Plan release", ["artifact.read", "artifact.patch"]),
    ("devops.deployment.validate@1", "Validate deployment", ["ci.read", "telemetry.query"]),
    ("operations.incident.triage@1", "Triage incident", ["logs.search", "telemetry.query"]),
    ("operations.root_cause.analyze@1", "Analyze root cause", ["logs.search", "context.search"]),
    ("artifact.render@1", "Render artifact", ["artifact.read", "artifact.render"]),
    ("routing.classify@1", "Classify Task", []),
]


def build_skill_interfaces() -> list[SkillInterface]:
    from src.platform.contracts.seed import default_interface_contracts

    schema = {"type": "object", "additionalProperties": True}
    return [
        SkillInterface(
            id=_id("interface", key),
            key=key,
            name=name,
            version=key.rsplit("@", 1)[-1],
            input_contract_key=default_interface_contracts(key)[0],
            output_contract_key=default_interface_contracts(key)[1],
            input_schema=schema,
            output_schema=schema,
            required_capabilities=capabilities,
            source="platform",
        )
        for key, name, capabilities in INTERFACE_SPECS
    ]


SKILL_MAPPINGS = [
    ("analyze_external_work_item", "analysis.problem.understand@1"),
    ("identify_stakeholders", "analysis.stakeholders.identify@1"),
    ("extract_requirements", "analysis.system_requirements.generate@1"),
    ("identify_constraints", "analysis.requirements.improve@1"),
    ("identify_adjacent_systems", "analysis.integration_impact.analyze@1"),
    ("collect_api_contracts", "analysis.integration_impact.analyze@1"),
    ("analyze_data_impact", "analysis.data_impact.analyze@1"),
    ("collect_security_context", "architecture.review@1"),
    ("validate_requirements", "analysis.requirements.validate@2"),
    ("render_system_requirements", "artifact.render@1"),
    ("request_human_approval", "architecture.review@1"),
    ("publish_result", "artifact.render@1"),
    ("generate_business_requirements", "analysis.business_requirements.generate@1"),
    ("review_code_change", "development.code.review@1"),
    ("generate_test_cases", "testing.cases.generate@1"),
]


def build_skills() -> list[SkillImplementation]:
    capabilities = {i.key: i.required_capabilities for i in build_skill_interfaces()}
    return [
        SkillImplementation(
            id=_id("skill", legacy_key),
            key=f"core/{legacy_key}",
            interface_key=interface_key,
            name=legacy_key.replace("_", " ").title(),
            version="1.0",
            status="active",
            source="system",
            owner="platform",
            skill_md=(
                f"# {legacy_key.replace('_', ' ').title()}\n\n"
                "Perform one bounded cognitive action using only declared platform capabilities. "
                "Return structured output with evidence references and explicit assumptions."
            ),
            manifest={"legacy_operator_key": legacy_key, "implements": interface_key},
            allowed_capabilities=capabilities[interface_key],
        )
        for legacy_key, interface_key in SKILL_MAPPINGS
    ]


CONTROL_KEYS = [
    "evidence-traceability",
    "unsupported-assumptions",
    "publication-approval",
    "audit-retention",
]


def build_controls() -> list[ControlPack]:
    return [
        ControlPack(
            id=_id("control", "evidence-traceability"),
            key="evidence-traceability",
            name="Evidence & Traceability",
            authority="corporate",
            enforcement="hard",
            status="active",
            applicability_rule={"exists": "execution.id"},
            locked_steps=[{"key": "validate-evidence", "phase": "pre_handoff", "required": True}],
            rules=[{"id": "evidence-required", "then": {"require_evidence": True}}],
        ),
        ControlPack(
            id=_id("control", "unsupported-assumptions"),
            key="unsupported-assumptions",
            name="Unsupported Assumptions",
            authority="corporate",
            enforcement="hard",
            status="active",
            applicability_rule={"exists": "execution.id"},
            locked_steps=[{"key": "validate-assumptions", "phase": "post_skill", "required": True}],
            rules=[{"id": "flag-unsupported", "then": {"block_unsupported_assumptions": True}}],
        ),
        ControlPack(
            id=_id("control", "publication-approval"),
            key="publication-approval",
            name="Publication Approval",
            authority="corporate",
            enforcement="controlled",
            status="active",
            applicability_rule={"eq": ["action.operation", "publish"]},
            locked_steps=[{"key": "publication-approval", "phase": "pre_publication", "required": True}],
            rules=[{"id": "approval-before-publish", "then": {"require_approval": True}}],
        ),
        ControlPack(
            id=_id("control", "audit-retention"),
            key="audit-retention",
            name="Audit Retention",
            authority="regulatory",
            enforcement="hard",
            status="active",
            applicability_rule={"exists": "execution.id"},
            locked_steps=[{"key": "write-audit-record", "phase": "post_skill", "required": True}],
            rules=[{"id": "retain-audit", "then": {"retention_days": 2555}}],
        ),
    ]


def _playbook(
    key: str,
    family: str,
    name: str,
    slots: list[tuple[str, str, str]],
) -> PlaybookDefinition:
    locked = [
        {"id": "determine-controls", "type": "locked_step", "label": "Determine Applicable Controls", "locked": True},
        {"id": "validate-evidence", "type": "locked_step", "label": "Evidence & Traceability Validation", "locked": True},
        {"id": "validate-assumptions", "type": "locked_step", "label": "Unsupported Assumptions Validation", "locked": True},
        {"id": "write-audit-record", "type": "locked_step", "label": "Write Audit Record", "locked": True},
        {"id": "publication-approval", "type": "human_checkpoint", "label": "Publication Approval", "locked": True},
    ]
    skill_slots = [
        {
            "key": slot_key,
            "title": title,
            "interface_ref": interface,
            "default_skill_ref": next(
                (f"core/{legacy}" for legacy, ref in SKILL_MAPPINGS if ref == interface), ""
            ),
            "customization_mode": "replaceable",
        }
        for slot_key, title, interface in slots
    ]
    slot_nodes = [
        {"id": slot["key"], "type": "skill_slot", "label": slot["title"], "skill_slot": slot["key"]}
        for slot in skill_slots
    ]
    nodes = [locked[0], *slot_nodes, *locked[1:]]
    edges = [{"source": nodes[i]["id"], "target": nodes[i + 1]["id"]} for i in range(len(nodes) - 1)]
    return PlaybookDefinition(
        id=_id("playbook", key),
        key=key,
        version="1.0",
        family=family,
        name=name,
        description=f"Governed {name} playbook with locked control spine and typed skill slots.",
        status="active",
        entry_contract="CanonicalWorkItem@1",
        exit_contract=f"{name.replace(' ', '')}Artifact@1",
        nodes=nodes,
        edges=edges,
        skill_slots=skill_slots,
        control_pack_keys=CONTROL_KEYS,
        rule_set_keys=["requirements-style-v1"] if "requirements" in key else ["code-style-v1"],
        dor=["work_item_available"],
        dod=["artifact_schema_valid", "evidence_linked", "approval_resolved"],
    )


def build_playbooks() -> list[PlaybookDefinition]:
    return [
        _playbook("system-requirements", "analysis", "System Requirements", [
            ("understand-problem", "Understand Work Item", "analysis.problem.understand@1"),
            ("generate-requirements", "Generate System Requirements", "analysis.system_requirements.generate@1"),
            ("validate-requirements", "Validate Requirements", "analysis.requirements.validate@2"),
            ("render-artifact", "Render Artifact", "artifact.render@1"),
        ]),
        _playbook("business-requirements", "analysis", "Business Requirements", [
            ("understand-problem", "Understand Work Item", "analysis.problem.understand@1"),
            ("generate-requirements", "Generate Business Requirements", "analysis.business_requirements.generate@1"),
            ("validate-requirements", "Validate Requirements", "analysis.requirements.validate@2"),
        ]),
        _playbook("code-review", "development", "Code Review", [
            ("understand-problem", "Understand Change", "analysis.problem.understand@1"),
            ("review-code", "Review Code Change", "development.code.review@1"),
            ("render-artifact", "Render Review", "artifact.render@1"),
        ]),
        _playbook("test-case-generation", "testing", "Test Case Generation", [
            ("derive-conditions", "Derive Test Conditions", "testing.conditions.derive@1"),
            ("generate-cases", "Generate Test Cases", "testing.cases.generate@1"),
            ("render-artifact", "Render Test Cases", "artifact.render@1"),
        ]),
    ]


def build_agents() -> list[Agent]:
    """Legacy seed — kept for read-only migration; prefer build_runtime_profiles()."""
    return [Agent(
        id=_id("agent", "requirements-agent"),
        key="requirements-agent",
        name="Requirements Agent",
        status="active",
        ingress_bindings=[
            {"source": "jira", "mode": "assignment", "enabled": True},
            {"source": "slack", "mode": "mention", "enabled": True},
        ],
        allowed_playbook_keys=["system-requirements", "business-requirements"],
        allowed_flow_keys=["requirements-to-delivery"],
        default_playbook_key="system-requirements",
        skill_bindings=[
            {"interface_key": interface, "skill_key": f"core/{legacy}"}
            for legacy, interface in SKILL_MAPPINGS
            if interface.startswith("analysis.") or interface == "artifact.render@1"
        ],
        knowledge_space_bindings=["corp-engineering", "payments-domain"],
        model_profile_key="gigachat-prod",
        supervision_profile_key="checkpoint",
    )]


def build_runtime_profiles() -> list[RuntimeProfile]:
    """V2 Runtime Profiles — migrated from Agent.model_profile_key + models catalog."""
    return [
        RuntimeProfile(
            id=_id("runtime", "default-gigachat"),
            key="default-gigachat",
            name="Default GigaChat",
            description="Профиль исполнения, мигрированный из requirements-agent",
            provider="gigachat",
            model="GigaChat-Pro",
            fallback_models=["GigaChat"],
            generation_config={"temperature": 0.2, "max_tokens": 8192},
            sandbox_config={"network": "restricted", "filesystem": "workspace"},
            limits_json={
                "max_concurrency": 4,
                "max_retries": 3,
                "max_cost_usd": 25,
                "max_context_tokens": 128000,
                "supervision_profile": "checkpoint",
            },
            secrets_reference="secret://runtime/gigachat",
            region="ru-central",
            status="active",
            migrated_from_agent_key="requirements-agent",
        ),
        RuntimeProfile(
            id=_id("runtime", "local-lm-studio"),
            key="local-lm-studio",
            name="Local LM Studio",
            description="Локальный профиль для разработки",
            provider="lm_studio",
            model="local-model",
            fallback_models=[],
            generation_config={"temperature": 0.1, "max_tokens": 4096},
            sandbox_config={"network": "localhost"},
            limits_json={"max_concurrency": 2, "max_retries": 2},
            secrets_reference="",
            region="local",
            status="active",
        ),
        RuntimeProfile(
            id=_id("runtime", "qwen-cli"),
            key="qwen-cli",
            name="Qwen Code CLI",
            description="Целевой runtime для Skill execution (V2)",
            provider="qwen",
            model="qwen-code",
            fallback_models=["default-gigachat"],
            generation_config={"timeout_seconds": 900},
            sandbox_config={"subprocess": True, "no_shell": True},
            limits_json={"max_concurrency": 2, "max_retries": 1, "max_cost_usd": 50},
            secrets_reference="secret://runtime/qwen",
            region="ru-central",
            status="draft",
        ),
    ]


def build_rules() -> list[RuleSet]:
    return [
        RuleSet(
            id=_id("rule", "requirements-style-v1"),
            key="requirements-style-v1",
            name="Requirements Style v1",
            scope="organization",
            status="active",
            content_md="Use atomic, testable SHALL statements and link every requirement to evidence.",
            structured_rules={"language": "ru", "require_ids": True, "require_acceptance_criteria": True},
        ),
        RuleSet(
            id=_id("rule", "code-style-v1"),
            key="code-style-v1",
            name="Code Style v1",
            scope="organization",
            status="active",
            content_md="Prefer small changes, typed interfaces, and tests for changed behavior.",
            structured_rules={"typed_interfaces": True, "tests_required": True},
        ),
    ]


def build_knowledge_spaces() -> list[KnowledgeSpace]:
    return [
        KnowledgeSpace(
            id=_id("knowledge", "corp-engineering"),
            key="corp-engineering",
            name="Corporate Engineering",
            status="active",
            source_bindings=[
                {"provider": "confluence", "scope": "ENG"},
                {"provider": "git", "scope": "engineering-*"},
            ],
            priorities=[{"provider": "confluence", "priority": 100}, {"provider": "git", "priority": 80}],
            data_classification="internal",
            freshness_hours=168,
        ),
        KnowledgeSpace(
            id=_id("knowledge", "payments-domain"),
            key="payments-domain",
            name="Payments Domain",
            status="active",
            source_bindings=[
                {"provider": "jira", "scope": "PAY"},
                {"provider": "slack", "scope": "payments"},
                {"provider": "confluence", "scope": "PAY"},
            ],
            priorities=[{"provider": "confluence", "priority": 100}, {"provider": "jira", "priority": 90}],
            data_classification="confidential",
            freshness_hours=24,
        ),
    ]


CAPABILITY_KEYS = [
    "work_item.read", "work_item.search", "work_item.comment", "chat.read_thread", "chat.reply",
    "context.search", "context.read", "context.follow_reference", "artifact.read", "artifact.patch",
    "artifact.render", "repo.search", "repo.read", "repo.propose_patch", "tests.run",
    "tests.read_results", "ci.read", "ci.run", "logs.search", "telemetry.query", "human.ask",
    "human.request_approval", "publisher.publish_draft", "publisher.publish",
]


def build_capabilities() -> list[CapabilityDef]:
    write_ops = {"comment", "reply", "patch", "render", "propose_patch", "run", "ask", "request_approval", "publish_draft", "publish"}
    return [
        CapabilityDef(
            id=_id("capability", key),
            key=key,
            name=key.replace(".", " ").replace("_", " ").title(),
            group=key.split(".", 1)[0],
            operation=key.split(".", 1)[1],
            risk="high" if key == "publisher.publish" else ("medium" if key.split(".", 1)[1] in write_ops else "read"),
            status="active",
        )
        for key in CAPABILITY_KEYS
    ]


def build_executions() -> list[Execution]:
    executions = build_legacy_executions()
    skill_ref = {legacy: f"core/{legacy}" for legacy, _ in SKILL_MAPPINGS}
    for execution in executions:
        execution.agent_key = "requirements-agent"
        execution.flow_key = "requirements-to-delivery" if execution.playbook_key == "system-requirements-standard" else None
        execution.stage = "analysis" if "requirements" in execution.playbook_key else "development"
        execution.current_node = execution.current_operator_key
        execution.waiting_human = execution.status == "waiting_approval"
        execution.case_context = {
            "task_charter": {
                "goal": execution.reason,
                "scope": [execution.external_work_item_id],
                "non_goals": [],
            },
            "current_stage": execution.stage,
            "evidence_refs": [item.id for item in execution.evidence],
            "open_questions": execution.open_questions,
            "conflicts": execution.conflicts,
            "applicable_controls": CONTROL_KEYS,
        }
        execution.run_contract = {
            "agent_key": execution.agent_key,
            "playbook_key": execution.playbook_key,
            "control_pack_keys": CONTROL_KEYS,
            "knowledge_space_keys": ["corp-engineering", "payments-domain"],
        }
        execution.skill_runs = [
            {
                "id": run.id,
                "skill_key": skill_ref.get(run.operator_key, f"legacy/{run.operator_key}"),
                "interface_key": next((interface for legacy, interface in SKILL_MAPPINGS if legacy == run.operator_key), "legacy.operator@1"),
                "status": run.status,
                "started_at": run.started_at.isoformat(),
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "summary": run.summary,
            }
            for run in execution.operator_runs
        ]
    return executions
