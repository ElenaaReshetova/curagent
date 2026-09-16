"""AI Agent Platform — domain models (Control Plane + Runtime Plane)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ── Control Plane ──────────────────────────────────────────────

class FacetDefinition(BaseModel):
    key: str
    name: str
    description: str = ""
    required: bool = True


class ArtifactBlueprint(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    name: str
    version: str = "1.0"
    status: Literal["draft", "active", "deprecated"] = "draft"
    artifact_schema: dict[str, Any] = Field(default_factory=dict)
    facets: list[FacetDefinition] = Field(default_factory=list)
    completion_rules: list[dict[str, Any]] = Field(default_factory=list)
    allowed_operator_keys: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OperatorDefinition(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    version: str = "1.0"
    name: str
    kind: Literal[
        "analysis",
        "evidence_acquisition",
        "transformation",
        "validation",
        "publication",
        "approval",
    ] = "analysis"
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    readiness_rule: dict[str, Any] = Field(default_factory=dict)
    completion_rule: dict[str, Any] = Field(default_factory=dict)
    allowed_capabilities: list[str] = Field(default_factory=list)
    risk_level: Literal["read", "low", "medium", "high", "critical"] = "read"
    side_effects: Literal["none", "draft", "write", "publish", "destructive"] = "none"
    prompt_template: Optional[str] = None
    enabled: bool = True
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AdaptiveZone(BaseModel):
    id: str
    name: str
    allowed_operator_kinds: list[str] = Field(default_factory=list)
    allowed_operator_keys: Optional[list[str]] = None
    allowed_capabilities: list[str] = Field(default_factory=list)
    forbidden_capabilities: list[str] = Field(default_factory=list)
    maximum_tool_calls: int = 20
    maximum_operator_runs: int = 30
    maximum_plan_revisions: int = 5
    maximum_llm_tokens: Optional[int] = None
    side_effect_limit: Literal["none", "draft", "write"] = "draft"
    require_confirmation_for_new_operator: bool = True


class Playbook(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    version: str = "1.0"
    name: str
    description: str = ""
    artifact_blueprint_key: str
    artifact_blueprint_version: str = "1.0"
    status: Literal["draft", "active", "deprecated"] = "draft"
    required_outcomes: list[str] = Field(default_factory=list)
    pinned_actions: list[dict[str, Any]] = Field(default_factory=list)
    conditional_actions: list[dict[str, Any]] = Field(default_factory=list)
    ordering_constraints: list[dict[str, Any]] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    adaptive_zones: list[AdaptiveZone] = Field(default_factory=list)
    publication_rules: dict[str, Any] = Field(default_factory=dict)
    flow_template_id: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PolicyPack(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    version: str = "1.0"
    name: str
    authority: Literal["regulatory", "corporate", "domain", "team"] = "corporate"
    enforcement: Literal["hard", "controlled", "customizable"] = "controlled"
    status: Literal["draft", "active", "deprecated"] = "draft"
    applicability_rule: dict[str, Any] = Field(default_factory=dict)
    rules: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Agent(BaseModel):
    """Legacy entity — deprecated by V2 RuntimeProfile. Kept for migration."""

    id: UUID = Field(default_factory=uuid4)
    key: str
    name: str
    status: Literal["draft", "active", "disabled"] = "draft"
    ingress_bindings: list[dict[str, Any]] = Field(default_factory=list)
    allowed_playbook_keys: list[str] = Field(default_factory=list)
    allowed_flow_keys: list[str] = Field(default_factory=list)
    default_playbook_key: Optional[str] = None
    skill_bindings: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_space_bindings: list[str] = Field(default_factory=list)
    model_profile_key: str = "gigachat-prod"
    supervision_profile_key: str = "checkpoint"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RuntimeProfile(BaseModel):
    """Technical execution configuration (V2 replacement for Agent)."""

    id: UUID = Field(default_factory=uuid4)
    key: str
    name: str
    description: str = ""
    provider: Literal["lm_studio", "gigachat", "qwen", "openai_compatible"] = "gigachat"
    model: str = ""
    fallback_models: list[str] = Field(default_factory=list)
    generation_config: dict[str, Any] = Field(default_factory=dict)
    sandbox_config: dict[str, Any] = Field(default_factory=dict)
    limits_json: dict[str, Any] = Field(default_factory=dict)
    secrets_reference: str = ""
    region: str = "ru-central"
    status: Literal["draft", "active", "disabled"] = "draft"
    migrated_from_agent_key: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class FlowDefinition(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    version: str = "1.0"
    name: str
    status: Literal["draft", "active", "deprecated"] = "draft"
    family: Optional[str] = None
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    entry_contract: str = ""
    exit_contract: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PlaybookDefinition(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    version: str = "1.0"
    family: str
    name: str
    description: str = ""
    status: Literal["draft", "active", "deprecated"] = "draft"
    entry_contract: str = ""
    exit_contract: str = ""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    skill_slots: list[dict[str, Any]] = Field(default_factory=list)
    control_pack_keys: list[str] = Field(default_factory=list)
    rule_set_keys: list[str] = Field(default_factory=list)
    dor: list[dict[str, Any] | str] = Field(default_factory=list)
    dod: list[dict[str, Any] | str] = Field(default_factory=list)
    flow_template_id: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SkillInterface(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    name: str
    version: str = "1"
    description: str = ""
    input_contract_key: str = ""
    output_contract_key: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    required_capabilities: list[str] = Field(default_factory=list)
    source: Literal["platform", "custom"] = "custom"
    status: Literal["draft", "active", "deprecated"] = "active"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SkillImplementation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    interface_key: str
    name: str
    version: str = "1.0"
    status: Literal["draft", "active", "deprecated", "disabled"] = "draft"
    source: Literal["system", "imported", "team"] = "system"
    owner: str = "platform"
    skill_md: str = ""
    manifest: dict[str, Any] = Field(default_factory=dict)
    allowed_capabilities: list[str] = Field(default_factory=list)
    prohibited_mcp_refs: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RuleSet(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    name: str
    scope: str = "organization"
    status: Literal["draft", "active", "deprecated"] = "draft"
    content_md: str = ""
    structured_rules: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ControlPack(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    name: str
    authority: Literal["regulatory", "corporate", "domain", "team"] = "corporate"
    enforcement: Literal["hard", "controlled", "customizable"] = "controlled"
    status: Literal["draft", "active", "deprecated"] = "draft"
    applicability_rule: dict[str, Any] = Field(default_factory=dict)
    locked_steps: list[dict[str, Any]] = Field(default_factory=list)
    rules: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeSpace(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    name: str
    status: Literal["draft", "active", "disabled"] = "draft"
    source_bindings: list[dict[str, Any]] = Field(default_factory=list)
    priorities: list[dict[str, Any]] = Field(default_factory=list)
    data_classification: str = "internal"
    freshness_hours: int = 24
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CapabilityDef(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    name: str
    group: str
    operation: str
    risk: Literal["read", "low", "medium", "high", "critical"] = "read"
    status: Literal["active", "disabled", "draft"] = "active"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutionContractTemplate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    version: str = "1.0"
    name: str
    description: str = ""
    status: Literal["draft", "active", "deprecated"] = "active"
    defaults_json: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MCPIntegrationSummary(BaseModel):
    key: str
    name: str
    version: str = "1.0"
    status: Literal["online", "degraded", "offline"] = "online"
    last_check_at: Optional[datetime] = None
    tool_count: int = 0
    description: str = ""
    endpoint: str = ""
    capabilities: list[str] = Field(default_factory=list)


class ModelProfile(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    name: str
    description: str = ""
    provider: Literal["lm_studio", "gigachat", "qwen", "openai_compatible"] = "lm_studio"
    model_id: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096
    prompt_system: str = ""
    status: Literal["draft", "active", "deprecated"] = "active"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PlatformUser(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    username: str
    display_name: str
    email: str = ""
    roles: list[str] = Field(default_factory=list)
    status: Literal["active", "disabled"] = "active"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AuditEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    actor: str = "system"
    action: str
    entity_type: str
    entity_id: str = ""
    summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


# ── Runtime Plane ──────────────────────────────────────────────

class ArtifactFacetStatus(BaseModel):
    key: str
    status: Literal[
        "unknown", "partial", "supported", "confirmed", "conflicting", "stale", "not_applicable"
    ] = "unknown"
    summary: str = ""


class OperatorRunRecord(BaseModel):
    id: str
    operator_key: str
    status: Literal["running", "completed", "failed", "skipped"] = "completed"
    started_at: datetime
    finished_at: Optional[datetime] = None
    summary: str = ""


class EvidenceRecord(BaseModel):
    id: str
    source_type: str
    source_ref: str
    trust_class: Literal["A", "B", "C", "D", "E"] = "E"
    summary: str = ""
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalRecord(BaseModel):
    id: str
    type: str
    status: Literal["pending", "approved", "rejected", "expired", "cancelled"] = "pending"
    requested_role: Optional[str] = None
    subject: str = ""
    decision_comment: Optional[str] = None


class Execution(BaseModel):
    id: str
    external_source: str
    external_work_item_id: str
    external_work_item_url: Optional[str] = None
    playbook_key: str
    playbook_name: str
    playbook_version: str = "1.0"
    agent_key: str = "requirements-agent"
    flow_key: Optional[str] = None
    stage: str = ""
    current_node: Optional[str] = None
    waiting_human: bool = False
    case_context: dict[str, Any] = Field(default_factory=dict)
    run_contract: dict[str, Any] = Field(default_factory=dict)
    skill_runs: list[dict[str, Any]] = Field(default_factory=list)
    status: Literal[
        "received",
        "compiling",
        "running",
        "waiting_approval",
        "blocked",
        "failed",
        "completed",
        "cancelled",
    ]
    contract_version: int = 1
    contract_summary: dict[str, Any] = Field(default_factory=dict)
    current_operator_key: Optional[str] = None
    next_proposed_action: Optional[str] = None
    reason: str = ""
    budget_usage: dict[str, Any] = Field(default_factory=dict)
    artifact_facets: list[ArtifactFacetStatus] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    operator_runs: list[OperatorRunRecord] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    approvals: list[ApprovalRecord] = Field(default_factory=list)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    audit_trail: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutionSummary(BaseModel):
    id: str
    external_source: str
    external_work_item_id: str
    playbook_name: str
    status: Literal[
        "received",
        "compiling",
        "running",
        "waiting_approval",
        "blocked",
        "failed",
        "completed",
        "cancelled",
    ]
    started_at: datetime
    current_operator_key: Optional[str] = None


class ActivityItem(BaseModel):
    id: str
    occurred_at: datetime
    execution_id: str
    kind: str
    message: str
    severity: Literal["info", "warn", "error"] = "info"


class QueueItem(BaseModel):
    id: str
    execution_id: str
    external_work_item_id: str
    playbook_name: str
    priority: int = 50
    status: Literal["queued", "claimed", "delayed"] = "queued"
    enqueued_at: datetime
    eta_seconds: Optional[int] = None


class PlatformEvent(BaseModel):
    id: str
    event_type: str
    occurred_at: datetime
    correlation_id: str = ""
    producer: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class SystemHealthItem(BaseModel):
    key: str
    label: str
    status: Literal["ok", "warn", "error"]
    detail: str


class ResourceMetric(BaseModel):
    key: str
    label: str
    value: str
    delta_pct: float
    series: list[float] = Field(default_factory=list)


class OverviewPayload(BaseModel):
    agents: list[Agent] = Field(default_factory=list)  # legacy
    runtime_profiles: list[RuntimeProfile] = Field(default_factory=list)
    # Versioned Playbooks/Skills catalogs (dicts for UI + dashboard; not governed-flat)
    playbooks: list[dict[str, Any]] = Field(default_factory=list)
    skills: list[dict[str, Any]] = Field(default_factory=list)
    controls: list[ControlPack] = Field(default_factory=list)
    knowledge_spaces: list[KnowledgeSpace] = Field(default_factory=list)
    flows: list[FlowDefinition] = Field(default_factory=list)
    integrations: list[MCPIntegrationSummary] = Field(default_factory=list)
    recent_executions: list[ExecutionSummary] = Field(default_factory=list)
    system_health: list[SystemHealthItem] = Field(default_factory=list)
    resource_usage: list[ResourceMetric] = Field(default_factory=list)
    waiting_approvals_count: int = 0
    operators: list[OperatorDefinition] = Field(default_factory=list)
    blueprints: list[ArtifactBlueprint] = Field(default_factory=list)
    policies: list[PolicyPack] = Field(default_factory=list)
    contract_templates: list[ExecutionContractTemplate] = Field(default_factory=list)
