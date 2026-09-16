"""enforce immutable workflow snapshot invariants

Revision ID: 006_workflow_invariants
Revises: 005_workflows
Create Date: 2026-08-18
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "006_workflow_invariants"
down_revision: Union[str, None] = "005_workflows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_workflow_versions_published_plan",
        "workflow_versions",
        "status != 'PUBLISHED' OR plan IS NOT NULL",
    )
    op.create_foreign_key(
        "fk_workflows_current_published_version",
        "workflows",
        "workflow_versions",
        ["current_published_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_workflows_current_draft_version",
        "workflows",
        "workflow_versions",
        ["current_draft_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_workflows_current_draft_version", "workflows", type_="foreignkey")
    op.drop_constraint("fk_workflows_current_published_version", "workflows", type_="foreignkey")
    op.drop_constraint("ck_workflow_versions_published_plan", "workflow_versions", type_="check")
