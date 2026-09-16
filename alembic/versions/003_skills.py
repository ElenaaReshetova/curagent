"""add skills + skill_versions tables

Revision ID: 003_skills
Revises: 002_rule_bindings
Create Date: 2026-07-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_skills"
down_revision: Union[str, None] = "002_rule_bindings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("skill_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("owner_team", sa.String(length=255), nullable=False),
        sa.Column("parent_skill_id", sa.Uuid(), nullable=True),
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
        sa.Column("current_published_version_id", sa.Uuid(), nullable=True),
        sa.Column("current_draft_version_id", sa.Uuid(), nullable=True),
        sa.Column("runs_30d", sa.Integer(), nullable=False),
        sa.Column("success_rate", sa.Float(), nullable=False),
        sa.Column("bindings_json", JSONType, nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name=op.f("fk_skills_workspace_id_workspaces")
        ),
        sa.ForeignKeyConstraint(
            ["parent_skill_id"],
            ["skills.id"],
            name=op.f("fk_skills_parent_skill_id_skills"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skills")),
        sa.UniqueConstraint("workspace_id", "key", name="uq_skills_workspace_key"),
    )
    op.create_index(op.f("ix_skills_workspace_id"), "skills", ["workspace_id"])
    op.create_index(op.f("ix_skills_parent_skill_id"), "skills", ["parent_skill_id"])

    op.create_table(
        "skill_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("semantic_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("skill_markdown", sa.Text(), nullable=False),
        sa.Column("manifest_json", JSONType, nullable=False),
        sa.Column("package_checksum", sa.String(length=128), nullable=False),
        sa.Column("runtime_type", sa.String(length=64), nullable=False),
        sa.Column("interface_key", sa.String(length=255), nullable=False),
        sa.Column("input_contract_key", sa.String(length=255), nullable=False),
        sa.Column("output_contract_key", sa.String(length=255), nullable=False),
        sa.Column("allowed_capabilities_json", JSONType, nullable=False),
        sa.Column("files_json", JSONType, nullable=False),
        sa.Column("test_cases_json", JSONType, nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("validation_report_json", JSONType, nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skills.id"],
            name=op.f("fk_skill_versions_skill_id_skills"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill_versions")),
        sa.UniqueConstraint("skill_id", "semantic_version", name="uq_skill_versions_semver"),
    )
    op.create_index(op.f("ix_skill_versions_skill_id"), "skill_versions", ["skill_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_skill_versions_skill_id"), table_name="skill_versions")
    op.drop_table("skill_versions")
    op.drop_index(op.f("ix_skills_parent_skill_id"), table_name="skills")
    op.drop_index(op.f("ix_skills_workspace_id"), table_name="skills")
    op.drop_table("skills")
