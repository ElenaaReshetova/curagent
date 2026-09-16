"""make playbook_versions.rule_bindings_json optional for historical installs

Revision ID: 002_rule_bindings
Revises: 001_workspaces_playbooks
Create Date: 2026-07-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision: str = "002_rule_bindings"
down_revision: Union[str, None] = "001_workspaces_playbooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("playbook_versions"):
        return
    cols = {c["name"] for c in insp.get_columns("playbook_versions")}
    if "rule_bindings_json" in cols:
        return
    op.add_column(
        "playbook_versions",
        sa.Column("rule_bindings_json", JSONType, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.alter_column("playbook_versions", "rule_bindings_json", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("playbook_versions"):
        return
    cols = {c["name"] for c in insp.get_columns("playbook_versions")}
    if "rule_bindings_json" not in cols:
        return
    op.drop_column("playbook_versions", "rule_bindings_json")
