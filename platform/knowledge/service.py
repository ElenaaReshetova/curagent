"""Knowledge Spaces persistence, catalog, and search playground."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from src.platform.knowledge.models import (
    KnowledgeCatalogItem,
    KnowledgeMetrics,
    KnowledgeSpaceRecord,
    SourceBinding,
)
from src.platform.knowledge.validation import validate_space
from src.platform.store import append_audit, get_platform_dir

logger = logging.getLogger(__name__)
NS = UUID("e9c4b2a1-3f7d-4a8e-9c12-5b6d8e0f1a2b")
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


def ensure_knowledge_seeded() -> None:
    global _SEEDING
    marker = _path(".seeded_knowledge_v1")
    if marker.exists() and _path("knowledge_space_records.json").exists():
        return
    if _SEEDING:
        return
    _SEEDING = True
    try:
        _seed_unlocked()
    finally:
        _SEEDING = False


def _seed_unlocked() -> None:
    marker = _path(".seeded_knowledge_v1")
    if marker.exists() and _path("knowledge_space_records.json").exists():
        return

    seeds = [
        {
            "key": "payments",
            "name": "Payments",
            "purpose": "Trusted context for payment products, architecture and operations.",
            "type": "DOMAIN",
            "status": "ACTIVE",
            "classification": "CONFIDENTIAL",
            "usage": 0,
            "success": 0.0,
            "project_areas": ["payments", "risk"],
            "team_names": ["Platform", "PAY squad"],
            "additional_context": "Use for payment processing, cancellation, and operational-risk context.",
            "sources": [
                ("jira", "Jira PAY", {"project": "PAY"}, 80),
                ("confluence", "Confluence PAY", {"space": "PAY"}, 100),
                ("git", "Git payment-api", {"repos": ["payment-api", "payment-core"]}, 70),
                ("slack", "Slack payments", {"channels": ["#payments-dev", "#payments-ops"]}, 40),
            ],
        },
        {
            "key": "cards",
            "name": "Cards",
            "purpose": "Card issuing, processing, fraud and settlement context.",
            "type": "DOMAIN",
            "status": "ACTIVE",
            "classification": "CONFIDENTIAL",
            "usage": 0,
            "success": 0.0,
            "sources": [
                ("jira", "Jira CARD", {"project": "CARD"}, 80),
                ("confluence", "Confluence CARD", {"space": "CARD"}, 100),
                ("git", "Git card-core", {"repos": ["card-core"]}, 70),
            ],
        },
        {
            "key": "identity-platform",
            "name": "Identity Platform",
            "purpose": "Identity, authentication and authorization platform knowledge.",
            "type": "SYSTEM",
            "status": "DEGRADED",
            "classification": "RESTRICTED",
            "usage": 0,
            "success": 0.0,
            "sources": [
                ("confluence", "Confluence IAM", {"space": "IAM"}, 100, 78.0),
                ("git", "Git identity", {"repos": ["identity"]}, 70, 85.0),
                ("api_catalog", "API Catalog IAM", {"catalog": "IAM"}, 60, 80.0),
            ],
        },
        {
            "key": "mobile-banking",
            "name": "Mobile Banking",
            "purpose": "Product and technical context for mobile applications.",
            "type": "PRODUCT",
            "status": "ACTIVE",
            "classification": "INTERNAL",
            "usage": 0,
            "success": 0.0,
            "sources": [
                ("jira", "Jira MOB", {"project": "MOB"}, 80),
                ("confluence", "Confluence Mobile", {"space": "MOBILE"}, 100),
                ("git", "Git mobile-app", {"repos": ["mobile-app"]}, 70),
            ],
        },
        {
            "key": "pci-dss",
            "name": "PCI DSS",
            "purpose": "Regulatory and compliance evidence for cardholder data.",
            "type": "REGULATORY",
            "status": "ACTIVE",
            "classification": "RESTRICTED",
            "usage": 0,
            "success": 0.0,
            "sources": [
                ("policy_library", "Policy Library", {"pack": "pci-dss"}, 100),
                ("audit_repo", "Audit Repository", {"scope": "pci"}, 90),
            ],
        },
        {
            "key": "pay-123-investigation",
            "name": "PAY-123 Investigation",
            "purpose": "Temporary context for payment cancellation investigation.",
            "type": "TEMPORARY",
            "status": "DRAFT",
            "classification": "INTERNAL",
            "usage": 0,
            "success": 0.0,
            "sources": [
                ("jira", "Jira PAY-123", {"issue": "PAY-123"}, 100),
            ],
        },
    ]

    records: list[KnowledgeSpaceRecord] = []
    for seed in seeds:
        sources = []
        for item in seed["sources"]:
            provider, name, selector, priority = item[0], item[1], item[2], item[3]
            health = item[4] if len(item) > 4 else 100.0
            status = "DEGRADED" if health < 85 else "ACTIVE"
            sources.append(SourceBinding(
                id=_id("ksrc", f"{seed['key']}:{name}"),
                provider=provider,
                name=name,
                selector=selector,
                priority=priority,
                status=status,
                health_pct=health,
                last_checked_at=datetime.utcnow(),
            ))
        records.append(KnowledgeSpaceRecord(
            id=_id("ks", seed["key"]),
            key=seed["key"],
            name=seed["name"],
            purpose=seed["purpose"],
            space_type=seed["type"],
            status=seed["status"],
            classification=seed["classification"],
            owner_team="Payments Analysis" if "pay" in seed["key"] or seed["key"] == "cards" else "Platform",
            project_areas=seed.get("project_areas", []),
            team_names=seed.get("team_names", []),
            additional_context=seed.get("additional_context", ""),
            sources=sources,
            search_policy={"max_results": 20, "dedupe": True, "prefer_fresh": True},
            access_policy={"roles": ["Process Designer", "Analyst", "Architect"]},
            freshness_hours=24 if seed["classification"] != "RESTRICTED" else 12,
            usage_30d=seed["usage"],
            search_success_pct=seed["success"],
        ))

    _write_json("knowledge_space_records.json", {"spaces": [r.model_dump(mode="json") for r in records]})
    marker.write_text(datetime.utcnow().isoformat() + "\n", encoding="utf-8")
    logger.info("Knowledge Spaces subsystem seeded")


def list_records() -> list[KnowledgeSpaceRecord]:
    ensure_knowledge_seeded()
    raw = _read_json("knowledge_space_records.json", {"spaces": []}).get("spaces", [])
    return [KnowledgeSpaceRecord.model_validate(x) for x in raw]


def _save_records(items: list[KnowledgeSpaceRecord]) -> None:
    _write_json("knowledge_space_records.json", {"spaces": [i.model_dump(mode="json") for i in items]})


def get_record(space_id: str) -> KnowledgeSpaceRecord | None:
    for r in list_records():
        if str(r.id) == space_id or r.key == space_id:
            return r
    return None


def _health(space: KnowledgeSpaceRecord) -> float:
    if not space.sources:
        return 0.0 if space.status == "ACTIVE" else 100.0
    return round(sum(s.health_pct for s in space.sources) / len(space.sources), 1)


def metrics() -> KnowledgeMetrics:
    records = list_records()
    sources = [s for r in records for s in r.sources]
    active = sum(1 for r in records if r.status == "ACTIVE")
    healthy = sum(1 for s in sources if s.health_pct >= 90 and s.status == "ACTIVE")
    stale = sum(1 for s in sources if s.health_pct < 85)
    success = [r.search_success_pct for r in records if r.status in ("ACTIVE", "DEGRADED") and r.usage_30d]
    return KnowledgeMetrics(
        active_spaces=active,
        connected_sources=len(sources),
        healthy_sources=healthy,
        search_success_pct=round(sum(success) / len(success), 1) if success else 0.0,
        stale_sources=stale,
    )


def catalog_items(
    search: str = "",
    space_type: str = "",
    status: str = "",
) -> list[KnowledgeCatalogItem]:
    items: list[KnowledgeCatalogItem] = []
    for r in list_records():
        blob = f"{r.name} {r.key} {r.purpose} {r.owner_team}".lower()
        if search and search.lower() not in blob:
            continue
        if space_type and space_type.upper() not in ("", "ALL") and r.space_type != space_type.upper():
            continue
        if status and status.upper() not in ("", "ALL") and r.status != status.upper():
            continue
        labels = [s.name for s in r.sources]
        items.append(KnowledgeCatalogItem(
            id=str(r.id),
            key=r.key,
            name=r.name,
            purpose=r.purpose,
            space_type=r.space_type,
            status=r.status,
            classification=r.classification,
            owner=r.owner_team,
            source_count=len(r.sources),
            source_labels=labels,
            health_pct=_health(r),
            usage_30d=r.usage_30d,
        ))
    return items


def detail(space_id: str) -> dict[str, Any]:
    rec = get_record(space_id)
    if not rec:
        raise KeyError("Knowledge Space not found")
    report = validate_space(rec)
    return {
        "space": rec.model_dump(mode="json"),
        "health_pct": _health(rec),
        "validation": report,
        "sources": [s.model_dump(mode="json") for s in rec.sources],
    }


def create_space(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_knowledge_seeded()
    name = payload["name"]
    key = payload.get("key") or name.lower().replace(" ", "-")
    if get_record(key):
        raise ValueError(f"Knowledge Space key already exists: {key}")
    rec = KnowledgeSpaceRecord(
        key=key,
        name=name,
        purpose=payload.get("purpose") or payload.get("description") or "Trusted context for this domain.",
        space_type=(payload.get("space_type") or payload.get("type") or "DOMAIN").upper(),
        status="DRAFT",
        classification=(payload.get("classification") or "INTERNAL").upper(),
        owner_team=payload.get("owner_team") or "Platform",
        project_areas=payload.get("project_areas") or [],
        team_names=payload.get("team_names") or [],
        additional_context=payload.get("additional_context") or "",
        sources=[],
        search_policy={"max_results": 20, "dedupe": True},
        access_policy={"roles": ["Process Designer"]},
        freshness_hours=int(payload.get("freshness_hours", 24)),
    )
    _save_records(list_records() + [rec])
    append_audit("create", "knowledge_space", str(rec.id), f"Created knowledge space {rec.key}")
    return detail(str(rec.id))


def update_space(space_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Update agent context and description without replacing source bindings."""
    rec = get_record(space_id)
    if not rec:
        raise KeyError("Knowledge Space not found")

    changes: dict[str, Any] = {}
    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if name:
            changes["name"] = name
    if "space_type" in payload or "type" in payload:
        changes["space_type"] = (payload.get("space_type") or payload.get("type") or rec.space_type).upper()
    if "classification" in payload:
        changes["classification"] = (payload.get("classification") or rec.classification).upper()
    if "description" in payload:
        changes["purpose"] = payload["description"] or ""
    elif "purpose" in payload:
        changes["purpose"] = payload["purpose"] or ""
    for field in ("project_areas", "team_names", "additional_context"):
        if field in payload:
            changes[field] = payload[field] or ([] if field != "additional_context" else "")
    try:
        updated = KnowledgeSpaceRecord.model_validate({
            **rec.model_dump(mode="python"),
            **changes,
            "updated_at": datetime.utcnow(),
            "revision": rec.revision + 1,
        })
    except Exception as e:
        raise ValueError(f"Invalid knowledge space update: {e}") from e

    records = list_records()
    records = [updated if str(item.id) == str(rec.id) else item for item in records]
    _save_records(records)
    append_audit("update", "knowledge_space", str(rec.id), f"Updated knowledge space {rec.key}")
    return detail(str(rec.id))


