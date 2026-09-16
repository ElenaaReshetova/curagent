"""relational workflow / scenario tables

Revision ID: 005_workflows
Revises: 004_drop_playbooks
Create Date: 2026-08-17
"""

from __future__ import annotations

from typing import Sequence, Union
from uuid import UUID, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_workflows"
down_revision: Union[str, None] = "004_drop_playbooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
NODE_NS = UUID("b2c3d4e5-6f70-4890-bcde-f01234567890")

# Canvas key → YAML Node.type family, config.type, default Temporal activity.
NODE_TYPE_SEED = [
    ("trigger", "Trigger", "SELF_SERVE_TRIGGER", "Entry trigger", None),
    ("ai_agent", "Activity", "AI_AGENT", "Skill-backed AI agent", "ai_agent_execute"),
    ("ai", "Activity", "AI", "Prompted AI step", "ai_generate_summary"),
    ("webhook", "Activity", "WEBHOOK", "HTTP webhook", "http_webhook"),
    ("upsert_entity", "Activity", "UPSERT_ENTITY", "Upsert entity", "upsert_entity"),
    ("kafka", "Activity", "KAFKA", "Kafka publish", "kafka_publish"),
    ("integration_action", "Activity", "INTEGRATION_ACTION", "External integration", "integration_action"),
    ("internal_service", "Activity", "INTERNAL_SERVICE", "Internal service call", "internal_service"),
    ("subflow", "Activity", "SUBFLOW", "Child scenario", "execute_subflow"),
    ("condition", "Condition", "CONDITION", "Branching condition", None),
    ("input", "Input", "INPUT", "Human checkpoint", "human_review"),
]


