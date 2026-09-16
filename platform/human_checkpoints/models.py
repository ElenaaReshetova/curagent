"""Human Checkpoints domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

CheckpointType = Literal[
    "APPROVAL",
    "REVIEW",
    "DECISION",
    "SIGN_OFF",
    "RISK_ACCEPTANCE",
    "PUBLICATION_APPROVAL",
    "CHANGE_REQUEST",
    "MANUAL_INPUT",
    "EXCEPTION_APPROVAL",
]
CheckpointStatus = Literal[
    "CREATED",
    "OPEN",
    "ASSIGNED",
    "IN_REVIEW",
    "APPROVED",
    "REJECTED",
    "CHANGES_REQUESTED",
    "INPUT_PROVIDED",
    "EXPIRED",
    "ESCALATED",
    "CANCELLED",
    "SUPERSEDED",
]
Priority = Literal["HIGH", "MEDIUM", "LOW"]
RiskLevel = Literal["HIGH", "MEDIUM", "LOW"]
DecisionKey = Literal[
    "APPROVE",
    "REJECT",
    "REQUEST_CHANGES",
    "ACCEPT_RISK",
    "DECLINE_RISK",
    "PROVIDE_INPUT",
    "SELECT_OPTION",
    "ACKNOWLEDGE",
]


class DecisionOption(BaseModel):
    key: DecisionKey
    label: str
    impact: str
    requires_comment: bool = False


class ActivityEvent(BaseModel):
    at: str
    title: str
    actor: str = "System"
    detail: str = ""


class EvidenceItem(BaseModel):
    title: str
    source: str
    score: float = 0.0
    excerpt: str = ""


class ControlResult(BaseModel):
    name: str
    result: Literal["PASSED", "FAILED", "WARNING", "NOT_APPLICABLE", "OVERRIDDEN"] = "PASSED"
    severity: str = "MEDIUM"
    blocking: bool = False
    explanation: str = ""


class HumanCheckpointRecord(BaseModel):
    id: str
    title: str
    execution_id: str
    execution_title: str = ""
    source: str = ""
    checkpoint_type: CheckpointType = "APPROVAL"
    status: CheckpointStatus = "OPEN"
    priority: Priority = "MEDIUM"
    risk_level: RiskLevel = "MEDIUM"
    blocking: bool = True
    question: str = ""
    requested_action: str = ""
    artifact_name: str = ""
    artifact_version: str = "v1"
    assignee: str = "Unassigned"
    assignee_role: str = ""
    assignee_team: str = ""
    assignment_type: str = "ROLE"
    due_label: str = ""
    sla_label: str = ""
    queue_view: Literal["my", "team", "unassigned", "overdue", "completed", "all"] = "all"
    waiting_minutes: int = 0
    warnings_count: int = 0
    evidence_count: int = 0
    controls_passed: int = 0
    controls_warning: int = 0
    escalated: bool = False
    decision_options: list[DecisionOption] = Field(default_factory=list)
    artifact_preview: str = ""
    artifact_diff: list[str] = Field(default_factory=list)
    key_changes: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    controls: list[ControlResult] = Field(default_factory=list)
    activity: list[ActivityEvent] = Field(default_factory=list)
    audit: list[dict[str, Any]] = Field(default_factory=list)
    decision_comment: Optional[str] = None
    selected_decision: Optional[str] = None
    review_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    decided_at: Optional[datetime] = None


class HumanCheckpointCatalogItem(BaseModel):
    id: str
    title: str
    execution_id: str
    source: str
    checkpoint_type: str
    priority: str
    risk_level: str
    status: str
    assignee: str
    due_label: str
    sla_label: str
    artifact_name: str
    waiting_minutes: int = 0
    escalated: bool = False


class HumanCheckpointMetrics(BaseModel):
    my_open: int = 0
    due_today: int = 0
    team_queue: int = 0
    unassigned: int = 0
    overdue: int = 0
    escalated: int = 0
    completed: int = 0
    avg_decision_time: str = "0h 00m"