def activate_space(space_id: str) -> dict[str, Any]:
    """Promote a draft (or re-enable) knowledge space to ACTIVE after validation."""
    rec = get_record(space_id)
    if not rec:
        raise KeyError("Knowledge Space not found")
    if rec.status == "ACTIVE":
        return detail(str(rec.id))
    if rec.status not in ("DRAFT", "DISABLED", "DEGRADED"):
        raise ValueError(f"Cannot activate knowledge space in status {rec.status}")

    candidate = KnowledgeSpaceRecord.model_validate({
        **rec.model_dump(mode="python"),
        "status": "ACTIVE",
    })
    report = validate_space(candidate)
    if not report["valid"]:
        messages = [e["message"] for e in report.get("errors", [])]
        raise ValueError("; ".join(messages) if messages else "Knowledge space validation failed")

    updated = KnowledgeSpaceRecord.model_validate({
        **rec.model_dump(mode="python"),
        "status": "ACTIVE",
        "updated_at": datetime.utcnow(),
        "revision": rec.revision + 1,
    })
    records = list_records()
    records = [updated if str(item.id) == str(rec.id) else item for item in records]
    _save_records(records)
    append_audit("activate", "knowledge_space", str(rec.id), f"Activated knowledge space {rec.key}")
    return detail(str(rec.id))


