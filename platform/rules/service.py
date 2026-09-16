"""Rules persistence, catalog, and resolve preview."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from src.platform.rules.models import (
    SCOPE_WEIGHTS,
    RuleCatalogItem,
    RuleMetrics,
    RuleRecord,
    RuleVersion,
)
from src.platform.rules.validation import validate_version
from src.platform.store import append_audit, get_platform_dir

logger = logging.getLogger(__name__)
NS = UUID("a1f8c3e2-5b4d-4c9a-8e71-2d6f0b9a34c1")
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


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def ensure_rules_seeded() -> None:
    global _SEEDING
    marker = _path(".seeded_rules_v1")
    if marker.exists() and _path("rule_records.json").exists() and _path("rule_versions.json").exists():
        return
    if _SEEDING:
        return
    _SEEDING = True
    try:
        _seed_unlocked()
    finally:
        _SEEDING = False


def _seed_unlocked() -> None:
    marker = _path(".seeded_rules_v1")
    if marker.exists() and _path("rule_records.json").exists():
        return

    seeds = [
        {
            "key": "corporate-writing-style",
            "name": "Corporate Writing Style",
            "description": "Clear concise language with rationale for decisions.",
            "category": "STYLE",
            "scope": "ORGANIZATION",
            "priority": 20,
            "published": "2.4.0",
            "usage": 0,
            "content": (
                "# Corporate Writing Style\n\n"
                "- Use clear, concise language.\n"
                "- Avoid unsupported assumptions.\n"
                "- Every decision must include rationale.\n"
            ),
            "conflict_key": "writing-style",
        },
        {
            "key": "payments-terminology",
            "name": "Payments Terminology",
            "description": "Domain terminology for payments workspace.",
            "category": "TERMINOLOGY",
            "scope": "DOMAIN",
            "priority": 50,
            "published": "1.8.0",
            "usage": 0,
            "content": (
                "# Payments Terminology\n\n"
                "Use **платёжная операция** instead of **транзакция** "
                "unless referring to a database transaction.\n"
            ),
            "conflict_key": "terminology",
            "scope_selector": {"domain": "Payments"},
        },
        {
            "key": "system-requirements-structure",
            "name": "System Requirements Structure",
            "description": "Mandatory sections for system requirements artifacts.",
            "category": "FORMAT",
            "scope": "PLAYBOOK",
            "priority": 80,
            "published": "3.1.0",
            "usage": 0,
            "content": (
                "# Mandatory sections\n\n"
                "1. Goal\n2. Actors\n3. Preconditions\n"
                "4. Main flow\n5. Error cases\n6. NFR\n"
            ),
            "conflict_key": "requirements-structure",
            "scope_selector": {"playbookKeys": ["system-requirements"]},
        },
        {
            "key": "java-service-conventions",
            "name": "Java Service Conventions",
            "description": "Team coding conventions for Java services.",
            "category": "CODING_STANDARD",
            "scope": "TEAM",
            "priority": 60,
            "published": None,
            "draft": "4.0.0",
            "usage": 0,
            "content": (
                "# Java conventions\n\n"
                "- Constructor injection only\n"
                "- No field injection\n"
                "- Public methods require tests\n"
            ),
            "conflict_key": "java-conventions",
        },
        {
            "key": "ru-output-language",
            "name": "Russian Output Language",
            "description": "User-facing artifacts must be written in Russian.",
            "category": "LANGUAGE",
            "scope": "WORKSPACE",
            "priority": 30,
            "published": "1.0.0",
            "usage": 0,
            "content": (
                "# Language\n\n"
                "**HARD CONSTRAINT:** весь пользовательский артефакт — только на русском языке.\n\n"
                "- Заголовки, секции, требования, acceptance criteria, таблицы и списки — на русском.\n"
                "- Английские названия секций из шаблона навыка — примеры; переводи их на русский.\n"
                "- Не смешивай языки. Даже если задача или шаблон частично на английском — ответ на русском.\n"
            ),
            "conflict_key": "output-language",
            "conflict_strategy": "ERROR",
        },
        {
            "key": "test-case-format",
            "name": "Test Case Format",
            "description": "Standard format for generated test cases.",
            "category": "FORMAT",
            "scope": "PLAYBOOK",
            "priority": 70,
            "published": "2.2.0",
            "usage": 0,
            "content": (
                "# Test case\n\n"
                "- ID\n- Preconditions\n- Steps\n- Expected result\n- Evidence\n"
            ),
            "conflict_key": "test-case-format",
        },
    ]

    records: list[RuleRecord] = []
    versions: list[RuleVersion] = []
    for seed in seeds:
        rid = _id("rule", seed["key"])
        rec = RuleRecord(
            id=rid,
            key=seed["key"],
            name=seed["name"],
            description=seed["description"],
            category=seed["category"],
            owner_team="Architecture Enablement" if seed["scope"] != "TEAM" else "Platform Engineering",
            status="draft" if not seed.get("published") else "active",
            usage_count=seed["usage"],
        )
        scope = seed["scope"]
        weight = SCOPE_WEIGHTS.get(scope, 200)
        base_kwargs = dict(
            rule_id=rid,
            content_markdown=seed["content"],
            scope_type=scope,
            scope_selector=seed.get("scope_selector", {}),
            scope_weight=weight,
            priority=seed["priority"],
            conflict_strategy=seed.get("conflict_strategy", "OVERRIDE"),
            conflict_key=seed.get("conflict_key", seed["key"]),
            checksum=_checksum(seed["content"]),
        )
        if seed.get("published"):
            ver = RuleVersion(
                id=_id("rv", f"{seed['key']}-{seed['published']}"),
                semantic_version=seed["published"],
                version_number=1,
                status="PUBLISHED",
                published_at=datetime.utcnow(),
                **base_kwargs,
            )
            report = validate_version(ver)
            ver.validation_report = report
            ver.validation_status = "valid" if report["valid"] else "invalid"
            versions.append(ver)
            rec.current_published_version_id = ver.id
        if seed.get("draft"):
            ver = RuleVersion(
                id=_id("rv", f"{seed['key']}-{seed['draft']}"),
                semantic_version=seed["draft"],
                version_number=2 if seed.get("published") else 1,
                status="DRAFT",
                **base_kwargs,
            )
            report = validate_version(ver)
            ver.validation_report = report
            ver.validation_status = "warning" if report.get("warnings") else ("valid" if report["valid"] else "invalid")
            versions.append(ver)
            rec.current_draft_version_id = ver.id
        records.append(rec)

    _write_json("rule_records.json", {"rules": [r.model_dump(mode="json") for r in records]})
    _write_json("rule_versions.json", {"versions": [v.model_dump(mode="json") for v in versions]})
    marker.write_text(datetime.utcnow().isoformat() + "\n", encoding="utf-8")
    logger.info("Rules subsystem seeded")


def list_records() -> list[RuleRecord]:
    ensure_rules_seeded()
    return [RuleRecord.model_validate(x) for x in _read_json("rule_records.json", {"rules": []}).get("rules", [])]


def list_versions(rule_id: str | None = None) -> list[RuleVersion]:
    ensure_rules_seeded()
    items = [RuleVersion.model_validate(x) for x in _read_json("rule_versions.json", {"versions": []}).get("versions", [])]
    if rule_id:
        items = [v for v in items if str(v.rule_id) == rule_id]
    return items


def _save_records(items: list[RuleRecord]) -> None:
    _write_json("rule_records.json", {"rules": [i.model_dump(mode="json") for i in items]})


def _save_versions(items: list[RuleVersion]) -> None:
    _write_json("rule_versions.json", {"versions": [i.model_dump(mode="json") for i in items]})


def get_record(rule_id: str) -> RuleRecord | None:
    for r in list_records():
        if str(r.id) == rule_id or r.key == rule_id:
            return r
    return None


def get_version(version_id: str) -> RuleVersion | None:
    for v in list_versions():
        if str(v.id) == version_id:
            return v
    return None


def metrics() -> RuleMetrics:
    records = list_records()
    versions = list_versions()
    published = sum(1 for v in versions if v.status == "PUBLISHED")
    drafts = sum(1 for v in versions if v.status == "DRAFT")
    return RuleMetrics(
        published=published,
        drafts=drafts,
        executions_30d=sum(r.usage_count for r in records),
    )


def catalog_items(
    search: str = "",
    category: str = "",
    scope: str = "",
    status: str = "",
) -> list[RuleCatalogItem]:
    by_rule: dict[str, list[RuleVersion]] = {}
    for v in list_versions():
        by_rule.setdefault(str(v.rule_id), []).append(v)

    items: list[RuleCatalogItem] = []
    for r in list_records():
        vers = by_rule.get(str(r.id), [])
        published = next((v for v in vers if v.status == "PUBLISHED"), None)
        draft = next((v for v in vers if v.status == "DRAFT"), None)
        active = published or draft
        st = "DEPRECATED" if r.status == "deprecated" else ("PUBLISHED" if published else "DRAFT")
        blob = f"{r.name} {r.key} {r.description} {r.owner_team}".lower()
        if search and search.lower() not in blob:
            continue
        if category and category.upper() not in ("", "ALL") and r.category != category.upper():
            continue
        if scope and scope.upper() not in ("", "ALL") and (not active or active.scope_type != scope.upper()):
            continue
        if status and status.upper() not in ("", "ALL") and st != status.upper():
            continue
        items.append(RuleCatalogItem(
            id=str(r.id),
            key=r.key,
            name=r.name,
            description=r.description,
            category=r.category,
            scope=active.scope_type if active else "ORGANIZATION",
            priority=active.priority if active else 50,
            version=active.semantic_version if active else None,
            status=st,
            owner=r.owner_team,
            usage_count=r.usage_count,
            conflict_strategy=active.conflict_strategy if active else "OVERRIDE",
        ))
    return items


def detail(rule_id: str) -> dict[str, Any]:
    rec = get_record(rule_id)
    if not rec:
        raise KeyError("Rule not found")
    versions = sorted(list_versions(str(rec.id)), key=lambda v: v.version_number, reverse=True)
    published = next((v for v in versions if v.status == "PUBLISHED"), None)
    draft = next((v for v in versions if v.status == "DRAFT"), None)
    current = published or draft or (versions[0] if versions else None)
    return {
        "rule": rec.model_dump(mode="json"),
        "current_version": current.model_dump(mode="json") if current else None,
        "published_version": published.model_dump(mode="json") if published else None,
        "draft_version": draft.model_dump(mode="json") if draft else None,
        "versions": [
            {
                "id": str(v.id),
                "semantic_version": v.semantic_version,
                "status": v.status,
                "validation_status": v.validation_status,
                "published_at": v.published_at.isoformat() if v.published_at else None,
            }
            for v in versions
        ],
    }


def usage(rule_id: str) -> dict[str, Any]:
    """Graph nodes that reference this rule."""
    rec = get_record(rule_id)
    if not rec:
        raise KeyError("Rule not found")
    from src.platform.graphs.bindings import rule_usages

    usages = rule_usages(rec.key)
    return {"rule_id": str(rec.id), "rule_key": rec.key, "usages": usages}


def create_rule(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_rules_seeded()
    name = payload["name"]
    key = payload.get("key") or name.lower().replace(" ", "-")
    if get_record(key):
        raise ValueError(f"Rule key already exists: {key}")
    scope = (payload.get("scope_type") or payload.get("scope") or "ORGANIZATION").upper()
    category = (payload.get("category") or "STYLE").upper()
    content = payload.get("content_markdown") or payload.get("content_md") or f"# {name}\n\nDraft content.\n"
    rec = RuleRecord(
        key=key,
        name=name,
        description=payload.get("description", ""),
        category=category,
        owner_team=payload.get("owner_team") or "Platform",
        status="draft",
    )
    ver = RuleVersion(
        rule_id=rec.id,
        semantic_version=payload.get("semantic_version", "0.1.0"),
        status="DRAFT",
        content_markdown=content,
        scope_type=scope,
        scope_selector=payload.get("scope_selector") or {},
        scope_weight=SCOPE_WEIGHTS.get(scope, 200),
        priority=int(payload.get("priority", 50)),
        conflict_strategy=payload.get("conflict_strategy", "OVERRIDE"),
        conflict_key=payload.get("conflict_key") or key,
        checksum=_checksum(content),
    )
    report = validate_version(ver)
    ver.validation_report = report
    ver.validation_status = "valid" if report["valid"] else "invalid"
    rec.current_draft_version_id = ver.id
    _save_records(list_records() + [rec])
    _save_versions(list_versions() + [ver])
    append_audit("create", "rule", str(rec.id), f"Created rule {rec.key}")
    return detail(str(rec.id))


def update_rule(rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    rec = get_record(rule_id)
    if not rec:
        raise KeyError("Rule not found")
    if rec.status == "archived":
        raise ValueError("Cannot edit an archived rule")
    name = payload.get("name")
    if name is not None:
        name = str(name).strip()
        if not name:
            raise ValueError("Name is required")
    records = list_records()
    now = datetime.utcnow()
    for record in records:
        if record.id != rec.id:
            continue
        if name is not None:
            record.name = name
        if "description" in payload:
            record.description = str(payload.get("description") or "")
        if payload.get("owner_team"):
            record.owner_team = str(payload["owner_team"]).strip()
        record.updated_at = now
        record.revision = int(record.revision or 1) + 1
        rec = record
        break
    _save_records(records)
    append_audit("update", "rule", str(rec.id), f"Updated rule {rec.key}")
    return detail(str(rec.id))


def delete_rule(rule_id: str) -> dict[str, Any]:
    rec = get_record(rule_id)
    if not rec:
        raise KeyError("Rule not found")
    from src.platform.graphs.bindings import rule_usages

    usages = rule_usages(rec.key)
    if usages:
        keys = sorted({u.get("graph_key") or u.get("flow_key") for u in usages if u.get("graph_key") or u.get("flow_key")})
        raise ValueError(
            "Cannot delete: referenced in graphs "
            + ", ".join(keys)
        )
    records = [r for r in list_records() if r.id != rec.id]
    versions = [v for v in list_versions() if str(v.rule_id) != str(rec.id)]
    _save_records(records)
    _save_versions(versions)
    append_audit("delete", "rule", str(rec.id), f"Deleted rule {rec.key}")
    return {"ok": True, "id": str(rec.id), "key": rec.key}


def save_content(rule_id: str, version_id: str, content: str, if_match: str | None = None) -> RuleVersion:
    rec = get_record(rule_id)
    ver = get_version(version_id)
    if not rec or not ver or str(ver.rule_id) != str(rec.id):
        raise KeyError("Version not found")
    if ver.status == "PUBLISHED":
        raise PermissionError("Cannot modify published version")
    if if_match is not None and if_match.strip('"') != str(ver.revision):
        raise RuntimeError("RULE_VERSION_CONFLICT")
    ver.content_markdown = content
    ver.checksum = _checksum(content)
    ver.revision += 1
    ver.updated_at = datetime.utcnow()
    report = validate_version(ver)
    ver.validation_report = report
    ver.validation_status = "valid" if report["valid"] else "invalid"
    versions = list_versions()
    for i, v in enumerate(versions):
        if str(v.id) == str(ver.id):
            versions[i] = ver
            break
    _save_versions(versions)
    return ver


def validate_rule_version(rule_id: str, version_id: str) -> dict[str, Any]:
    rec = get_record(rule_id)
    ver = get_version(version_id)
    if not rec or not ver or str(ver.rule_id) != str(rec.id):
        raise KeyError("Version not found")
    report = validate_version(ver)
    versions = list_versions()
    for i, v in enumerate(versions):
        if str(v.id) == str(ver.id):
            v.validation_report = report
            v.validation_status = "valid" if report["valid"] else "invalid"
            if report["valid"] and report.get("warnings"):
                v.validation_status = "warning"
            versions[i] = v
            break
    _save_versions(versions)
    return report


def publish_version(rule_id: str, version_id: str) -> dict[str, Any]:
    rec = get_record(rule_id)
    ver = get_version(version_id)
    if not rec or not ver or str(ver.rule_id) != str(rec.id):
        raise KeyError("Version not found")
    report = validate_rule_version(rule_id, version_id)
    if not report["valid"]:
        raise ValueError("Cannot publish invalid rule version")
    versions = list_versions()
    for v in versions:
        if str(v.rule_id) == str(rec.id) and v.status == "PUBLISHED":
            v.status = "DEPRECATED"
        if str(v.id) == str(ver.id):
            v.status = "PUBLISHED"
            v.published_at = datetime.utcnow()
            ver = v
    records = list_records()
    for r in records:
        if str(r.id) == str(rec.id):
            r.current_published_version_id = ver.id
            r.status = "active"
            r.updated_at = datetime.utcnow()
    _save_versions(versions)
    _save_records(records)
    append_audit("publish", "rule_version", str(ver.id), f"Published {rec.key}@{ver.semantic_version}")
    return detail(str(rec.id))


def resolve_bound_bundle(rule_keys: list[str] | None = None) -> dict[str, Any]:
    """Resolve published markdown for explicitly bound rule keys (skill-slot bindings)."""
    keys = [str(k).strip() for k in (rule_keys or []) if str(k).strip()]
    empty = {
        "matched": 0,
        "overridden": 0,
        "conflicts": [],
        "application_order": [],
        "bundle_markdown": "",
        "effective_rule_ids": [],
        "effective_rule_keys": [],
        "rule_keys": keys,
    }
    if not keys:
        return empty

    records_by_key = {r.key: r for r in list_records()}
    versions_by_id = {str(v.id): v for v in list_versions()}
    selected: list[tuple[RuleRecord, RuleVersion]] = []
    for key in keys:
        rec = records_by_key.get(key)
        if not rec:
            logger.warning("Bound rule key %r not found", key)
            continue
        ver: RuleVersion | None = None
        if rec.current_published_version_id:
            ver = versions_by_id.get(str(rec.current_published_version_id))
        if not ver or ver.status != "PUBLISHED":
            pubs = [v for v in list_versions(str(rec.id)) if v.status == "PUBLISHED"]
            ver = pubs[-1] if pubs else None
        if not ver:
            logger.warning("Bound rule %r has no published version", key)
            continue
        selected.append((rec, ver))

    by_conflict: dict[str, tuple[RuleRecord, RuleVersion]] = {}
    stack: list[dict[str, Any]] = []
    overridden = 0
    for rec, ver in selected:
        ck = ver.conflict_key or rec.key
        entry: dict[str, Any] = {
            "rule_id": str(rec.id),
            "key": rec.key,
            "name": rec.name,
            "scope": ver.scope_type,
            "priority": ver.priority,
            "version": ver.semantic_version,
            "conflict_key": ver.conflict_key,
            "version_id": str(ver.id),
        }
        if ck in by_conflict:
            prev_rec, prev_ver = by_conflict[ck]
            if (ver.scope_weight, ver.priority) >= (prev_ver.scope_weight, prev_ver.priority):
                overridden += 1
                entry["overrides"] = prev_rec.key
                by_conflict[ck] = (rec, ver)
            else:
                overridden += 1
                entry["overridden_by"] = prev_rec.key
        else:
            by_conflict[ck] = (rec, ver)
        stack.append(entry)

    key_order = {k: i for i, k in enumerate(keys)}
    effective = sorted(
        by_conflict.values(),
        key=lambda pair: key_order.get(pair[0].key, 10_000),
    )
    if not effective:
        return empty

    bundle_parts = ["# Bound Rule Bundle\n"]
    for rec, ver in effective:
        bundle_parts.append(f"## {rec.name} (`{rec.key}`)\n{ver.content_markdown.strip()}\n")

    return {
        "matched": len(selected),
        "overridden": overridden,
        "conflicts": [],
        "application_order": stack,
        "bundle_markdown": "\n".join(bundle_parts).rstrip() + "\n",
        "effective_rule_ids": [str(ver.id) for _, ver in effective],
        "effective_rule_keys": [rec.key for rec, _ in effective],
        "rule_keys": keys,
    }


def resolve_preview(context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build effective rule bundle for a mock execution context."""
    context = context or {}
    bound_keys = context.get("rule_keys") or context.get("bound_rule_keys")
    if bound_keys:
        result = resolve_bound_bundle([str(k) for k in bound_keys])
        result["context"] = context
        return result

    published = [v for v in list_versions() if v.status == "PUBLISHED"]
    records = {str(r.id): r for r in list_records()}

    # Match by increasing specificity; sort by scope_weight then priority
    matched = sorted(published, key=lambda v: (v.scope_weight, v.priority))
    stack = []
    by_conflict: dict[str, RuleVersion] = {}
    overridden = 0
    for v in matched:
        rec = records.get(str(v.rule_id))
        if not rec:
            continue
        entry = {
            "rule_id": str(rec.id),
            "key": rec.key,
            "name": rec.name,
            "scope": v.scope_type,
            "priority": v.priority,
            "version": v.semantic_version,
            "conflict_key": v.conflict_key,
        }
        if v.conflict_key and v.conflict_key in by_conflict:
            overridden += 1
            entry["overridden_by"] = records[str(by_conflict[v.conflict_key].rule_id)].key
        by_conflict[v.conflict_key or rec.key] = v
        stack.append(entry)

    # Control always wins over rules with the same conflict_key.
    conflicts = []
    effective = list(by_conflict.values())
    effective.sort(key=lambda v: (v.scope_weight, v.priority))
    bundle_parts = ["# Effective Rule Bundle\n"]
    for v in effective:
        rec = records[str(v.rule_id)]
        bundle_parts.append(f"## {rec.name}\n{v.content_markdown.strip()}\n")
    if conflicts:
        bundle_parts.append("WARNING:\n" + "\n".join(c["message"] for c in conflicts))

    return {
        "context": context,
        "matched": len(stack),
        "overridden": overridden,
        "conflicts": conflicts,
        "application_order": stack,
        "bundle_markdown": "\n".join(bundle_parts),
        "effective_rule_ids": [str(v.id) for v in effective],
    }
