"""Helpers to initialize platform schema (tests / local SQLite)."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from src.platform.db.base import Base
from src.platform.db import models  # noqa: F401
from src.platform.db.session import get_engine, reset_engine_cache

# Process-level cache: skip inspect() after first successful ensure per URL key.
_READY: set[str] = set()


def clear_schema_cache() -> None:
    """Reset schema-ready cache (tests / engine URL changes)."""
    _READY.clear()


def init_schema(url: str | None = None) -> Engine:
    """Create all tables for the given URL (or PLATFORM_DATABASE_URL)."""
    reset_engine_cache()
    clear_schema_cache()
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    _READY.add(url or "")
    return engine


def ensure_schema(url: str | None = None) -> Engine:
    """Create tables if the platform schema is missing (dev / first boot).

    Prefer `alembic upgrade head` in production; this is a safe no-op when tables exist.
    Cached per process so list endpoints do not re-inspect on every request.
    """
    cache_key = url or ""
    if url:
        reset_engine_cache()
        engine = get_engine(url)
    else:
        engine = get_engine()

    if cache_key in _READY:
        return engine

    insp = inspect(engine)
    if not insp.has_table("workspaces"):
        Base.metadata.create_all(engine)
    else:
        incremental = [
            "skills",
            "skill_versions",
            "node_types",
            "temporal_activities",
            "workflows",
            "workflow_versions",
            "workflow_stages",
            "workflow_connections",
            "executions",
            "execution_steps",
        ]
        missing = [
            Base.metadata.tables[name]
            for name in incremental
            if name in Base.metadata.tables and not insp.has_table(name)
        ]
        if missing:
            Base.metadata.create_all(engine, tables=missing)
    _READY.add(cache_key)
    return engine