def disable_space(space_id: str) -> dict[str, Any]:
    """Disable an active or degraded knowledge space."""
    rec = get_record(space_id)
    if not rec:
        raise KeyError("Knowledge Space not found")
    if rec.status == "DISABLED":
        return detail(str(rec.id))
    if rec.status not in ("ACTIVE", "DEGRADED"):
        raise ValueError(f"Cannot disable knowledge space in status {rec.status}")

    updated = KnowledgeSpaceRecord.model_validate({
        **rec.model_dump(mode="python"),
        "status": "DISABLED",
        "updated_at": datetime.utcnow(),
        "revision": rec.revision + 1,
    })
    records = list_records()
    records = [updated if str(item.id) == str(rec.id) else item for item in records]
    _save_records(records)
    append_audit("disable", "knowledge_space", str(rec.id), f"Disabled knowledge space {rec.key}")
    return detail(str(rec.id))


def delete_space(space_id: str) -> dict[str, Any]:
    """Permanently remove a knowledge space."""
    rec = get_record(space_id)
    if not rec:
        raise KeyError("Knowledge Space not found")
    records = [r for r in list_records() if r.id != rec.id]
    _save_records(records)
    append_audit("delete", "knowledge_space", str(rec.id), f"Deleted knowledge space {rec.key}")
    return {"ok": True, "id": str(rec.id), "key": rec.key}


