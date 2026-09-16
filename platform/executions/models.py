"""Executions domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


ExecutionType = Literal["FLOW", "PLAYBOOK", "SKILL", "SUBFLOW", "REPLAY", "SIMULATION"]
ExecutionStatus = Literal[
    "CREATED", "QUEUED", "STARTING", "RUNNING", "WAITING_FOR_EVENT",
    "WAITING_FOR_HUMAN", "PAUSED", "CANCELLING", "CANCELLED", "COMPENSATING",
    "COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED", "TIMED_OUT",
]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class StageRun(BaseModel):
    key: str
    name: str
    status: Literal["NOT_STARTED", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"] = "NOT_STARTED"
    duration: str = ""


class TimelineEvent(BaseModel):
    at: str
    title: str
    detail: str = ""
    actor: str = "System"


class ArtifactRef(BaseModel):
    name: str
    version: str = "v1"
    status: str = "Draft"


class EvidenceRef(BaseModel):
    title: str
    source: str
    score: float = 0.0


class ExecutionRecord(BaseModel):
    id: str
    title: str
    execution_type: ExecutionType = "FLOW"
    source_type: str = "JIRA"
    source_ref: str = ""
    flow_key: str = ""
    flow_name: str = ""
    playbook_key: str = ""
    playbook_name: str = ""
    current_stage: str = ""
    progress_pct: int = 0
    status: ExecutionStatus = "RUNNING"
    risk_level: RiskLevel = "MEDIUM"
    duration: str = "—"
    cost_usd: float = 0.0
    owner_team: str = "Platform"
    tokens: int = 0
    evidence_count: int = 0
    artifacts_count: int = 0
    current_activity: str = ""
    current_skill: str = ""
    stage_runs: list[StageRun] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    runtime_effective: dict[str, Any] = Field(default_factory=dict)
    snapshot: dict[str, Any] = Field(default_factory=dict)
    logs: str = ""
    legacy_store_id: Optional[str] = None
    # Graph-runtime linkage (unified WorkflowGraph runs)
    graph_id: Optional[str] = None
    graph_run_id: Optional[str] = None
    graph_version_id: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutionCatalogItem(BaseModel):
    id: str
    title: str
    source: str
    flow_name: str
    current_stage: str
    progress_pct: int
    status: str
    duration: str
    cost: str
    risk_level: str
    execution_type: str
    started_at: Optional[datetime] = None


class ExecutionMetrics(BaseModel):
    running: int = 0
    waiting_human: int = 0
    completed_today: int = 0
    success_rate_pct: float = 0.0
    failed: int = 0
    retryable: int = 0
    monthly_cost_usd: float = 0.0
    budget_pct: float = 0.0
