"""Database connection settings."""

from __future__ import annotations

import os


DEFAULT_WORKSPACE_KEY = "default"
DEFAULT_WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"


def database_url() -> str | None:
    """Return SQLAlchemy URL when platform DB is configured."""
    url = (os.environ.get("PLATFORM_DATABASE_URL") or "").strip()
    return url or None


def skills_use_postgres() -> bool:
    """Skills SoT is PostgreSQL when DATABASE_URL is set or store=postgres."""
    store = (os.environ.get("SKILLS_STORE") or "").strip().lower()
    if store in ("json", "file"):
        return False
    if store in ("postgres", "postgresql", "sql"):
        return True
    return database_url() is not None


def workflows_use_postgres() -> bool:
    """Workflow/scenario SoT is PostgreSQL when DATABASE_URL is set or store=postgres."""
    store = (os.environ.get("WORKFLOWS_STORE") or "").strip().lower()
    if store in ("json", "file"):
        return False
    if store in ("postgres", "postgresql", "sql"):
        return True
    return database_url() is not None
