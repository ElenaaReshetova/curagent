"""Controls domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

ControlType = Literal[
    "PRECONDITION", "POSTCONDITION", "ARTIFACT_VALIDATION", "RUNTIME_RESTRICTION",
    "CAPABILITY_RESTRICTION", "APPROVAL_REQUIREMENT", "DATA_RESIDENCY", "SECURITY",
    "COMPLIANCE", "COST_LIMIT", "QUALITY_GATE", "PUBLICATION_GATE",
    "ROUTING_RESTRICTION", "OBSERVABILITY", "RETENTION", "CUSTOM",
]
ControlStatus = Literal["draft", "active", "deprecated", "disabled", "archived"]
VersionStatus = Literal["DRAFT", "READY", "ACTIVE", "DEPRECATED", "DISABLED", "ARCHIVED"]
Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
EnforcementAction = Literal[
    "BLOCK", "WARN", "REQUIRE_HUMAN_APPROVAL", "PAUSE_EXECUTION",
    "FAIL_EXECUTION", "ESCALATE", "ALLOW_WITH_AUDIT",
]
EvaluationPoint = Literal[
    "BEFORE_EXECUTION", "AFTER_GRAPH", "BEFORE_ARTIFACT_PUBLICATION",
    "CONTINUOUS", "BEFORE_SKILL", "AFTER_SKILL",
]


class ApplicabilityCondition(BaseModel):
    field: str
    operator: str = "EQUALS"
    value: str = ""


class ViolationRef(BaseModel):
    execution_id: str
    summary: str
    status: str = "OPEN"


EvaluationResult = Literal["PASSED", "FAILED", "WARNING", "ERROR"]
ViolationStatus = Literal["OPEN", "IN_REMEDIATION", "RESOLVED", "ACCEPTED_RISK"]
ExceptionStatus = Literal["ACTIVE", "EXPIRED", "REVOKED"]


class ControlEvaluationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    control_key: str
    control_version_id: Optional[UUID] = None
    execution_id: Optional[str] = None
    evaluation_point: str = ""
    result: EvaluationResult = "PASSED"
    blocking: bool = False
    message: str = ""
    duration_ms: Optional[int] = None
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class ControlViolationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    control_key: str
    control_evaluation_id: Optional[UUID] = None
    execution_id: str = ""
    summary: str = ""
    status: ViolationStatus = "OPEN"
    blocking: bool = True
    severity: Severity = "MEDIUM"
    first_detected_at: datetime = Field(default_factory=datetime.utcnow)
    last_detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class ControlExceptionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    control_key: str
    reason: str = ""
    status: ExceptionStatus = "ACTIVE"
    valid_from: datetime = Field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None


class ControlVersion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    control_id: UUID
    semantic_version: str = "1.0.0"
    version_number: int = 1
    status: VersionStatus = "DRAFT"
    control_type: ControlType = "QUALITY_GATE"
    severity: Severity = "MEDIUM"
    evaluation_point: EvaluationPoint = "AFTER_GRAPH"
    evaluation_type: str = "DECLARATIVE_EXPRESSION"
    expression: str = ""
    enforcement_on_failed: EnforcementAction = "BLOCK"
    enforcement_on_error: EnforcementAction = "PAUSE_EXECUTION"
    applicability: list[ApplicabilityCondition] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    remediation_steps: list[str] = Field(default_factory=list)
    exception_policy: dict[str, Any] = Field(default_factory=dict)
    monitoring: dict[str, Any] = Field(default_factory=dict)
    validation_status: str = "unknown"
    validation_report: dict[str, Any] = Field(default_factory=dict)
    pass_rate_pct: float = 0.0
    violations_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None

    @field_validator("evaluation_point", mode="before")
    @classmethod
    def _coerce_eval_point(cls, value: Any) -> Any:
        if str(value or "").upper() == "AFTER_PLAYBOOK":
            return "AFTER_GRAPH"
        return value


class ControlRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    name: str
    description: str = ""
    owner_team: str = "Governance Team"
    status: ControlStatus = "draft"
    current_active_version_id: Optional[UUID] = None
    current_draft_version_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ControlCatalogItem(BaseModel):
    id: str
    key: str
    name: str
    description: str = ""
    control_type: str
    severity: str
    enforcement: str
    status: str
    evaluation_point: str
    version: Optional[str] = None
    owner: str = ""
    violations_count: int = 0
    pass_rate: str = "—"


class ControlMetrics(BaseModel):
    active: int = 0
    critical: int = 0
    evaluations_today: int = 0
    pass_rate_pct: float = 0.0
    open_violations: int = 0
    blocking_violations: int = 0
    active_exceptions: int = 0
    exceptions_expiring_week: int = 0
