"""Executions persistence, catalog, and inspector detail."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.platform.domain.models import Execution
from src.platform.executions.models import (
    ArtifactRef,
    EvidenceRef,
    ExecutionCatalogItem,
    ExecutionMetrics,
    ExecutionRecord,
    StageRun,
    TimelineEvent,
)
from src.platform.executions.validation import validate_record
from src.platform.store import append_audit, get_execution, get_platform_dir, list_executions, save_execution

logger = logging.getLogger(__name__)
_SEEDING = False

LEGACY_STATUS_MAP = {
    "running": "RUNNING",
    "waiting_approval": "WAITING_FOR_HUMAN",
    "blocked": "PAUSED",
    "completed": "COMPLETED",
    "failed": "FAILED",
    "cancelled": "CANCELLED",
    "received": "QUEUED",
    "compiling": "STARTING",
}

REVERSE_STATUS_MAP = {
    "RUNNING": "running",
    "WAITING_FOR_HUMAN": "waiting_approval",
    "PAUSED": "blocked",
    "COMPLETED": "completed",
    "FAILED": "failed",
    "CANCELLED": "cancelled",
    "QUEUED": "received",
    "STARTING": "compiling",
}


def _path(name: str) -> Path:
    return get_platform_dir() / name


def _read_json(name: str, default: Any) -> Any:
    path = _path(name)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed reading %s: %s", path, e)
        return default


def _write_json(name: str, payload: Any) -> None:
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def ensure_executions_seeded() -> None:
    global _SEEDING
    marker = _path(".seeded_executions_v1")
    if marker.exists() and _path("execution_records.json").exists():
        return
    if _SEEDING:
        return
    _SEEDING = True
    try:
        _seed_unlocked()
    finally:
        _SEEDING = False


def _seed_unlocked() -> None:
    marker = _path(".seeded_executions_v1")
    if marker.exists() and _path("execution_records.json").exists():
        return

    # No demo executions — metrics come from real runs only.
    _write_json("execution_records.json", {"executions": []})
    marker.write_text(datetime.utcnow().isoformat() + "\n", encoding="utf-8")
    logger.info("Executions module seeded (0 records)")


def list_records() -> list[ExecutionRecord]:
    ensure_executions_seeded()
    raw = _read_json("execution_records.json", {"executions": []}).get("executions", [])
    return [ExecutionRecord.model_validate(x) for x in raw]


def _save_records(items: list[ExecutionRecord]) -> None:
    _write_json("execution_records.json", {"executions": [i.model_dump(mode="json") for i in items]})


def get_record(execution_id: str) -> ExecutionRecord | None:
    for r in list_records():
        if r.id == execution_id or r.legacy_store_id == execution_id:
            return r
    return None


def _legacy_to_catalog(ex: Execution) -> ExecutionCatalogItem:
    status = LEGACY_STATUS_MAP.get(ex.status, ex.status.upper())
    source = f"{ex.external_source.upper()} {ex.external_work_item_id}"
    progress = 100 if ex.status == "completed" else (75 if ex.status == "running" else 50)
    cost = ex.budget_usage.get("cost_usd", 0) if ex.budget_usage else 0
    return ExecutionCatalogItem(
        id=ex.id,
        title=ex.reason or ex.playbook_name,
        source=source,
        flow_name=ex.flow_key or ex.playbook_name,
        current_stage=ex.stage or ex.current_operator_key or "—",
        progress_pct=progress,
        status=status,
        duration="—",
        cost=f"${cost:.2f}" if cost else "—",
        risk_level="MEDIUM",
        execution_type="PLAYBOOK" if not ex.flow_key else "FLOW",
        started_at=ex.started_at,
    )


def _legacy_to_record(ex: Execution) -> ExecutionRecord:
    return ExecutionRecord(
        id=ex.id,
        title=ex.reason or ex.playbook_name,
        execution_type="FLOW" if ex.flow_key else "PLAYBOOK",
        source_type=ex.external_source.upper(),
        source_ref=ex.external_work_item_id,
        flow_key=ex.flow_key or "",
        flow_name=ex.flow_key or ex.playbook_name,
        playbook_key=ex.playbook_key,
        playbook_name=ex.playbook_name,
        current_stage=ex.stage or ex.current_operator_key or "",
        progress_pct=100 if ex.status == "completed" else 50,
        status=LEGACY_STATUS_MAP.get(ex.status, "RUNNING"),  # type: ignore[arg-type]
        duration="—",
        cost_usd=float(ex.budget_usage.get("cost_usd", 0) or 0),
        tokens=int(ex.budget_usage.get("llm_tokens", 0) or 0),
        evidence_count=len(ex.evidence),
        artifacts_count=len(ex.artifact_facets),
        current_activity=ex.current_operator_key or "",
        stage_runs=[
            StageRun(key=str(i), name=step.get("operator_key", f"step-{i}"), status="COMPLETED" if step.get("status") == "done" else "RUNNING")  # type: ignore[arg-type]
            for i, step in enumerate(ex.plan)
        ],
        timeline=[
            TimelineEvent(at=item.get("at", ""), title=item.get("event", "event"), detail=item.get("operator", ""), actor="System")
            for item in ex.audit_trail
        ],
        artifacts=[ArtifactRef(name=f.key, version="v1", status=f.status) for f in ex.artifact_facets[:5]],
        evidence=[EvidenceRef(title=e.summary, source=f"{e.source_type} · {e.source_ref}", score=0.8) for e in ex.evidence[:5]],
        runtime_effective={"profile": ex.agent_key, "playbook": ex.playbook_name},
        snapshot={"playbookVersion": ex.playbook_version, "contractVersion": ex.contract_version},
        logs="\n".join(f"{t.at} {t.title}: {t.detail}" for t in [
            TimelineEvent(at=item.get("at", ""), title=item.get("event", ""), detail=item.get("operator", ""))
            for item in ex.audit_trail
        ]),
        legacy_store_id=ex.id,
        started_at=ex.started_at,
        updated_at=ex.updated_at,
    )


_SUCCESS_STATUSES = frozenset({"COMPLETED", "COMPLETED_WITH_WARNINGS"})
_ACTIVE_STATUSES = frozenset({
    "CREATED", "QUEUED", "STARTING", "RUNNING",
    "WAITING_FOR_EVENT", "WAITING_FOR_HUMAN", "PAUSED",
    "CANCELLING", "COMPENSATING",
})
# Old Slack playbook spine — must not mix with published graph nodes.
# `publish` is also a real AI PDLC node id, so it is not in this set.
LEGACY_PLAYBOOK_STAGE_KEYS = frozenset({
    "intake", "classify", "brd", "srd", "approval",
})


def _canonical_stage_key(stages: list[StageRun], stage_key: str) -> str:
    keys = {s.key for s in stages}
    if stage_key in keys:
        return stage_key
    if stage_key.startswith("approval-"):
        rest = stage_key[len("approval-"):]
        if rest in keys:
            return rest
        if "review" in keys:
            return "review"
    return stage_key


def _drop_legacy_playbook_stages(stages: list[StageRun]) -> list[StageRun]:
    return [s for s in stages if s.key not in LEGACY_PLAYBOOK_STAGE_KEYS]


def _apply_stage_status(
    stages: list[StageRun],
    stage_key: str,
    stage_status: str,
    *,
    stage_name: str | None = None,
) -> list[StageRun]:
    key = _canonical_stage_key(stages, stage_key)
    graphish = key not in LEGACY_PLAYBOOK_STAGE_KEYS and not key.startswith("approval-")
    if graphish and any(s.key in LEGACY_PLAYBOOK_STAGE_KEYS for s in stages):
        stages = _drop_legacy_playbook_stages(stages)
        key = _canonical_stage_key(stages, stage_key)
    if stage_status == "RUNNING":
        for other in stages:
            if other.key != key and other.status == "RUNNING":
                other.status = "COMPLETED"  # type: ignore[assignment]
    found = False
    for stage in stages:
        if stage.key != key:
            continue
        stage.status = stage_status  # type: ignore[assignment]
        if stage_name:
            stage.name = stage_name
        found = True
        break
    if not found:
        if key.startswith("approval-") and any(
            s.key not in LEGACY_PLAYBOOK_STAGE_KEYS for s in stages
        ):
            return stages
        stages.append(StageRun(key=key, name=stage_name or key, status=stage_status))  # type: ignore[arg-type]
    return stages


def _finalize_stages(stages: list[StageRun], status: str | None) -> None:
    if status not in {"COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED"}:
        return
    for stage in stages:
        if stage.status == "RUNNING":
            stage.status = "FAILED" if status == "FAILED" else "COMPLETED"  # type: ignore[assignment]
        elif stage.status == "NOT_STARTED":
            stage.status = "SKIPPED"  # type: ignore[assignment]


def _progress_from_stages(stages: list[StageRun]) -> int:
    if not stages:
        return 0
    done = sum(1 for s in stages if s.status in {"COMPLETED", "SKIPPED", "FAILED"})
    return min(99, int(round(100 * done / len(stages)))) or (5 if done else 0)
def usage_stats(*, days: int = 30) -> dict[str, dict[str, dict[str, Any]]]:
    """Aggregate real execution usage for the last N days.

    Returns indexes keyed by flow / playbook / skill with:
      count, active, completed, failed, success_rate (0..1),
      success_rate_pct (0..100), avg_duration.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    indexes: dict[str, dict[str, dict[str, Any]]] = {
        "flow": {},
        "playbook": {},
        "skill": {},
    }

    def _bucket(kind: str, key: str) -> dict[str, Any]:
        key = (key or "").strip()
        if not key:
            return {}
        bucket = indexes[kind].get(key)
        if bucket is None:
            bucket = {
                "count": 0,
                "active": 0,
                "completed": 0,
                "failed": 0,
                "durations": [],
                "success_rate": 0.0,
                "success_rate_pct": 0.0,
                "avg_duration": "—",
            }
            indexes[kind][key] = bucket
        return bucket

    def _observe(bucket: dict[str, Any], rec: ExecutionRecord) -> None:
        if not bucket:
            return
        bucket["count"] += 1
        if rec.status in _ACTIVE_STATUSES:
            bucket["active"] += 1
        if rec.status in _SUCCESS_STATUSES:
            bucket["completed"] += 1
        if rec.status in ("FAILED", "TIMED_OUT"):
            bucket["failed"] += 1
        if rec.duration and rec.duration not in ("", "—", "0m"):
            bucket["durations"].append(rec.duration)

    for rec in list_records():
        started = rec.started_at
        if started and started.replace(tzinfo=None) < cutoff:
            continue
        _observe(_bucket("flow", rec.flow_key), rec)
        _observe(_bucket("playbook", rec.playbook_key), rec)
        _observe(_bucket("skill", rec.current_skill), rec)

    for kind in indexes:
        for bucket in indexes[kind].values():
            decided = bucket["completed"] + bucket["failed"]
            if decided:
                rate = bucket["completed"] / decided
                bucket["success_rate"] = round(rate, 3)
                bucket["success_rate_pct"] = round(rate * 100, 1)
            elif bucket["count"]:
                # In-flight only — no success yet.
                bucket["success_rate"] = 0.0
                bucket["success_rate_pct"] = 0.0
            durations = bucket.pop("durations")
            if durations:
                # Prefer the most common recorded duration string.
                bucket["avg_duration"] = max(set(durations), key=durations.count)
            else:
                bucket["avg_duration"] = "—"

    return indexes


