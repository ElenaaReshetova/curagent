"""workspaces + playbooks foundation

Revision ID: 001_workspaces_playbooks
Revises:
Create Date: 2026-07-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_workspaces_playbooks"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
        sa.UniqueConstraint("key", name=op.f("uq_workspaces_key")),
    )

    op.create_table(
        "playbooks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("owner_team", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_published_version_id", sa.Uuid(), nullable=True),
        sa.Column("current_draft_version_id", sa.Uuid(), nullable=True),
        sa.Column("executions_30d", sa.Integer(), nullable=False),
        sa.Column("success_rate", sa.Float(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name=op.f("fk_playbooks_workspace_id_workspaces")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_playbooks")),
        sa.UniqueConstraint("workspace_id", "key", name="uq_playbooks_workspace_key"),
    )
    op.create_index(op.f("ix_playbooks_workspace_id"), "playbooks", ["workspace_id"])

    op.create_table(
        "playbook_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("playbook_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("semantic_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("graph_json", JSONType, nullable=False),
        sa.Column("input_contract_key", sa.String(length=255), nullable=False),
        sa.Column("output_contract_key", sa.String(length=255), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("validation_report", JSONType, nullable=False),
        sa.Column("skill_bindings_json", JSONType, nullable=False),
        sa.Column("control_bindings_json", JSONType, nullable=False),
        sa.Column("rule_bindings_json", JSONType, nullable=False),
        sa.Column("compiled_definition_json", JSONType, nullable=True),
        sa.Column("dependency_snapshot_json", JSONType, nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["playbook_id"],
            ["playbooks.id"],
            name=op.f("fk_playbook_versions_playbook_id_playbooks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_playbook_versions")),
        sa.UniqueConstraint("playbook_id", "version_number", name="uq_playbook_versions_number"),
    )
    op.create_index(op.f("ix_playbook_versions_playbook_id"), "playbook_versions", ["playbook_id"])

    op.create_table(
        "playbook_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("playbook_version_id", sa.Uuid(), nullable=False),
        sa.Column("node_key", sa.String(length=128), nullable=False),
        sa.Column("node_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("interface_key", sa.String(length=255), nullable=True),
        sa.Column("immutable", sa.Boolean(), nullable=False),
        sa.Column("control_source", sa.String(length=255), nullable=True),
        sa.Column("config_json", JSONType, nullable=False),
        sa.Column("input_mapping_json", JSONType, nullable=True),
        sa.Column("output_mapping_json", JSONType, nullable=True),
        sa.Column("retry_policy_json", JSONType, nullable=True),
        sa.Column("timeout_policy_json", JSONType, nullable=True),
        sa.Column("error_policy_json", JSONType, nullable=True),
        sa.Column("position_json", JSONType, nullable=False),
        sa.ForeignKeyConstraint(
            ["playbook_version_id"],
            ["playbook_versions.id"],
            name=op.f("fk_playbook_nodes_playbook_version_id_playbook_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_playbook_nodes")),
        sa.UniqueConstraint("playbook_version_id", "node_key", name="uq_playbook_nodes_version_key"),
    )
    op.create_index(op.f("ix_playbook_nodes_playbook_version_id"), "playbook_nodes", ["playbook_version_id"])

    op.create_table(
        "playbook_transitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("playbook_version_id", sa.Uuid(), nullable=False),
        sa.Column("edge_key", sa.String(length=128), nullable=False),
        sa.Column("source_node_key", sa.String(length=128), nullable=False),
        sa.Column("source_outcome", sa.String(length=64), nullable=False),
        sa.Column("target_node_key", sa.String(length=128), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("condition_json", JSONType, nullable=True),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("config_json", JSONType, nullable=False),
        sa.ForeignKeyConstraint(
            ["playbook_version_id"],
            ["playbook_versions.id"],
            name=op.f("fk_playbook_transitions_playbook_version_id_playbook_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_playbook_transitions")),
    )
    op.create_index(
        op.f("ix_playbook_transitions_playbook_version_id"),
        "playbook_transitions",
        ["playbook_version_id"],
    )

    # Default workspace seed (idempotent for fresh DBs)
    op.execute(
        """
        INSERT INTO workspaces (id, key, name, status, region)
        VALUES (
          '00000000-0000-4000-8000-000000000001',
          'default',
          'Default Workspace',
          'active',
          NULL
        )
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_playbook_transitions_playbook_version_id"), table_name="playbook_transitions")
    op.drop_table("playbook_transitions")
    op.drop_index(op.f("ix_playbook_nodes_playbook_version_id"), table_name="playbook_nodes")
    op.drop_table("playbook_nodes")
    op.drop_index(op.f("ix_playbook_versions_playbook_id"), table_name="playbook_versions")
    op.drop_table("playbook_versions")
    op.drop_index(op.f("ix_playbooks_workspace_id"), table_name="playbooks")
    op.drop_table("playbooks")
    op.drop_table("workspaces")