def add_source(space_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    rec = get_record(space_id)
    if not rec:
        raise KeyError("Knowledge Space not found")
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("Source name is required")
    provider = (payload.get("provider") or "other").lower()
    try:
        src = SourceBinding(
            provider=provider,
            name=name,
            selector=payload.get("selector") if isinstance(payload.get("selector"), dict) else {},
            priority=int(payload.get("priority", 50)),
            status=(payload.get("status") or "ACTIVE").upper(),
            health_pct=float(payload.get("health_pct", 100.0)),
            last_checked_at=datetime.utcnow(),
        )
    except Exception as e:
        raise ValueError(f"Invalid source: {e}") from e
    records = list_records()
    for r in records:
        if str(r.id) == str(rec.id):
            r.sources.append(src)
            r.updated_at = datetime.utcnow()
            r.revision += 1
            break
    _save_records(records)
    append_audit("create", "knowledge_source", str(src.id), f"Added source {src.name} to {rec.key}")
    return detail(str(rec.id))


def update_source(space_id: str, source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    rec = get_record(space_id)
    if not rec:
        raise KeyError("Knowledge Space not found")
    records = list_records()
    updated_src: SourceBinding | None = None
    for r in records:
        if str(r.id) != str(rec.id):
            continue
        next_sources: list[SourceBinding] = []
        for src in r.sources:
            if str(src.id) != str(source_id):
                next_sources.append(src)
                continue
            data = src.model_dump(mode="python")
            if "name" in payload:
                name = (payload.get("name") or "").strip()
                if not name:
                    raise ValueError("Source name is required")
                data["name"] = name
            if "provider" in payload and payload.get("provider"):
                data["provider"] = str(payload["provider"]).lower()
            if "selector" in payload:
                data["selector"] = payload["selector"] if isinstance(payload.get("selector"), dict) else {}
            if "priority" in payload and payload.get("priority") is not None:
                data["priority"] = int(payload["priority"])
            if "status" in payload and payload.get("status"):
                data["status"] = str(payload["status"]).upper()
            if "health_pct" in payload and payload.get("health_pct") is not None:
                data["health_pct"] = float(payload["health_pct"])
            data["last_checked_at"] = datetime.utcnow()
            try:
                updated_src = SourceBinding.model_validate(data)
            except Exception as e:
                raise ValueError(f"Invalid source update: {e}") from e
            next_sources.append(updated_src)
        if updated_src is None:
            raise KeyError("Source not found")
        r.sources = next_sources
        r.updated_at = datetime.utcnow()
        r.revision += 1
        break
    if updated_src is None:
        raise KeyError("Source not found")
    _save_records(records)
    append_audit("update", "knowledge_source", str(source_id), f"Updated source on {rec.key}")
    return detail(str(rec.id))


def delete_source(space_id: str, source_id: str) -> dict[str, Any]:
    rec = get_record(space_id)
    if not rec:
        raise KeyError("Knowledge Space not found")
    records = list_records()
    found = False
    for r in records:
        if str(r.id) != str(rec.id):
            continue
        before = len(r.sources)
        r.sources = [s for s in r.sources if str(s.id) != str(source_id)]
        found = len(r.sources) < before
        if found:
            r.updated_at = datetime.utcnow()
            r.revision += 1
        break
    if not found:
        raise KeyError("Source not found")
    _save_records(records)
    append_audit("delete", "knowledge_source", str(source_id), f"Removed source from {rec.key}")
    return detail(str(rec.id))


def search_playground(space_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """MVP search: ranked mock evidence based on space sources (no side effects)."""
    rec = get_record(space_id)
    if not rec:
        raise KeyError("Knowledge Space not found")
    body = body or {}
    query = (body.get("query") or "").strip() or "context"
    need = body.get("information_need") or "Architecture context"

    catalog = {
        "confluence": [
            ("Payment Cancellation Architecture", "Describes cancellation states, compensation flow and integration boundaries.", 0.93),
            ("Payment Operations Runbook", "Operational recovery and manual compensation procedures.", 0.78),
        ],
        "git": [
            ("CancellationService.java", "Implements cancellation eligibility and publishes PaymentCancelled event.", 0.89),
        ],
        "jira": [
            ("PAY-872 Previous cancellation feature", "Contains accepted business restrictions and error scenarios.", 0.84),
        ],
        "slack": [
            ("#payments-ops thread", "Ops notes about compensation retries.", 0.71),
        ],
        "api_catalog": [
            ("CancelPayment API", "OpenAPI contract for cancellation endpoint.", 0.80),
        ],
        "policy_library": [
            ("PCI retention policy", "Retention and masking requirements.", 0.88),
        ],
        "audit_repo": [
            ("Last audit evidence pack", "Evidence references for control coverage.", 0.86),
        ],
        "other": [
            ("Generic note", "Fallback evidence stub.", 0.60),
        ],
    }

    evidence = []
    for src in sorted(rec.sources, key=lambda s: -s.priority):
        if src.status == "DISABLED":
            continue
        for title, snippet, score in catalog.get(src.provider, catalog["other"]):
            # slight boost if query tokens appear
            boost = 0.02 if any(tok in title.lower() or tok in snippet.lower() for tok in query.lower().split() if len(tok) > 3) else 0
            evidence.append({
                "title": title,
                "source": f"{src.name}",
                "provider": src.provider,
                "snippet": snippet,
                "score": round(min(0.99, score + boost + src.priority / 5000), 2),
                "freshness": "current",
                "classification": rec.classification,
            })

    evidence.sort(key=lambda e: -e["score"])
    evidence = evidence[:6]
    excluded = max(0, len(rec.sources) * 3 - len(evidence))
    return {
        "space_id": str(rec.id),
        "space_key": rec.key,
        "query": query,
        "information_need": need,
        "sources_considered": len([s for s in rec.sources if s.status != "DISABLED"]),
        "raw_results": len(rec.sources) * 7,
        "evidence_count": len(evidence),
        "excluded": excluded,
        "evidence": evidence,
        "pipeline": ["Information Need", "Source Selection", "Search", "Ranking", "Evidence"],
    }


def health_check(space_id: str) -> dict[str, Any]:
    rec = get_record(space_id)
    if not rec:
        raise KeyError("Knowledge Space not found")
    sources = []
    for s in rec.sources:
        sources.append({
            "id": str(s.id),
            "name": s.name,
            "status": s.status,
            "health_pct": s.health_pct,
            "ok": s.health_pct >= 85 and s.status != "ERROR",
        })
    overall = _health(rec)
    return {
        "overall_pct": overall,
        "status": "HEALTHY" if overall >= 90 else ("DEGRADED" if overall >= 70 else "UNHEALTHY"),
        "sources": sources,
        "validation": validate_space(rec),
    }
