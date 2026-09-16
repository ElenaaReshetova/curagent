"""Relational workflow (scenario) schema.

Physical SoT for graphs: catalog node types, versioned workflows,
normalized stages/connections, executions and per-step runs.

Author API remains an atomic workflow DSL document; these tables are the
normalized projection of that document plus runtime history.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.platform.db.base import Base, JsonDict


class NodeTypeRow(Base):
    """Reusable node catalog (YAML `/nodes`). Not a canvas instance."""

    __tablename__ = "node_types"
    __table_args__ = (UniqueConstraint("key", name="uq_node_types_key"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # Trigger | Activity | Input | Condition
    subtype: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    dsl: Mapped[dict[str, Any]] = mapped_column(JsonDict, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    activities: Mapped[list[TemporalActivityRow]] = relationship(
        back_populates="node_type", cascade="all, delete-orphan"
    )


class TemporalActivityRow(Base):
    """Temporal worker binding for a catalog node (YAML `/activities`).

`worker` is the Temporal activity name (`http_webhook`, `ai_agent_execute`, …),
not a task-queue label and not Temporal's own database.
"""

    __tablename__ = "temporal_activities"
    __table_args__ = (
        UniqueConstraint("node_type_id", "activity_name", name="uq_temporal_activities_node_activity"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    node_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("node_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    worker: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    activity_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    node_type: Mapped[NodeTypeRow] = relationship(back_populates="activities")


class WorkflowRow(Base):
    """Scenario identity (YAML `/workflows`). Product name: scenario."""

    __tablename__ = "workflows"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_workflows_workspace_key"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="e2e")  # e2e | stage
    segment_id: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    launched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    owner_team: Mapped[str] = mapped_column(String(255), nullable=False, default="Platform")
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    current_published_version_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    current_draft_version_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list[WorkflowVersionRow]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    executions: Mapped[list[ExecutionRow]] = relationship(back_populates="workflow")


class WorkflowVersionRow(Base):
    """Immutable-on-publish snapshot. YAML `/workflows/{id}/versions` cannot live on one row."""

    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version_number", name="uq_workflow_versions_number"),
        CheckConstraint("status != 'PUBLISHED' OR plan IS NOT NULL", name="ck_workflow_versions_published_plan"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    semantic_version: Mapped[str] = mapped_column(String(32), nullable=False, default="0.1.0")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    dsl: Mapped[dict[str, Any]] = mapped_column(JsonDict, nullable=False, default=dict)
    plan: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonDict, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    validation_report: Mapped[dict[str, Any]] = mapped_column(JsonDict, nullable=False, default=dict)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

    workflow: Mapped[WorkflowRow] = relationship(back_populates="versions")
    stages: Mapped[list[WorkflowStageRow]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    connections: Mapped[list[WorkflowConnectionRow]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class WorkflowStageRow(Base):
    """Canvas instance of a node on a workflow version (YAML `/stages`)."""

    __tablename__ = "workflow_stages"
    __table_args__ = (
        UniqueConstraint("workflow_version_id", "identifier", name="uq_workflow_stages_version_identifier"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_type_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("node_types.id", ondelete="SET NULL"), nullable=True, index=True
    )
    identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pos_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pos_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dsl: Mapped[dict[str, Any]] = mapped_column(JsonDict, nullable=False, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    version: Mapped[WorkflowVersionRow] = relationship(back_populates="stages")


class WorkflowConnectionRow(Base):
    """Directed edge on a workflow version (YAML `/connections` + source/target FKs)."""

    __tablename__ = "workflow_connections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_stage_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_stage_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_outlet: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_option: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dsl: Mapped[dict[str, Any]] = mapped_column(JsonDict, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    version: Mapped[WorkflowVersionRow] = relationship(back_populates="connections")


class ExecutionRow(Base):
    """Workflow run header (YAML `/executions`)."""

    __tablename__ = "executions"
    __table_args__ = (UniqueConstraint("temporal_workflow_id", name="uq_executions_temporal_workflow_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    workflow_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="live")  # live | test
    started_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    ended_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    iteration: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    input_json: Mapped[dict[str, Any]] = mapped_column(JsonDict, nullable=False, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JsonDict, nullable=False, default=dict)
    state_json: Mapped[dict[str, Any]] = mapped_column(JsonDict, nullable=False, default=dict)
    plan: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonDict, nullable=True)
    dsl_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonDict, nullable=True)
    events_json: Mapped[list[Any]] = mapped_column(JsonDict, nullable=False, default=list)
    temporal_workflow_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    parent_execution_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    workflow: Mapped[WorkflowRow] = relationship(back_populates="executions")
    steps: Mapped[list[ExecutionStepRow]] = relationship(
        back_populates="execution", cascade="all, delete-orphan"
    )


class ExecutionStepRow(Base):
    """Per-node progress of a run. Missing from the YAML; required for inspector/runtime."""

    __tablename__ = "execution_steps"
    __table_args__ = (
        UniqueConstraint("execution_id", "node_identifier", name="uq_execution_steps_execution_node"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("workflow_stages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    node_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    step_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="activity")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input_json: Mapped[dict[str, Any]] = mapped_column(JsonDict, nullable=False, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JsonDict, nullable=False, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    execution: Mapped[ExecutionRow] = relationship(back_populates="steps")
