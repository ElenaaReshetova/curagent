"""Controls persistence, catalog, validation, and resolution preview."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

from src.platform.controls.models import (
    ApplicabilityCondition,
    ControlCatalogItem,
    ControlEvaluationRecord,
    ControlExceptionRecord,
    ControlMetrics,
    ControlRecord,
    ControlVersion,
    ControlViolationRecord,
    ViolationRef,
)
from src.platform.controls.validation import validate_version
from src.platform.store import append_audit, get_platform_dir, list_controls

_NS_OPS = UUID("d5e6f7a8-9b0c-4d1e-8f2a-3b4c5d6e7f80")

_CONTROL_SEEDS = [
    {
        "key": "human-approval-before-publication",
        "name": "Human approval before publication",
        "description": "Published system artifacts require an approved checkpoint.",
        "control_type": "PUBLICATION_GATE",
        "severity": "HIGH",
        "enforcement_on_failed": "REQUIRE_HUMAN_APPROVAL",
        "status": "ACTIVE",
        "evaluation_point": "BEFORE_ARTIFACT_PUBLICATION",
        "expression": 'context.checkpoint.status == "APPROVED"',
        "applicability": [
            ApplicabilityCondition(field="environment", value="PRODUCTION"),
            ApplicabilityCondition(field="artifact.type", value="SYSTEM_REQUIREMENTS"),
        ],
        "pass_rate_pct": 98.7,
        "violations_count": 3,
        "violations": [
            ViolationRef(execution_id="EXE-2026-004166", summary="Approval evidence missing"),
            ViolationRef(execution_id="EXE-2026-004121", summary="Rollback section missing", status="IN REMEDIATION"),
        ],
        "remediation_steps": ["Request checkpoint approval", "Attach decision record to artifact"],
        "exceptions": 1,
    },
    {
        "key": "eu-restricted-processing",
        "name": "EU processing for restricted data",
        "description": "Restricted data must be processed only in approved EU regions.",
        "control_type": "DATA_RESIDENCY",
        "severity": "CRITICAL",
        "enforcement_on_failed": "BLOCK",
        "status": "ACTIVE",
        "evaluation_point": "BEFORE_EXECUTION",
        "expression": 'context.runtime.region in ["EU-WEST", "EU-CENTRAL"]',
        "applicability": [ApplicabilityCondition(field="data.classification", value="RESTRICTED")],
        "pass_rate_pct": 99.9,
        "violations_count": 1,
        "violations": [
            ViolationRef(execution_id="EXE-2026-004088", summary="Runtime region US-EAST-1"),
        ],
    },
    {
        "key": "no-unrestricted-network",
        "name": "No unrestricted production network",
        "description": "Production runtime profiles cannot use unrestricted network access.",
        "control_type": "SECURITY",
        "severity": "CRITICAL",
        "enforcement_on_failed": "BLOCK",
        "status": "ACTIVE",
        "evaluation_point": "BEFORE_EXECUTION",
        "expression": 'context.runtime.network != "UNRESTRICTED"',
        "applicability": [ApplicabilityCondition(field="environment", value="PRODUCTION")],
        "pass_rate_pct": 99.4,
        "violations_count": 2,
        "violations": [
            ViolationRef(execution_id="EXE-2026-004055", summary="Unrestricted network profile"),
            ViolationRef(execution_id="EXE-2026-004031", summary="Egress policy missing", status="RESOLVED"),
        ],
    },
    {
        "key": "minimum-evidence-coverage",
        "name": "Minimum evidence coverage",
        "description": "Artifacts must be supported by sufficient fresh evidence.",
        "control_type": "QUALITY_GATE",
        "severity": "MEDIUM",
        "enforcement_on_failed": "WARN",
        "status": "ACTIVE",
        "evaluation_point": "AFTER_GRAPH",
        "expression": "context.evidence.count >= 5",
        "applicability": [ApplicabilityCondition(field="artifact.type", value="SYSTEM_REQUIREMENTS")],
        "pass_rate_pct": 94.2,
        "violations_count": 8,
        "violations": [
            ViolationRef(execution_id="EXE-2026-004201", summary="Only 2 evidence items linked"),
            ViolationRef(execution_id="EXE-2026-004198", summary="Evidence older than 90 days"),
        ],
    },
    {
        "key": "execution-cost-ceiling",
        "name": "Execution cost ceiling",
        "description": "Pause executions that exceed the approved cost ceiling.",
        "control_type": "COST_LIMIT",
        "severity": "HIGH",
        "enforcement_on_failed": "PAUSE_EXECUTION",
        "status": "DRAFT",
        "evaluation_point": "CONTINUOUS",
        "expression": "context.execution.cost_usd <= context.budget.max_usd",
        "applicability": [ApplicabilityCondition(field="environment", value="PRODUCTION")],
        "pass_rate_pct": 0.0,
        "violations_count": 0,
    },
    {
        "key": "legacy-schema-gate",
        "name": "Legacy artifact schema gate",
        "description": "Legacy schema validation retained for historical executions.",
        "control_type": "ARTIFACT_VALIDATION",
        "severity": "LOW",
        "enforcement_on_failed": "WARN",
        "status": "DEPRECATED",
        "evaluation_point": "BEFORE_ARTIFACT_PUBLICATION",
        "expression": "context.artifact.schema_valid == true",
        "applicability": [ApplicabilityCondition(field="artifact.legacy", value="true")],
        "pass_rate_pct": 91.0,
        "violations_count": 0,
    },
]


def _blocking_enforcement(enforcement: str) -> bool:
    return enforcement.upper() in {"BLOCK", "REQUIRE_HUMAN_APPROVAL", "PAUSE_EXECUTION", "FAIL_EXECUTION"}


def _normalize_violation_status(raw: str) -> str:
    cleaned = (raw or "OPEN").strip().upper().replace(" ", "_")
    if cleaned in {"OPEN", "IN_REMEDIATION", "RESOLVED", "ACCEPTED_RISK"}:
        return cleaned
    if cleaned == "IN_REMEDIATION":
        return "IN_REMEDIATION"
    return "OPEN"


def _list_evaluations(control_key: str | None = None) -> list[ControlEvaluationRecord]:
    ensure_control_ops_seeded()
    items = [
        ControlEvaluationRecord.model_validate(x)
        for x in _read_json("control_evaluations.json", {"evaluations": []}).get("evaluations", [])
    ]
    if control_key:
        return [e for e in items if e.control_key == control_key]
    return items


def _save_evaluations(items: list[ControlEvaluationRecord]) -> None:
    _write_json("control_evaluations.json", {
        "evaluations": [i.model_dump(mode="json") for i in items],
    })


def _list_violation_records(control_key: str | None = None) -> list[ControlViolationRecord]:
    ensure_control_ops_seeded()
    raw = _read_json("control_violations.json", {"violations": []})
    blob = raw.get("violations", [])
    if isinstance(blob, dict):
        items: list[ControlViolationRecord] = []
        for key, rows in blob.items():
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                items.append(ControlViolationRecord(
                    id=uuid5(_NS_OPS, f"legacy:{key}:{row.get('execution_id', '')}"),
                    control_key=key,
                    execution_id=row.get("execution_id", ""),
                    summary=row.get("summary", ""),
                    status=_normalize_violation_status(row.get("status", "OPEN")),  # type: ignore[arg-type]
                    blocking=True,
                ))
        return [v for v in items if not control_key or v.control_key == control_key]
    items = [ControlViolationRecord.model_validate(x) for x in blob]
    if control_key:
        return [v for v in items if v.control_key == control_key]
    return items


def _save_violations(items: list[ControlViolationRecord]) -> None:
    _write_json("control_violations.json", {
        "violations": [i.model_dump(mode="json") for i in items],
    })


def _list_exceptions(control_key: str | None = None) -> list[ControlExceptionRecord]:
    ensure_control_ops_seeded()
    items = [
        ControlExceptionRecord.model_validate(x)
        for x in _read_json("control_exceptions.json", {"exceptions": []}).get("exceptions", [])
    ]
    if control_key:
        return [e for e in items if e.control_key == control_key]
    return items


def _save_exceptions(items: list[ControlExceptionRecord]) -> None:
    _write_json("control_exceptions.json", {
        "exceptions": [i.model_dump(mode="json") for i in items],
    })


def _open_violations(control_key: str | None = None) -> list[ControlViolationRecord]:
    open_statuses = {"OPEN", "IN_REMEDIATION"}
    return [v for v in _list_violation_records(control_key) if v.status in open_statuses]


def _active_exceptions(control_key: str | None = None) -> list[ControlExceptionRecord]:
    now = datetime.utcnow()
    active: list[ControlExceptionRecord] = []
    for ex in _list_exceptions(control_key):
        if ex.status != "ACTIVE":
            continue
        if ex.valid_until and ex.valid_until < now:
            continue
        active.append(ex)
    return active


def _relative_time(dt: datetime | None) -> str:
    if not dt:
        return "—"
    delta = datetime.utcnow() - dt
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return f"{seconds} сек. назад"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} мин. назад"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} ч. назад"
    days = hours // 24
    return f"{days} дн. назад"


def _stats_for_control(control_key: str, ver: ControlVersion | None = None) -> dict[str, Any]:
    evals = _list_evaluations(control_key)
    open_violations = _open_violations(control_key)
    today = datetime.utcnow().date()
    today_evals = [e for e in evals if e.evaluated_at.date() == today]
    total = len(evals)
    passed = sum(1 for e in evals if e.result == "PASSED")
    last = max((e.evaluated_at for e in evals), default=None)
    enforcement = ver.enforcement_on_failed if ver else "BLOCK"
    return {
        "pass_rate_pct": round(100.0 * passed / total, 1) if total else 0.0,
        "violations_count": len(open_violations),
        "evaluations_today": len(today_evals),
        "evaluations_total": total,
        "last_evaluation_at": last,
        "last_evaluation": _relative_time(last),
        "blocking_violations": sum(1 for v in open_violations if v.blocking),
        "active_exceptions": len(_active_exceptions(control_key)),
    }


def _seed_operational_data(seeds: list[dict[str, Any]], records: list[ControlRecord], versions: list[ControlVersion]) -> None:
    key_to_ver: dict[str, ControlVersion] = {}
    for ver in versions:
        rec = next((r for r in records if r.id == ver.control_id), None)
        if rec:
            key_to_ver[rec.key] = ver

    evaluations: list[ControlEvaluationRecord] = []
    violations: list[ControlViolationRecord] = []
    exceptions: list[ControlExceptionRecord] = []
    now = datetime.utcnow()

    for seed in seeds:
        key = seed["key"]
        ver = key_to_ver.get(key)
        if not ver or seed.get("status") != "ACTIVE":
            continue
        pass_rate = float(seed.get("pass_rate_pct") or 0.0)
        total = 96 if seed.get("violations_count", 0) > 5 else 64
        fail_count = max(int(round(total * (100.0 - pass_rate) / 100.0)), int(seed.get("violations_count") or 0))
        enforcement = seed.get("enforcement_on_failed") or ver.enforcement_on_failed
        blocking_fail = _blocking_enforcement(enforcement)

        for i in range(total):
            days_ago = i % 30
            hours = (i * 5) % 24
            evaluated_at = now - timedelta(days=days_ago, hours=hours, minutes=(i * 3) % 60)
            is_pass = i >= fail_count
            if is_pass:
                result = "PASSED"
            elif enforcement == "WARN":
                result = "WARNING"
            else:
                result = "FAILED"
            evaluations.append(ControlEvaluationRecord(
                id=uuid5(_NS_OPS, f"eval:{key}:{i}"),
                control_key=key,
                control_version_id=ver.id,
                execution_id=f"EXE-2026-{400000 + (hash(key) % 1000) + i}",
                evaluation_point=ver.evaluation_point,
                result=result,  # type: ignore[arg-type]
                blocking=result == "FAILED" and blocking_fail,
                message="Control evaluation passed" if is_pass else "Control evaluation failed",
                duration_ms=40 + (i % 180),
                evaluated_at=evaluated_at,
            ))

        seen_exec: set[str] = set()
        for vref in seed.get("violations") or []:
            payload = vref.model_dump() if isinstance(vref, ViolationRef) else dict(vref)
            exec_id = payload.get("execution_id", "")
            status = _normalize_violation_status(payload.get("status", "OPEN"))
            violations.append(ControlViolationRecord(
                id=uuid5(_NS_OPS, f"viol:{key}:{exec_id}"),
                control_key=key,
                execution_id=exec_id,
                summary=payload.get("summary", ""),
                status=status,  # type: ignore[arg-type]
                blocking=blocking_fail and status in {"OPEN", "IN_REMEDIATION"},
                severity=ver.severity,
                first_detected_at=now - timedelta(days=3 + len(seen_exec)),
                last_detected_at=now - timedelta(hours=6 + len(seen_exec)),
                resolved_at=now - timedelta(days=1) if status == "RESOLVED" else None,
            ))
            seen_exec.add(exec_id)

        for ex_idx in range(int(seed.get("exceptions") or 0)):
            exceptions.append(ControlExceptionRecord(
                id=uuid5(_NS_OPS, f"exc:{key}:{ex_idx}"),
                control_key=key,
                reason="Temporary waiver for migration window",
                status="ACTIVE",
                valid_from=now - timedelta(days=14),
                valid_until=now + timedelta(days=5 + ex_idx * 3),
            ))

    _save_evaluations(evaluations)
    _save_violations(violations)
    _save_exceptions(exceptions)


def ensure_control_ops_seeded() -> None:
    _ensure_control_ops_seeded_unlocked()


def _ensure_control_ops_seeded_unlocked() -> None:
    marker = _path(".seeded_control_ops_v1")
    if marker.exists() and _path("control_evaluations.json").exists():
        return
    records_path = _path("control_records.json")
    if not records_path.exists():
        return
    records = [ControlRecord.model_validate(x) for x in _read_json("control_records.json", {"controls": []}).get("controls", [])]
    versions = [ControlVersion.model_validate(x) for x in _read_json("control_versions.json", {"versions": []}).get("versions", [])]
    if not records:
        return
    _seed_operational_data(_CONTROL_SEEDS, records, versions)
    marker.write_text(datetime.utcnow().isoformat() + "\n", encoding="utf-8")
    logger.info("Controls operational data seeded (evaluations, violations, exceptions)")


def record_evaluation(
    *,
    control_key: str,
    control_version: ControlVersion,
    result: str,
    message: str,
    execution_id: str | None = None,
    context: dict[str, Any] | None = None,
    duration_ms: int | None = None,
) -> ControlEvaluationRecord:
    ensure_control_ops_seeded()
    normalized = result.upper()
    if normalized not in {"PASSED", "FAILED", "WARNING", "ERROR"}:
        normalized = "PASSED" if normalized == "OK" else "FAILED"
    blocking = normalized == "FAILED" and _blocking_enforcement(control_version.enforcement_on_failed)
    ev = ControlEvaluationRecord(
        control_key=control_key,
        control_version_id=control_version.id,
        execution_id=execution_id or (context or {}).get("execution_id"),
        evaluation_point=control_version.evaluation_point,
        result=normalized,  # type: ignore[arg-type]
        blocking=blocking,
        message=message,
        duration_ms=duration_ms,
        evaluated_at=datetime.utcnow(),
    )
    evals = _list_evaluations()
    evals.append(ev)
    _save_evaluations(evals)

    if normalized in {"FAILED", "WARNING"} and execution_id:
        violations = _list_violation_records()
        violations.append(ControlViolationRecord(
            control_key=control_key,
            control_evaluation_id=ev.id,
            execution_id=execution_id,
            summary=message,
            status="OPEN",
            blocking=blocking,
            severity=control_version.severity,
        ))
        _save_violations(violations)
    return ev


logger = logging.getLogger(__name__)
NS = UUID("c4d5e6f7-8a9b-4c0d-9e1f-2a3b4c5d6e7f")
_SEEDING = False


def _id(kind: str, key: str) -> UUID:
    return uuid5(NS, f"{kind}:{key}")


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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def ensure_controls_seeded() -> None:
    global _SEEDING
    marker = _path(".seeded_controls_v1")
    if marker.exists() and _path("control_records.json").exists():
        _ensure_control_ops_seeded_unlocked()
        return
    if _SEEDING:
        return
    _SEEDING = True
    try:
        _seed_unlocked()
    finally:
        _SEEDING = False


def _seed_unlocked() -> None:
    marker = _path(".seeded_controls_v1")
    if marker.exists() and _path("control_records.json").exists():
        _ensure_control_ops_seeded_unlocked()
        return

    seeds = _CONTROL_SEEDS

    records: list[ControlRecord] = []
    versions: list[ControlVersion] = []
    for seed in seeds:
        rec = ControlRecord(
            id=_id("control", seed["key"]),
            key=seed["key"],
            name=seed["name"],
            description=seed["description"],
            owner_team="Governance Team",
            status="active" if seed["status"] == "ACTIVE" else ("deprecated" if seed["status"] == "DEPRECATED" else "draft"),
        )
        ver = ControlVersion(
            id=_id("cv", f"{seed['key']}-1.4.0"),
            control_id=rec.id,
            semantic_version="1.4.0",
            status=seed["status"],
            control_type=seed["control_type"],
            severity=seed["severity"],
            evaluation_point=seed["evaluation_point"],
            expression=seed["expression"],
            enforcement_on_failed=seed["enforcement_on_failed"],
            applicability=seed["applicability"],
            pass_rate_pct=seed["pass_rate_pct"],
            violations_count=seed["violations_count"],
            remediation_steps=seed.get("remediation_steps", []),
        )
        report = validate_version(ver)
        ver.validation_report = report
        ver.validation_status = report["status"]
        if seed["status"] == "ACTIVE":
            ver.activated_at = datetime.utcnow()
            rec.current_active_version_id = ver.id
        else:
            rec.current_draft_version_id = ver.id
        records.append(rec)
        versions.append(ver)

    _write_json("control_records.json", {"controls": [r.model_dump(mode="json") for r in records]})
    _write_json("control_versions.json", {"versions": [v.model_dump(mode="json") for v in versions]})
    _seed_operational_data(seeds, records, versions)
    marker.write_text(datetime.utcnow().isoformat() + "\n", encoding="utf-8")


def list_records() -> list[ControlRecord]:
    ensure_controls_seeded()
    return [ControlRecord.model_validate(x) for x in _read_json("control_records.json", {"controls": []}).get("controls", [])]


def list_versions(control_id: str | None = None) -> list[ControlVersion]:
    ensure_controls_seeded()
    items = [ControlVersion.model_validate(x) for x in _read_json("control_versions.json", {"versions": []}).get("versions", [])]
    if control_id:
        items = [v for v in items if str(v.control_id) == control_id]
    return items


def _save_records(items: list[ControlRecord]) -> None:
    _write_json("control_records.json", {"controls": [i.model_dump(mode="json") for i in items]})


def _save_versions(items: list[ControlVersion]) -> None:
    _write_json("control_versions.json", {"versions": [i.model_dump(mode="json") for i in items]})


def get_record(control_id: str) -> ControlRecord | None:
    for r in list_records():
        if str(r.id) == control_id or r.key == control_id:
            return r
    return None


def get_version(version_id: str) -> ControlVersion | None:
    for v in list_versions():
        if str(v.id) == version_id:
            return v
    return None


def _current_version(rec: ControlRecord) -> ControlVersion | None:
    if rec.current_active_version_id:
        active = get_version(str(rec.current_active_version_id))
        if active:
            return active
    if rec.current_draft_version_id:
        draft = get_version(str(rec.current_draft_version_id))
        if draft:
            return draft
    versions = list_versions(str(rec.id))
    return versions[0] if versions else None


def _draft_version(rec: ControlRecord) -> ControlVersion | None:
    if rec.current_draft_version_id:
        ver = get_version(str(rec.current_draft_version_id))
        if ver and ver.status == "DRAFT":
            return ver
    for ver in list_versions(str(rec.id)):
        if ver.status == "DRAFT":
            return ver
    return None


def _editable_version(rec: ControlRecord) -> ControlVersion | None:
    return _draft_version(rec) or _current_version(rec)


def _bump_patch(version: str) -> str:
    parts = [int(p) if p.isdigit() else 0 for p in str(version or "0.1.0").split(".")[:3]]
    while len(parts) < 3:
        parts.append(0)
    parts[2] += 1
    return f"{parts[0]}.{parts[1]}.{parts[2]}"


def _next_version_number(control_id: str) -> int:
    versions = list_versions(control_id)
    return (max((v.version_number for v in versions), default=0) + 1)


def metrics() -> ControlMetrics:
    ensure_control_ops_seeded()
    versions = list_versions()
    active = [v for v in versions if v.status == "ACTIVE"]
    all_evals = _list_evaluations()
    today = datetime.utcnow().date()
    today_evals = [e for e in all_evals if e.evaluated_at.date() == today]
    passed_all = sum(1 for e in all_evals if e.result == "PASSED")
    total_all = len(all_evals)
    open_violations = _open_violations()
    active_exceptions = _active_exceptions()
    week_later = datetime.utcnow() + timedelta(days=7)

    return ControlMetrics(
        active=len(active),
        critical=sum(1 for v in active if v.severity == "CRITICAL"),
        evaluations_today=len(today_evals),
        pass_rate_pct=round(100.0 * passed_all / total_all, 1) if total_all else 0.0,
        open_violations=len(open_violations),
        blocking_violations=sum(1 for v in open_violations if v.blocking),
        active_exceptions=len(active_exceptions),
        exceptions_expiring_week=sum(
            1 for ex in active_exceptions
            if ex.valid_until and ex.valid_until <= week_later
        ),
    )


def catalog_items(
    search: str = "",
    control_type: str = "",
    severity: str = "",
    status: str = "",
) -> list[ControlCatalogItem]:
    items: list[ControlCatalogItem] = []
    seen: set[str] = set()

    for rec in list_records():
        seen.add(rec.key)
        ver = _current_version(rec)
        if not ver:
            continue
        blob = f"{rec.name} {rec.key} {rec.description} {rec.owner_team}".lower()
        if search and search.lower() not in blob:
            continue
        if control_type and ver.control_type != control_type.upper():
            continue
        if severity and ver.severity != severity.upper():
            continue
        st = ver.status if ver.status in {"DRAFT", "DEPRECATED", "DISABLED"} else ("ACTIVE" if rec.status == "active" else rec.status.upper())
        if status and status.upper() not in ("", "ALL") and st != status.upper():
            continue
        stats = _stats_for_control(rec.key, ver)
        items.append(ControlCatalogItem(
            id=str(rec.id),
            key=rec.key,
            name=rec.name,
            description=rec.description,
            control_type=ver.control_type,
            severity=ver.severity,
            enforcement=ver.enforcement_on_failed,
            status=st,
            evaluation_point=ver.evaluation_point,
            version=ver.semantic_version,
            owner=rec.owner_team,
            violations_count=stats["violations_count"],
            pass_rate=f"{stats['pass_rate_pct']:.1f}%" if stats["evaluations_total"] else "—",
        ))

    for legacy in list_controls():
        if legacy.key in seen:
            continue
        blob = f"{legacy.name} {legacy.key}".lower()
        if search and search.lower() not in blob:
            continue
        legacy_type = "COMPLIANCE"
        legacy_severity = "HIGH" if legacy.enforcement == "hard" else "MEDIUM"
        legacy_status = legacy.status.upper()
        if control_type and legacy_type != control_type.upper():
            continue
        if severity and legacy_severity != severity.upper():
            continue
        if status and status.upper() not in ("", "ALL") and legacy_status != status.upper():
            continue
        items.append(ControlCatalogItem(
            id=str(legacy.id),
            key=legacy.key,
            name=legacy.name,
            description=f"{legacy.authority} · {legacy.enforcement} enforcement",
            control_type=legacy_type,
            severity=legacy_severity,
            enforcement="BLOCK" if legacy.enforcement == "hard" else "REQUIRE_HUMAN_APPROVAL",
            status=legacy_status,
            evaluation_point="BEFORE_EXECUTION",
            version="1.0.0",
            owner=legacy.authority,
            violations_count=0,
            pass_rate="—",
        ))
    items.sort(key=lambda x: x.key)
    return items


def _violations_for(key: str) -> list[Any]:
    return [
        {
            "execution_id": v.execution_id,
            "summary": v.summary,
            "status": v.status.replace("_", " "),
        }
        for v in _list_violation_records(key)
        if v.status in {"OPEN", "IN_REMEDIATION"}
    ]


def _slug_key(name: str) -> str:
    raw = (name or "").strip().lower()
    # Keep latin/digits; map common Cyrillic letters so RU names don't collapse to "".
    translit = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
        "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
        "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
        "я": "ya",
    }
    mapped = "".join(translit.get(ch, ch) for ch in raw)
    key = re.sub(r"[^a-z0-9]+", "-", mapped).strip("-")
    return key or f"control-{uuid4().hex[:8]}"


def detail(control_id: str) -> dict[str, Any]:
    rec = get_record(control_id)
    if not rec:
        raise KeyError("Control not found")
    versions = sorted(list_versions(str(rec.id)), key=lambda v: v.version_number, reverse=True)
    current = _current_version(rec)
    draft = _draft_version(rec)
    editable = draft or current
    violations = _violations_for(rec.key or "")
    stats = _stats_for_control(rec.key or "", current)
    return {
        "control": rec.model_dump(mode="json"),
        "current_version": current.model_dump(mode="json") if current else None,
        "draft_version": draft.model_dump(mode="json") if draft else None,
        "editable_version": editable.model_dump(mode="json") if editable else None,
        "versions": [
            {
                "id": str(v.id),
                "semantic_version": v.semantic_version,
                "status": v.status,
                "validation_status": v.validation_status,
            }
            for v in versions
        ],
        "violations": violations,
        "health": {
            "last_evaluation": stats["last_evaluation"],
            "pass_rate_pct": stats["pass_rate_pct"],
            "open_violations": stats["violations_count"],
            "active_exceptions": stats["active_exceptions"],
        },
    }


def create_control(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_controls_seeded()
    name = payload["name"]
    key = (payload.get("key") or "").strip() or _slug_key(name)
    if get_record(key):
        raise ValueError(f"Control key already exists: {key}")
    rec = ControlRecord(
        key=key,
        name=name,
        description=payload.get("description", ""),
        owner_team=payload.get("owner_team") or "Governance Team",
        status="draft",
    )
    ver = ControlVersion(
        control_id=rec.id,
        semantic_version="0.1.0",
        version_number=1,
        status="DRAFT",
        control_type=(payload.get("type") or payload.get("control_type") or "QUALITY_GATE").upper(),
        severity=(payload.get("severity") or "HIGH").upper(),
        evaluation_point=(payload.get("evaluation_point") or "AFTER_GRAPH").upper(),
        expression=payload.get("expression") or "true",
        enforcement_on_failed=(payload.get("enforcement") or payload.get("enforcement_on_failed") or "BLOCK").upper(),
        applicability=[ApplicabilityCondition(field="environment", value="PRODUCTION")],
        remediation_steps=list(payload.get("remediation_steps") or []),
    )
    report = validate_version(ver)
    ver.validation_report = report
    ver.validation_status = report["status"]
    rec.current_draft_version_id = ver.id
    _save_records(list_records() + [rec])
    _save_versions(list_versions() + [ver])
    append_audit("create", "control", str(rec.id), f"Created control {rec.key}")
    return detail(str(rec.id))


def create_draft(control_id: str) -> dict[str, Any]:
    rec = get_record(control_id)
    if not rec:
        raise KeyError("Control not found")
    existing = _draft_version(rec)
    if existing:
        return detail(str(rec.id))

    source = _current_version(rec)
    if not source:
        raise ValueError("No version to clone into draft")

    draft = source.model_copy(deep=True)
    draft.id = uuid4()
    draft.semantic_version = _bump_patch(source.semantic_version)
    draft.version_number = _next_version_number(str(rec.id))
    draft.status = "DRAFT"
    draft.activated_at = None
    draft.created_at = datetime.utcnow()
    draft.updated_at = datetime.utcnow()
    report = validate_version(draft)
    draft.validation_report = report
    draft.validation_status = report["status"]

    versions = list_versions()
    versions.append(draft)
    _save_versions(versions)

    records = list_records()
    for r in records:
        if str(r.id) == str(rec.id):
            r.current_draft_version_id = draft.id
            r.updated_at = datetime.utcnow()
            rec = r
            break
    _save_records(records)
    append_audit("create_draft", "control", str(rec.id), f"Draft {draft.semantic_version} for {rec.key}")
    return detail(str(rec.id))


def _parse_applicability(raw: Any) -> list[ApplicabilityCondition]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            # field=value lines
            items: list[ApplicabilityCondition] = []
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    field, _, value = line.partition("=")
                    items.append(ApplicabilityCondition(field=field.strip(), value=value.strip()))
            return items
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out: list[ApplicabilityCondition] = []
    for item in raw:
        if isinstance(item, ApplicabilityCondition):
            out.append(item)
        elif isinstance(item, dict):
            out.append(ApplicabilityCondition.model_validate(item))
    return out


def update_draft(control_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    rec = get_record(control_id)
    if not rec:
        raise KeyError("Control not found")

    draft = _draft_version(rec)
    if not draft:
        create_draft(str(rec.id))
        rec = get_record(control_id)
        if not rec:
            raise KeyError("Control not found")
        draft = _draft_version(rec)
    if not draft:
        raise ValueError("No draft version available")

    records = list_records()
    for r in records:
        if str(r.id) != str(rec.id):
            continue
        if "name" in payload and payload["name"]:
            r.name = str(payload["name"]).strip()
        if "description" in payload and payload["description"] is not None:
            r.description = str(payload["description"])
        if "owner_team" in payload and payload["owner_team"]:
            r.owner_team = str(payload["owner_team"])
        r.updated_at = datetime.utcnow()
        rec = r
        break
    _save_records(records)

    versions = list_versions()
    for idx, ver in enumerate(versions):
        if str(ver.id) != str(draft.id):
            continue
        if "control_type" in payload or "type" in payload:
            ver.control_type = str(payload.get("control_type") or payload.get("type") or ver.control_type).upper()
        if "severity" in payload and payload["severity"]:
            ver.severity = str(payload["severity"]).upper()
        if "evaluation_point" in payload and payload["evaluation_point"]:
            ver.evaluation_point = str(payload["evaluation_point"]).upper()
        if "expression" in payload and payload["expression"] is not None:
            ver.expression = str(payload["expression"])
        if "enforcement_on_failed" in payload or "enforcement" in payload:
            ver.enforcement_on_failed = str(
                payload.get("enforcement_on_failed") or payload.get("enforcement") or ver.enforcement_on_failed
            ).upper()
        if "applicability" in payload:
            ver.applicability = _parse_applicability(payload.get("applicability"))
        if "remediation_steps" in payload:
            steps = payload.get("remediation_steps")
            if isinstance(steps, str):
                ver.remediation_steps = [s.strip() for s in steps.splitlines() if s.strip()]
            elif isinstance(steps, list):
                ver.remediation_steps = [str(s).strip() for s in steps if str(s).strip()]
        ver.updated_at = datetime.utcnow()
        report = validate_version(ver)
        ver.validation_report = report
        ver.validation_status = report["status"]
        versions[idx] = ver
        draft = ver
        break
    _save_versions(versions)
    append_audit("update", "control", str(rec.id), f"Updated draft {draft.semantic_version}")
    return detail(str(rec.id))


def delete_control(control_id: str) -> dict[str, Any]:
    rec = get_record(control_id)
    if not rec:
        raise KeyError("Control not found")
    from src.platform.graphs.bindings import graphs_using_control

    consumers = graphs_using_control(rec.key)
    if consumers:
        raise ValueError(
            "Cannot delete: referenced in graphs "
            + ", ".join(consumers)
        )
    records = [r for r in list_records() if r.id != rec.id]
    versions = [v for v in list_versions() if str(v.control_id) != str(rec.id)]
    _save_records(records)
    _save_versions(versions)
    append_audit("delete", "control", str(rec.id), f"Deleted control {rec.key}")
    return {"ok": True, "id": str(rec.id), "key": rec.key}


def validate_control(control_id: str) -> dict[str, Any]:
    rec = get_record(control_id)
    if not rec:
        raise KeyError("Control not found")
    ver = _editable_version(rec)
    if not ver:
        return {"valid": False, "errors": ["No control version found"], "warnings": []}
    report = validate_version(ver)
    ver.validation_report = report
    ver.validation_status = report["status"]
    versions = list_versions()
    for idx, item in enumerate(versions):
        if item.id == ver.id:
            versions[idx] = ver
            break
    _save_versions(versions)
    return {
        "valid": report["valid"],
        "errors": [e["message"] for e in report.get("errors", [])],
        "warnings": [w["message"] for w in report.get("warnings", [])],
        "validation": report,
    }


def activate_control(control_id: str) -> ControlRecord:
    rec = get_record(control_id)
    if not rec:
        raise KeyError("Control not found")
    report = validate_control(control_id)
    if not report["valid"]:
        raise ValueError("; ".join(report["errors"]))
    ver = _draft_version(rec) or _current_version(rec)
    if not ver:
        raise ValueError("No version to activate")
    versions = list_versions()
    for idx, item in enumerate(versions):
        if str(item.control_id) == str(rec.id) and item.status == "ACTIVE" and item.id != ver.id:
            item.status = "DEPRECATED"
            item.updated_at = datetime.utcnow()
            versions[idx] = item
    ver.status = "ACTIVE"
    ver.activated_at = datetime.utcnow()
    ver.updated_at = datetime.utcnow()
    for idx, item in enumerate(versions):
        if item.id == ver.id:
            versions[idx] = ver
            break
    rec.status = "active"
    rec.current_active_version_id = ver.id
    rec.current_draft_version_id = None
    rec.updated_at = datetime.utcnow()
    records = list_records()
    for idx, item in enumerate(records):
        if item.id == rec.id:
            records[idx] = rec
            break
    _save_records(records)
    _save_versions(versions)
    append_audit("activate", "control", str(rec.id), f"Activated control {rec.key}")
    return rec


def test_control(control_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    rec = get_record(control_id)
    if not rec:
        raise KeyError("Control not found")
    ver = _editable_version(rec)
    if not ver:
        raise ValueError("No version to test")
    context = (body or {}).get("context") or {}
    execution_id = (body or {}).get("execution_id") or context.get("execution_id")
    if rec.key == "human-approval-before-publication" and context.get("checkpoint", {}).get("status") != "APPROVED":
        record_evaluation(
            control_key=rec.key,
            control_version=ver,
            result="FAILED",
            message="approved checkpoint not found",
            execution_id=execution_id,
            context=context,
        )
        return {
            "ok": False,
            "result": "FAILED",
            "message": "approved checkpoint not found",
            "enforcement": ver.enforcement_on_failed,
        }
    record_evaluation(
        control_key=rec.key,
        control_version=ver,
        result="PASSED",
        message="Control evaluation passed",
        execution_id=execution_id,
        context=context,
    )
    return {
        "ok": True,
        "result": "PASSED",
        "message": "Control evaluation passed",
        "enforcement": ver.enforcement_on_failed,
    }


def resolve_preview(payload: dict[str, Any]) -> dict[str, Any]:
    environment = (payload.get("environment") or "PRODUCTION").upper()
    flow = (payload.get("flow") or payload.get("flow_name") or "").lower()
    playbook = (payload.get("playbook") or payload.get("playbook_name") or "").lower()
    artifact = (payload.get("artifact") or payload.get("artifact_type") or "").upper()
    risk = (payload.get("risk") or payload.get("risk_level") or "MEDIUM").upper()

    applicable: list[dict[str, Any]] = []
    for rec in list_records():
        ver = _current_version(rec)
        if not ver or ver.status != "ACTIVE":
            continue
        if not _matches(ver, environment, artifact, risk):
            continue
        source = "Platform baseline"
        if "feature" in flow:
            source = "Flow binding"
        elif playbook:
            source = "Playbook binding"
        if ver.severity == "CRITICAL" and risk == "HIGH":
            source = "Risk controls"
        applicable.append({
            "key": rec.key,
            "name": rec.name,
            "severity": ver.severity,
            "enforcement": ver.enforcement_on_failed,
            "source": source,
        })

    blocking = sum(1 for item in applicable if item["enforcement"] in {"BLOCK", "REQUIRE_HUMAN_APPROVAL", "PAUSE_EXECUTION"})
    return {
        "matched": len(applicable),
        "blocking": blocking,
        "exceptions_active": len(_active_exceptions()),
        "trace": ["Platform baseline", "Workspace controls", "Flow bindings", "Risk controls"],
        "controls": applicable,
    }


def _matches(ver: ControlVersion, environment: str, artifact: str, risk: str) -> bool:
    if not ver.applicability:
        return True
    for cond in ver.applicability:
        if cond.field == "environment" and cond.value.upper() != environment:
            return False
        if cond.field == "artifact.type" and artifact and cond.value.upper() != artifact:
            return False
        if cond.field == "risk.level" and cond.value.upper() != risk:
            return False
    return True
