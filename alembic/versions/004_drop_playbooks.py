"""drop playbook tables — PDLC stages removed in favor of graph governance tails

Revision ID: 004_drop_playbooks
Revises: 003_skills
Create Date: 2026-08-13
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "004_drop_playbooks"
down_revision: Union[str, None] = "003_skills"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("playbook_transitions", "playbook_nodes", "playbook_versions", "playbooks"):
        op.execute(f"DROP TABLE IF EXISTS {table}")


def downgrade() -> None:
    raise NotImplementedError("playbooks / PDLC stages are not restored")
