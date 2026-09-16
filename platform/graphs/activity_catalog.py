"""workflow node type → Temporal worker (activity) name.

`temporal_activities.worker` is the Temporal activity registered on the
platform worker (`http_webhook`, `ai_agent_execute`, …). YAML calls this
field `worker`. It is not Temporal's own database.

Parser and seed share DEFAULT_BINDINGS. When PLATFORM_DATABASE_URL is set,
bindings are loaded from `node_types` + `temporal_activities`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.platform.graphs.workflow_dsl import _CANVAS_TYPE, _CANVAS_TO_CONFIG


@dataclass(frozen=True)
class NodeWorkerBinding:
    key: str
    family: str
    port_type: str
    worker: str
    wait_for_signal: bool = False


DEFAULT_BINDINGS: tuple[NodeWorkerBinding, ...] = (
    NodeWorkerBinding("trigger", "Trigger", "SELF_SERVE_TRIGGER", ""),
    NodeWorkerBinding("ai_agent", "Activity", "AI_AGENT", "ai_agent_execute"),
    NodeWorkerBinding("ai", "Activity", "AI", "ai_generate_summary"),
    NodeWorkerBinding("webhook", "Activity", "WEBHOOK", "http_webhook"),
    NodeWorkerBinding("upsert_entity", "Activity", "UPSERT_ENTITY", "upsert_entity"),
    NodeWorkerBinding("kafka", "Activity", "KAFKA", "kafka_publish"),
    NodeWorkerBinding("integration_action", "Activity", "INTEGRATION_ACTION", "integration_action"),
    NodeWorkerBinding("internal_service", "Activity", "INTERNAL_SERVICE", "internal_service"),
    NodeWorkerBinding("subflow", "Activity", "SUBFLOW", "execute_subflow"),
    NodeWorkerBinding("condition", "Condition", "CONDITION", ""),
    NodeWorkerBinding("input", "Input", "INPUT", "human_review", wait_for_signal=True),
)

_CACHE: dict[str, NodeWorkerBinding] | None = None
_CACHE_BY_KEY: dict[str, NodeWorkerBinding] | None = None
_CACHE_PG: bool | None = None


def reset_activity_catalog_cache() -> None:
    global _CACHE, _CACHE_BY_KEY, _CACHE_PG
    _CACHE = None
    _CACHE_BY_KEY = None
    _CACHE_PG = None


def _index_defaults() -> tuple[dict[str, NodeWorkerBinding], dict[str, NodeWorkerBinding]]:
    by_port = {b.port_type.upper(): b for b in DEFAULT_BINDINGS}
    by_key = {b.key.lower(): b for b in DEFAULT_BINDINGS}
    return by_port, by_key


def _load_db_bindings() -> list[NodeWorkerBinding] | None:
    try:
        from src.platform.db.settings import workflows_use_postgres

        if not workflows_use_postgres():
            return None
        from src.platform.db.session import session_scope
        from src.platform.graphs.repository import WorkflowsRepository

        with session_scope() as session:
            repo = WorkflowsRepository(session)
            repo.ensure_node_types()
            return repo.list_worker_bindings()
    except Exception:
        return None


def _ensure_index() -> tuple[dict[str, NodeWorkerBinding], dict[str, NodeWorkerBinding]]:
    global _CACHE, _CACHE_BY_KEY, _CACHE_PG
    from src.platform.db.settings import workflows_use_postgres

    pg = workflows_use_postgres()
    if _CACHE is not None and _CACHE_BY_KEY is not None and _CACHE_PG is pg:
        return _CACHE, _CACHE_BY_KEY
    by_port, by_key = _index_defaults()
    loaded = _load_db_bindings() if pg else None
    if loaded:
        for b in loaded:
            if b.port_type:
                by_port[b.port_type.upper()] = b
            if b.key:
                by_key[b.key.lower()] = b
            if b.worker:
                by_key[b.worker.lower()] = b
    _CACHE, _CACHE_BY_KEY, _CACHE_PG = by_port, by_key, pg
    return by_port, by_key


def resolve_worker(type_or_key: str) -> Optional[NodeWorkerBinding]:
    """Resolve `config.type` or canvas key to a Temporal worker binding."""
    raw = (type_or_key or "").strip()
    if not raw:
        return None
    by_port, by_key = _ensure_index()
    upper = raw.upper()
    lower = raw.lower()
    if upper in by_port:
        return by_port[upper]
    if lower in by_key:
        return by_key[lower]
    canvas = _CANVAS_TYPE.get(upper)
    if canvas and canvas.lower() in by_key:
        return by_key[canvas.lower()]
    if lower in _CANVAS_TO_CONFIG:
        return by_key.get(lower)
    return None


def list_bindings() -> list[NodeWorkerBinding]:
    by_port, by_key = _ensure_index()
    seen: dict[str, NodeWorkerBinding] = {}
    for b in list(by_key.values()) + list(by_port.values()):
        seen[b.key] = b
    return list(seen.values())