def stats_for(kind: str, key: str, *, days: int = 30) -> dict[str, Any]:
    """Lookup usage stats for one flow / playbook / skill key."""
    empty = {
        "count": 0,
        "active": 0,
        "completed": 0,
        "failed": 0,
        "success_rate": 0.0,
        "success_rate_pct": 0.0,
        "avg_duration": "—",
    }
    if not key:
        return empty
    return usage_stats(days=days).get(kind, {}).get(key, empty)


def metrics() -> ExecutionMetrics:
    items = catalog_items()
    running = sum(1 for i in items if i.status == "RUNNING")
    waiting = sum(1 for i in items if i.status == "WAITING_FOR_HUMAN")
    failed = sum(1 for i in items if i.status == "FAILED")
    completed = sum(1 for i in items if i.status in _SUCCESS_STATUSES)
    decided = completed + failed
    return ExecutionMetrics(
        running=running,
        waiting_human=waiting,
        completed_today=completed,
        success_rate_pct=round(completed / decided * 100, 1) if decided else 0.0,
        failed=failed,
        retryable=sum(1 for i in items if i.status == "FAILED"),
    )


def catalog_items(
    search: str = "",
    status: str = "",
    execution_type: str = "",
    risk: str = "",
) -> list[ExecutionCatalogItem]:
    items: list[ExecutionCatalogItem] = []
    seen: set[str] = set()

    for r in list_records():
        seen.add(r.id)
        if r.legacy_store_id:
            seen.add(r.legacy_store_id)
        blob = f"{r.id} {r.title} {r.source_ref} {r.flow_name}".lower()
        if search and search.lower() not in blob:
            continue
        if status and status.upper() not in ("", "ALL") and r.status != status.upper():
            continue
        if execution_type and execution_type.upper() not in ("", "ALL") and r.execution_type != execution_type.upper():
            continue
        if risk and risk.upper() not in ("", "ALL") and r.risk_level != risk.upper():
            continue
        items.append(ExecutionCatalogItem(
            id=r.id,
            title=r.title,
            source=f"{r.source_type} {r.source_ref}".strip(),
            flow_name=r.flow_name or r.playbook_name,
            current_stage=r.current_stage,
            progress_pct=r.progress_pct,
            status=r.status,
            duration=r.duration,
            cost=f"${r.cost_usd:.2f}",
            risk_level=r.risk_level,
            execution_type=r.execution_type,
            started_at=r.started_at,
        ))

    for ex in list_executions():
        if ex.id in seen:
            continue
        cat = _legacy_to_catalog(ex)
        blob = f"{cat.id} {cat.title} {cat.source} {cat.flow_name}".lower()
        if search and search.lower() not in blob:
            continue
        if status and status.upper() not in ("", "ALL") and cat.status != status.upper():
            continue
        if execution_type and execution_type.upper() not in ("", "ALL") and cat.execution_type != execution_type.upper():
            continue
        if risk and risk.upper() not in ("", "ALL") and cat.risk_level != risk.upper():
            continue
        items.append(cat)

    items.sort(
        key=lambda x: x.started_at or datetime.min,
        reverse=True,
    )
    return items


