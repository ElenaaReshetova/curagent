"""Decision record, idempotency store, audit queries (AUD-001–AUD-010)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.tool_gateway.models.audit import DecisionRecord, ExecutionRecord
from src.tool_gateway.models.envelopes import NormalizedResult

logger = logging.getLogger(__name__)

_lock = threading.RLock()
_idempotency_cache: dict[str, NormalizedResult] = {}
_IDEMPOTENCY_TTL_SEC = int(os.environ.get("TOOL_GATEWAY_IDEMPOTENCY_TTL_SEC", "86400"))


def _audit_dir() -> Path:
    base = os.environ.get("TOOL_GATEWAY_AUDIT_DIR", "")
    if base:
        return Path(base).expanduser().resolve()
    return Path(__file__).resolve().parents[3] / "data" / "tool_gateway_audit"


def inputs_hash(inputs: dict[str, Any]) -> str:
    payload = json.dumps(inputs, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def persist_decision(record: DecisionRecord) -> None:
    """AUD-001: durable before dispatch/response."""
    audit_dir = _audit_dir()
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / "decisions" / f"{record.decision_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    log_path = audit_dir / "decisions.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")


def persist_execution(record: ExecutionRecord) -> None:
    audit_dir = _audit_dir()
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / "executions" / f"{record.execution_record_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")


def get_decision(decision_id: str) -> Optional[DecisionRecord]:
    path = _audit_dir() / "decisions" / f"{decision_id}.json"
    if not path.exists():
        return None
    return DecisionRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))


def list_recent_decisions(limit: int = 50) -> list[DecisionRecord]:
    log_path = _audit_dir() / "decisions.jsonl"
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    records: list[DecisionRecord] = []
    for line in reversed(lines[-limit:]):
        if not line.strip():
            continue
        try:
            records.append(DecisionRecord.model_validate(json.loads(line)))
        except Exception:
            continue
    return records


def replay_decision(decision_id: str) -> Optional[dict[str, Any]]:
    """AUD-008: reconstruct resolution outcome from Decision Record."""
    record = get_decision(decision_id)
    if record is None:
        return None
    return {
        "decision_id": record.decision_id,
        "accepted": record.accepted,
        "denial_code": record.denial_code,
        "capability_id": record.capability_id,
        "tenant_id": record.tenant_id,
        "trace_id": record.trace_id,
        "manifest_version": record.manifest_version,
        "policy_version": record.policy_version,
        "resolver_version": record.resolver_version,
        "registry_snapshot_id": record.registry_snapshot_id,
        "explainability": record.explainability,
        "timestamp": record.timestamp,
    }


def idempotency_key(tenant_id: str, capability_id: str, key: str) -> str:
    return f"{tenant_id}:{capability_id}:{key}"


def _idempotency_path(ik: str) -> Path:
    safe = hashlib.sha256(ik.encode()).hexdigest()
    return _audit_dir() / "idempotency" / f"{safe}.json"


def get_cached_result(tenant_id: str, capability_id: str, key: str) -> Optional[NormalizedResult]:
    ik = idempotency_key(tenant_id, capability_id, key)
    with _lock:
        mem = _idempotency_cache.get(ik)
        if mem:
            return mem.model_copy(update={"cached": True})
    path = _idempotency_path(ik)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        saved_at = data.get("saved_at", 0)
        if datetime.now(timezone.utc).timestamp() - saved_at > _IDEMPOTENCY_TTL_SEC:
            path.unlink(missing_ok=True)
            return None
        result = NormalizedResult.model_validate(data["result"])
        with _lock:
            _idempotency_cache[ik] = result
        return result.model_copy(update={"cached": True})
    except Exception:
        return None


def cache_result(tenant_id: str, capability_id: str, key: str, result: NormalizedResult) -> None:
    ik = idempotency_key(tenant_id, capability_id, key)
    with _lock:
        _idempotency_cache[ik] = result
    path = _idempotency_path(ik)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "saved_at": datetime.now(timezone.utc).timestamp(),
        "result": result.model_dump(),
    }, default=str), encoding="utf-8")


def new_decision_id() -> str:
    return str(uuid.uuid4())


def new_tool_call_id() -> str:
    return str(uuid.uuid4())


def new_execution_id() -> str:
    return str(uuid.uuid4())