def upgrade() -> None:
    op.create_table(
        "node_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("subtype", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("dsl", JSONType, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_node_types")),
        sa.UniqueConstraint("key", name="uq_node_types_key"),
    )

    op.create_table(
        "temporal_activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("node_type_id", sa.Uuid(), nullable=False),
        sa.Column("worker", sa.String(length=128), nullable=False),
        sa.Column("activity_name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["node_type_id"],
            ["node_types.id"],
            name=op.f("fk_temporal_activities_node_type_id_node_types"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_temporal_activities")),
        sa.UniqueConstraint("node_type_id", "activity_name", name="uq_temporal_activities_node_activity"),
    )
    op.create_index(op.f("ix_temporal_activities_node_type_id"), "temporal_activities", ["node_type_id"])

    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("segment_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("launched", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("owner_team", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=False),
        sa.Column("current_published_version_id", sa.Uuid(), nullable=True),
        sa.Column("current_draft_version_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name=op.f("fk_workflows_workspace_id_workspaces")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflows")),
        sa.UniqueConstraint("workspace_id", "key", name="uq_workflows_workspace_key"),
    )
    op.create_index(op.f("ix_workflows_workspace_id"), "workflows", ["workspace_id"])

    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("semantic_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dsl", JSONType, nullable=False),
        sa.Column("plan", JSONType, nullable=True),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("validation_report", JSONType, nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
            name=op.f("fk_workflow_versions_workflow_id_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_versions")),
        sa.UniqueConstraint("workflow_id", "version_number", name="uq_workflow_versions_number"),
    )
    op.create_index(op.f("ix_workflow_versions_workflow_id"), "workflow_versions", ["workflow_id"])

    op.create_table(
        "workflow_stages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("node_type_id", sa.Uuid(), nullable=True),
        sa.Column("identifier", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("pos_x", sa.Float(), nullable=True),
        sa.Column("pos_y", sa.Float(), nullable=True),
        sa.Column("dsl", JSONType, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
            name=op.f("fk_workflow_stages_workflow_id_workflows"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_version_id"],
            ["workflow_versions.id"],
            name=op.f("fk_workflow_stages_workflow_version_id_workflow_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_type_id"],
            ["node_types.id"],
            name=op.f("fk_workflow_stages_node_type_id_node_types"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_stages")),
        sa.UniqueConstraint("workflow_version_id", "identifier", name="uq_workflow_stages_version_identifier"),
    )
    op.create_index(op.f("ix_workflow_stages_workflow_id"), "workflow_stages", ["workflow_id"])
    op.create_index(op.f("ix_workflow_stages_workflow_version_id"), "workflow_stages", ["workflow_version_id"])
    op.create_index(op.f("ix_workflow_stages_node_type_id"), "workflow_stages", ["node_type_id"])

    op.create_table(
        "workflow_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_stage_id", sa.Uuid(), nullable=False),
        sa.Column("target_stage_id", sa.Uuid(), nullable=False),
        sa.Column("source_outlet", sa.String(length=128), nullable=True),
        sa.Column("source_option", sa.String(length=128), nullable=True),
        sa.Column("fallback", sa.Boolean(), nullable=False),
        sa.Column("dsl", JSONType, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
            name=op.f("fk_workflow_connections_workflow_id_workflows"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_version_id"],
            ["workflow_versions.id"],
            name=op.f("fk_workflow_connections_workflow_version_id_workflow_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_stage_id"],
            ["workflow_stages.id"],
            name=op.f("fk_workflow_connections_source_stage_id_workflow_stages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_stage_id"],
            ["workflow_stages.id"],
            name=op.f("fk_workflow_connections_target_stage_id_workflow_stages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_connections")),
    )
    op.create_index(op.f("ix_workflow_connections_workflow_id"), "workflow_connections", ["workflow_id"])
    op.create_index(
        op.f("ix_workflow_connections_workflow_version_id"), "workflow_connections", ["workflow_version_id"]
    )
    op.create_index(op.f("ix_workflow_connections_source_stage_id"), "workflow_connections", ["source_stage_id"])
    op.create_index(op.f("ix_workflow_connections_target_stage_id"), "workflow_connections", ["target_stage_id"])

    op.create_table(
        "executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("started_by", sa.String(length=255), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_by", sa.String(length=255), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("input_json", JSONType, nullable=False),
        sa.Column("output_json", JSONType, nullable=False),
        sa.Column("state_json", JSONType, nullable=False),
        sa.Column("plan", JSONType, nullable=True),
        sa.Column("dsl_snapshot", JSONType, nullable=True),
        sa.Column("events_json", JSONType, nullable=False),
        sa.Column("temporal_workflow_id", sa.String(length=255), nullable=True),
        sa.Column("parent_execution_id", sa.Uuid(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
            name=op.f("fk_executions_workflow_id_workflows"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_version_id"],
            ["workflow_versions.id"],
            name=op.f("fk_executions_workflow_version_id_workflow_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_execution_id"],
            ["executions.id"],
            name=op.f("fk_executions_parent_execution_id_executions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_executions")),
        sa.UniqueConstraint("temporal_workflow_id", name="uq_executions_temporal_workflow_id"),
    )
    op.create_index(op.f("ix_executions_workflow_id"), "executions", ["workflow_id"])
    op.create_index(op.f("ix_executions_workflow_version_id"), "executions", ["workflow_version_id"])
    op.create_index(op.f("ix_executions_status"), "executions", ["status"])
    op.create_index(op.f("ix_executions_parent_execution_id"), "executions", ["parent_execution_id"])

    op.create_table(
        "execution_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=True),
        sa.Column("node_identifier", sa.String(length=128), nullable=False),
        sa.Column("step_kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("input_json", JSONType, nullable=False),
        sa.Column("output_json", JSONType, nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_execution_steps_execution_id_executions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stage_id"],
            ["workflow_stages.id"],
            name=op.f("fk_execution_steps_stage_id_workflow_stages"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_execution_steps")),
        sa.UniqueConstraint("execution_id", "node_identifier", name="uq_execution_steps_execution_node"),
    )
    op.create_index(op.f("ix_execution_steps_execution_id"), "execution_steps", ["execution_id"])
    op.create_index(op.f("ix_execution_steps_stage_id"), "execution_steps", ["stage_id"])

    node_rows = []
    activity_rows = []
    for key, family, port_type, description, activity_name in NODE_TYPE_SEED:
        node_id = uuid5(NODE_NS, f"node-type:{key}")
        node_rows.append(
            {
                "id": node_id,
                "key": key,
                "type": family,
                "subtype": port_type,
                "description": description,
                "dsl": {"canvas_type": key, "port_type": port_type, "worker": activity_name or ""},
            }
        )
        if activity_name:
            activity_rows.append(
                {
                    "id": uuid5(NODE_NS, f"activity:{key}:{activity_name}"),
                    "node_type_id": node_id,
                    "worker": activity_name,
                    "activity_name": activity_name,
                }
            )

    node_types = sa.table(
        "node_types",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("type", sa.String()),
        sa.column("subtype", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("dsl", JSONType),
    )
    op.bulk_insert(node_types, node_rows)
    if activity_rows:
        activities = sa.table(
            "temporal_activities",
            sa.column("id", sa.Uuid()),
            sa.column("node_type_id", sa.Uuid()),
            sa.column("worker", sa.String()),
            sa.column("activity_name", sa.String()),
        )
        op.bulk_insert(activities, activity_rows)


def downgrade() -> None:
    op.drop_index(op.f("ix_execution_steps_stage_id"), table_name="execution_steps")
    op.drop_index(op.f("ix_execution_steps_execution_id"), table_name="execution_steps")
    op.drop_table("execution_steps")
    op.drop_index(op.f("ix_executions_parent_execution_id"), table_name="executions")
    op.drop_index(op.f("ix_executions_status"), table_name="executions")
    op.drop_index(op.f("ix_executions_workflow_version_id"), table_name="executions")
    op.drop_index(op.f("ix_executions_workflow_id"), table_name="executions")
    op.drop_table("executions")
    op.drop_index(op.f("ix_workflow_connections_target_stage_id"), table_name="workflow_connections")
    op.drop_index(op.f("ix_workflow_connections_source_stage_id"), table_name="workflow_connections")
    op.drop_index(op.f("ix_workflow_connections_workflow_version_id"), table_name="workflow_connections")
    op.drop_index(op.f("ix_workflow_connections_workflow_id"), table_name="workflow_connections")
    op.drop_table("workflow_connections")
    op.drop_index(op.f("ix_workflow_stages_node_type_id"), table_name="workflow_stages")
    op.drop_index(op.f("ix_workflow_stages_workflow_version_id"), table_name="workflow_stages")
    op.drop_index(op.f("ix_workflow_stages_workflow_id"), table_name="workflow_stages")
    op.drop_table("workflow_stages")
    op.drop_index(op.f("ix_workflow_versions_workflow_id"), table_name="workflow_versions")
    op.drop_table("workflow_versions")
    op.drop_index(op.f("ix_workflows_workspace_id"), table_name="workflows")
    op.drop_table("workflows")
    op.drop_index(op.f("ix_temporal_activities_node_type_id"), table_name="temporal_activities")
    op.drop_table("temporal_activities")
    op.drop_table("node_types")