def detail(execution_id: str) -> dict[str, Any]:
    rec = get_record(execution_id)
    if rec:
        # Backfill graph linkage from snapshot / temporal workflow id
        snap = dict(rec.snapshot or {})
        wf = str(snap.get("temporal_workflow_id") or "")
        if not rec.graph_run_id:
            if snap.get("graph_run_id"):
                rec.graph_run_id = str(snap["graph_run_id"])
            elif wf.startswith("graph-run-"):
                rec.graph_run_id = wf[len("graph-run-"):]
        if not rec.graph_id and snap.get("graph_id"):
            rec.graph_id = str(snap["graph_id"])
        if not rec.graph_version_id and snap.get("graph_version_id"):
            rec.graph_version_id = str(snap["graph_version_id"])
        report = validate_record(rec)
        return {
            "execution": rec.model_dump(mode="json"),
            "validation": report,
        }
    ex = get_execution(execution_id)
    if ex:
        rec = _legacy_to_record(ex)
        return {
            "execution": rec.model_dump(mode="json"),
            "validation": validate_record(rec),
            "legacy": True,
        }
    raise KeyError("Execution not found")


def save_record(rec: ExecutionRecord) -> ExecutionRecord:
    """Insert or replace a runtime execution record."""
    ensure_executions_seeded()
    records = [r for r in list_records() if r.id != rec.id]
    records.append(rec)
    _save_records(records)
    return rec


