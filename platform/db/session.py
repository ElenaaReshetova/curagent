"""Engine and session factory for the platform database."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.platform.db.settings import database_url


@lru_cache(maxsize=4)
def get_engine(url: str | None = None) -> Engine:
    resolved = url or database_url()
    if not resolved:
        raise RuntimeError("PLATFORM_DATABASE_URL is not configured")
    connect_args: dict = {}
    if resolved.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(resolved, future=True, pool_pre_ping=True, connect_args=connect_args)

    if resolved.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_fk(dbapi_conn, _connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


@lru_cache(maxsize=4)
def get_session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url), autoflush=False, autocommit=False, future=True)


def reset_engine_cache() -> None:
    """Clear cached engines (tests)."""
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    from src.platform.db.schema import clear_schema_cache

    clear_schema_cache()
    try:
        from src.platform.skills.service import reset_skills_seed_cache

        reset_skills_seed_cache()
    except Exception:
        pass
    try:
        from src.platform.graphs.service import reset_graphs_seed_cache

        reset_graphs_seed_cache()
    except Exception:
        pass


@contextmanager
def session_scope(url: str | None = None) -> Iterator[Session]:
    factory = get_session_factory(url)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
