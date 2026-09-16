"""Ensure default workspace exists."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.platform.db.models.workspace import WorkspaceRow
from src.platform.db.settings import DEFAULT_WORKSPACE_ID, DEFAULT_WORKSPACE_KEY


def ensure_default_workspace(session: Session) -> WorkspaceRow:
    ws_id = UUID(DEFAULT_WORKSPACE_ID)
    row = session.get(WorkspaceRow, ws_id)
    if row:
        return row
    existing = session.scalar(select(WorkspaceRow).where(WorkspaceRow.key == DEFAULT_WORKSPACE_KEY))
    if existing:
        return existing
    row = WorkspaceRow(
        id=ws_id,
        key=DEFAULT_WORKSPACE_KEY,
        name="Default Workspace",
        status="active",
        region=None,
    )
    session.add(row)
    session.flush()
    return row