def patch_execution(
    execution_id: str,
    *,
    status: str | None = None,
    current_stage: str | None = None,
    current_activity: str | None = None,
    progress_pct: int | None = None,
    current_skill: str | None = None,
    playbook_key: str | None = None,
    playbook_name: str | None = None,
    timeline_event: TimelineEvent | None = None,
    snapshot_updates: dict[str, Any] | None = None,
    stage_key: str | None = None,
    stage_status: str | None = None,
    stage_name: str | None = None,
    replace_stage_runs: list[StageRun] | None = None,
    flow_key: str | None = None,
    flow_name: str | None = None,
) -> ExecutionRecord | None:
    ensure_executions_seeded()
    records = list_records()
    target: ExecutionRecord | None = None
    for r in records:
        if r.id != execution_id:
            continue
        if status:
            r.status = status  # type: ignore[assignment]
        if current_stage is not None:
            r.current_stage = current_stage
        if current_activity is not None:
            r.current_activity = current_activity
        if current_skill is not None:
            r.current_skill = current_skill
        if playbook_key is not None:
            r.playbook_key = playbook_key
        if playbook_name is not None:
            r.playbook_name = playbook_name
        if flow_key is not None:
            r.flow_key = flow_key
        if flow_name is not None:
            r.flow_name = flow_name
        if timeline_event is not None:
            r.timeline.append(timeline_event)
        if snapshot_updates:
            snap = dict(r.snapshot or {})
            snap.update(snapshot_updates)
            r.snapshot = snap
            if snap.get("graph_id"):
                r.graph_id = str(snap["graph_id"])
            if snap.get("graph_run_id"):
                r.graph_run_id = str(snap["graph_run_id"])
            if snap.get("graph_version_id"):
                r.graph_version_id = str(snap["graph_version_id"])
            # Derive graph_run_id from Temporal workflow id when present
            wf = str(snap.get("temporal_workflow_id") or "")
            if not r.graph_run_id and wf.startswith("graph-run-"):
                r.graph_run_id = wf[len("graph-run-"):]
                snap["graph_run_id"] = r.graph_run_id
                r.snapshot = snap
        if replace_stage_runs is not None:
            r.stage_runs = list(replace_stage_runs)
        if stage_key and stage_status:
            r.stage_runs = _apply_stage_status(
                list(r.stage_runs),
                stage_key,
                stage_status,
                stage_name=stage_name,
            )
        _finalize_stages(r.stage_runs, status)
        if progress_pct is not None:
            r.progress_pct = progress_pct
        elif status in {"COMPLETED", "COMPLETED_WITH_WARNINGS"}:
            r.progress_pct = 100
        elif status == "FAILED":
            r.progress_pct = r.progress_pct or 100
        elif status != "WAITING_FOR_HUMAN" and r.stage_runs:
            r.progress_pct = _progress_from_stages(r.stage_runs)
        r.updated_at = datetime.utcnow()
        target = r
        break
    if target:
        _save_records(records)
    return target


