"""Graph persistence models — workflow DSL document + Temporal plan + runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.platform.graphs.workflow_dsl import DslConnection, DslNode, WorkflowDsl

GraphKind = Literal["e2e", "stage"]
GraphStatus = Literal["draft", "active", "deprecated", "archived"]
VersionStatus = Literal["DRAFT", "PUBLISHED", "DEPRECATED", "ARCHIVED"]
ValidationStatus = Literal["unknown", "valid", "invalid", "warning"]

# Back-compat names used by UI canvas helpers
WorkflowGraph = WorkflowDsl
WorkflowEdge = DslConnection
BaseNode = DslNode

# Canvas palette kinds (map to config.type). No End — has none.
NodeType = Literal[
    "trigger",
    "ai_agent",
    "ai",
    "webhook",
    "condition",
    "input",
    "upsert_entity",
    "kafka",
    "integration_action",
    "internal_service",
    "subflow",
]


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"
    node_id: Optional[str] = None


class ValidationReport(BaseModel):
    ok: bool = True
    issues: list[ValidationIssue] = Field(default_factory=list)

    def add(self, code: str, message: str, *, severity: Literal["error", "warning"] = "error", node_id: str | None = None) -> None:
        self.issues.append(ValidationIssue(code=code, message=message, severity=severity, node_id=node_id))
        if severity == "error":
            self.ok = False


class GraphVersion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    graph_id: UUID
    semantic_version: str = "0.1.0"
    status: VersionStatus = "DRAFT"
    # workflow DSL document (source of truth)
    dsl: dict[str, Any] = Field(default_factory=dict)
    # Parsed Temporal steps (set on publish / run)
    temporal_plan: Optional[dict[str, Any]] = None
    validation_status: ValidationStatus = "unknown"
    validation_report: dict[str, Any] = Field(default_factory=dict)
    revision: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GraphRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str = "default"
    key: str
    name: str
    description: str = ""
    kind: GraphKind
    status: GraphStatus = "draft"
    launched: bool = False
    owner_team: str = "Platform"
    current_published_version_id: Optional[UUID] = None
    current_draft_version_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    revision: int = 1


class GraphRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    graph_id: UUID
    version_id: UUID
    status: Literal["pending", "running", "waiting", "completed", "failed", "cancelled"] = "pending"
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    temporal_workflow_id: Optional[str] = None
    parent_execution_id: Optional[UUID] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
