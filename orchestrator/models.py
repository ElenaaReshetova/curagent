"""Typed contracts for Temporal multi-agent orchestration."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    NEW = "new"
    NORMALIZED = "normalized"
    PLANNED = "planned"
    EXECUTING = "executing"
    UNDER_REVIEW = "under_review"
    REWORK = "rework"
    APPROVED = "approved"
    PUBLISHING = "publishing"
    DELIVERED = "delivered"
    FAILED = "failed"
    ESCALATED = "escalated"
    CLOSED = "closed"


class VerificationStatus(str, Enum):
    PASS = "pass"
    REWORK = "rework"
    FAIL = "fail"


class ArtifactType(str, Enum):
    BUSINESS_REQUIREMENTS = "BusinessRequirementsDoc"
    SYSTEM_REQUIREMENTS = "SystemRequirementsDoc"
    TEST_CASE_PACK = "TestCasePack"
    CODE_ANALYSIS = "CodeAnalysisReport"
    GENERAL = "GeneralArtifact"


class WorkflowInput(BaseModel):
    """Input to TaskLifecycleWorkflow — mirrors Kafka TaskMessage."""

    task_id: str
    source: str
    source_id: str
    description: str
    created_at: str
    callback_url: Optional[str] = None
    trace_id: Optional[str] = None
    workflow_template_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional pin. Normally omitted: workflow classifies first, then picks "
            "template via scenario_router.SKILL_TO_TEMPLATE or armed E2E flow graph."
        ),
    )
    flow_key: Optional[str] = Field(
        default=None,
        description="Explicit platform E2E flow key (e.g. slack-srd-delivery).",
    )


class NormalizedTaskSpec(BaseModel):
    task_id: str
    trace_id: str
    title: str
    description: str
    source: str
    source_id: str
    callback_url: Optional[str] = None
    language: str = "auto"
    constraints: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class RoutingDecision(BaseModel):
    primary_skill: str
    artifact_type: ArtifactType
    complexity: str = "low"  # low | medium | high
    confidence: float = 1.0
    verifier_rubric_id: str = "default"
    requires_planning: bool = False


class ExecutionStep(BaseModel):
    step_id: str
    skill: str
    description: str
    done_criteria: str


class ExecutionPlan(BaseModel):
    task_id: str
    steps: list[ExecutionStep]
    evidence_requirements: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    evidence_id: str
    type: str
    source_uri: str
    excerpt: str
    checksum: str


class EvidenceBundle(BaseModel):
    task_id: str
    items: list[EvidenceItem] = Field(default_factory=list)


class ArtifactDraft(BaseModel):
    artifact_id: str
    task_id: str
    type: ArtifactType
    skill: str
    version: int = 1
    content: str
    content_checksum: str
    evidence_refs: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class VerificationFinding(BaseModel):
    section: str
    severity: str  # blocking | warning
    message: str


class VerificationReport(BaseModel):
    artifact_id: str
    artifact_version: int
    status: VerificationStatus
    scores: dict[str, float] = Field(default_factory=dict)
    findings: list[VerificationFinding] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)


class ComplianceViolation(BaseModel):
    rule_id: str
    severity: str
    message: str


class ComplianceReport(BaseModel):
    artifact_id: str
    status: VerificationStatus
    violations: list[ComplianceViolation] = Field(default_factory=list)


class PublicationReceipt(BaseModel):
    receipt_id: str
    task_id: str
    artifact_id: str
    artifact_version: int
    target: str
    external_id: str
    url: Optional[str] = None
    content_checksum: str
    published_at: str


class WorkflowResult(BaseModel):
    task_id: str
    trace_id: str
    status: TaskStatus
    artifact: Optional[ArtifactDraft] = None
    receipt: Optional[PublicationReceipt] = None
    error: Optional[str] = None