def create_execution(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_executions_seeded()
    now = datetime.utcnow()
    seq = len(list_records()) + 183
    eid = f"EXE-2026-{seq:06d}"
    rec = ExecutionRecord(
        id=eid,
        title=payload.get("title") or "New execution",
        execution_type=(payload.get("execution_type") or payload.get("type") or "FLOW").upper(),  # type: ignore[arg-type]
        source_type=(payload.get("source_type") or "MANUAL").upper(),
        source_ref=payload.get("source_ref") or payload.get("reference") or "MAN-NEW",
        flow_name=payload.get("flow_name") or payload.get("flow") or "Feature Delivery",
        flow_key=payload.get("flow_key") or "feature-delivery",
        current_stage="Starting",
        progress_pct=2,
        status="RUNNING",
        risk_level="MEDIUM",
        duration="0m",
        cost_usd=0.0,
        current_activity="Initializing snapshot",
        stage_runs=[StageRun(key="start", name="Starting", status="RUNNING")],
        timeline=[TimelineEvent(at=now.strftime("%H:%M:%S"), title="Execution started", detail=payload.get("flow_name", "Feature Delivery"))],
        runtime_effective={"profile": "Qwen Production v2.0.0"},
        snapshot={"flowVersion": payload.get("flow_name", "Feature Delivery")},
        started_at=now,
        updated_at=now,
    )
    _save_records(list_records() + [rec])
    append_audit("create", "execution", rec.id, f"Started execution {rec.id}")
    return detail(rec.id)


def set_status(execution_id: str, status: str, reason: str = "") -> dict[str, Any]:
    rec = get_record(execution_id)
    if rec:
        records = list_records()
        for r in records:
            if r.id == rec.id:
                r.status = status  # type: ignore[assignment]
                r.updated_at = datetime.utcnow()
                if reason:
                    r.timeline.append(TimelineEvent(
                        at=datetime.utcnow().strftime("%H:%M:%S"),
                        title=f"Status → {status}",
                        detail=reason,
                        actor="Operator",
                    ))
                break
        _save_records(records)
        ex = next(r for r in records if r.id == rec.id)
        payload = ex.model_dump(mode="json")
        payload["status"] = REVERSE_STATUS_MAP.get(status, status.lower())
        return payload

    legacy_status = REVERSE_STATUS_MAP.get(status, status.lower())
    ex = get_execution(execution_id)
    if not ex:
        raise KeyError("Execution not found")
    ex.status = legacy_status  # type: ignore[assignment]
    ex.reason = reason or ex.reason
    ex.updated_at = datetime.utcnow()
    ex.audit_trail.append({
        "at": datetime.utcnow().isoformat(),
        "event": f"status.{legacy_status}",
        "actor": "operator",
    })
    save_execution(ex)
    detail_payload = _legacy_to_record(ex).model_dump(mode="json")
    detail_payload["status"] = legacy_status
    return detail_payload


def status_response(execution_id: str, status: str, reason: str) -> dict[str, Any]:
    payload = set_status(execution_id, status, reason)
    if "execution" in payload:
        ex = payload["execution"]
        legacy = REVERSE_STATUS_MAP.get(status, status.lower())
        return {**ex, "status": legacy}
    return payload
