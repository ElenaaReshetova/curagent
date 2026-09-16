"""Skills persistence + catalog service (JSON store or PostgreSQL SoT)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

from src.platform.db.settings import skills_use_postgres
from src.platform.skills.models import (
    SkillBindingRef,
    SkillCatalogItem,
    SkillFile,
    SkillMetrics,
    SkillRecord,
    SkillTestCase,
    SkillVersion,
    skill_is_immutable,
)
from src.platform.contracts.registry import interface_contract_index, interface_contracts
from src.platform.skills.validation import validate_skill_output, validate_version
from src.platform.skills.seed_data import (
    build_seed_catalog,
    default_skill_md,
    ensure_quality_scaffold,
    interface_index as seed_interface_index,
)
from src.platform.store import append_audit, get_platform_dir, list_skill_interfaces

logger = logging.getLogger(__name__)
NS = UUID("c3a91f0e-7b2d-4e5a-9c18-4f6d8a2b01ef")

_PATH_RE = re.compile(r"^[A-Za-z0-9._\-]+(/[A-Za-z0-9._\-]+)*$")
_FOLDER_RE = re.compile(r"^[A-Za-z0-9._\-]+(/[A-Za-z0-9._\-]+)*/?$")


def _id(kind: str, key: str) -> UUID:
    return uuid5(NS, f"{kind}:{key}")


def _path(name: str) -> Path:
    return get_platform_dir() / name


def _read_json(name: str, default: Any) -> Any:
    from src.platform.json_store import read_json

    return read_json(_path(name), default)


def _write_json(name: str, payload: Any) -> None:
    from src.platform.json_store import write_json

    write_json(_path(name), payload)


def _checksum(markdown: str, manifest: dict, files: list[SkillFile] | None = None) -> str:
    payload = {
        "md": markdown,
        "manifest": manifest,
        "files": [
            {"path": f.path, "kind": f.kind, "content_text": f.content_text}
            for f in (files or [])
        ],
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _normalize_package_path(path: str, *, folder: bool = False) -> str:
    cleaned = (path or "").strip().replace("\\", "/").lstrip("/")
    if not cleaned or ".." in cleaned.split("/"):
        raise ValueError("Invalid package path")
    if folder:
        cleaned = cleaned.rstrip("/") + "/"
        if not _FOLDER_RE.match(cleaned.rstrip("/")):
            raise ValueError("Invalid folder path")
        return cleaned
    if not _PATH_RE.match(cleaned):
        raise ValueError("Invalid file path")
    return cleaned


def _media_type_for(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".md"):
        return "text/markdown"
    if lower.endswith((".yaml", ".yml")):
        return "text/yaml"
    if lower.endswith(".json"):
        return "application/json"
    if lower.endswith(".py"):
        return "text/x-python"
    if lower.endswith(".sh"):
        return "text/x-shellscript"
    return "text/plain"


def _manifest_to_yaml(manifest: dict[str, Any]) -> str:
    try:
        import yaml

        return yaml.safe_dump(manifest or {}, allow_unicode=True, sort_keys=False)
    except Exception:
        return json.dumps(manifest or {}, ensure_ascii=False, indent=2) + "\n"


def _parse_manifest_text(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        import yaml

        data = yaml.safe_load(raw)
    except Exception as exc:
        raise ValueError(f"Invalid manifest.yaml: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("manifest.yaml must be a mapping")
    return data


def _apply_manifest_fields(ver: SkillVersion, manifest: dict[str, Any]) -> None:
    """Project known fields from package manifest into version columns."""
    ver.manifest = dict(manifest or {})
    spec = ver.manifest.get("spec") if isinstance(ver.manifest.get("spec"), dict) else {}

    interface_key = ver.manifest.get("interface_key")
    if not interface_key and isinstance(spec, dict):
        implements = spec.get("implements")
        if isinstance(implements, list) and implements:
            interface_key = implements[0]
        elif isinstance(implements, str):
            interface_key = implements
    if interface_key:
        ver.interface_key = str(interface_key)

    input_key = ver.manifest.get("input_contract_key") or (
        spec.get("inputContract") or spec.get("input_contract") if isinstance(spec, dict) else None
    )
    if input_key:
        ver.input_contract_key = str(input_key)

    output_key = ver.manifest.get("output_contract_key") or (
        spec.get("outputContract") or spec.get("output_contract") if isinstance(spec, dict) else None
    )
    if output_key:
        ver.output_contract_key = str(output_key)

    caps = ver.manifest.get("allowed_capabilities")
    if caps is None and isinstance(spec, dict):
        caps = spec.get("allowedCapabilities") or spec.get("allowed_capabilities")
    if isinstance(caps, list):
        ver.allowed_capabilities = [str(c) for c in caps]


def _sync_manifest_file(ver: SkillVersion) -> bool:
    """Keep files[].manifest.yaml content aligned with ver.manifest. Returns True if changed."""
    text = _manifest_to_yaml(ver.manifest or {})
    digest = hashlib.sha256(text.encode()).hexdigest()[:16]
    for i, existing in enumerate(ver.files):
        if existing.path != "manifest.yaml":
            continue
        if (existing.content_text or "").strip() == text.strip() and existing.content_hash == digest:
            return False
        ver.files[i] = existing.model_copy(
            update={
                "kind": "file",
                "media_type": "text/yaml",
                "content_text": text,
                "content_hash": digest,
            }
        )
        return True
    ver.files.insert(
        1 if ver.files else 0,
        SkillFile(
            path="manifest.yaml",
            media_type="text/yaml",
            content_text=text,
            content_hash=digest,
            kind="file",
        ),
    )
    return True


def _hydrate_version_package(
    ver: SkillVersion,
    *,
    persist: bool = False,
    scaffold: bool = True,
) -> SkillVersion:
    """Fill empty/outdated package projections used by the editor."""
    changed = _sync_manifest_file(ver)
    if scaffold:
        files, tests = ensure_quality_scaffold(ver.files, ver.test_cases)
        if files != ver.files:
            ver.files = files
            changed = True
        if tests != ver.test_cases:
            ver.test_cases = tests
            changed = True
    if changed and persist:
        ver.package_checksum = _checksum(ver.skill_markdown, ver.manifest, ver.files)
        ver.updated_at = datetime.utcnow()
        _persist_version(ver)
    return ver


def _version_payload(ver: SkillVersion | None) -> dict[str, Any] | None:
    if ver is None:
        return None
    hydrated = ver.model_copy(deep=True)
    _hydrate_version_package(hydrated, persist=False, scaffold=False)
    return hydrated.model_dump(mode="json")


def _interface_index() -> tuple[set[str], dict[str, list[str]]]:
    return seed_interface_index()


def _validation_context() -> tuple[set[str], dict[str, list[str]], dict[str, tuple[str, str]]]:
    known, caps_map = _interface_index()
    return known, caps_map, interface_contract_index()


def _validate_version(ver: SkillVersion) -> dict[str, Any]:
    known, caps_map, contracts_map = _validation_context()
    return validate_version(
        ver,
        known_interfaces=known,
        interface_capabilities=caps_map,
        interface_contracts=contracts_map,
    )


def _apply_validation(ver: SkillVersion) -> dict[str, Any]:
    report = _validate_version(ver)
    ver.validation_report = report
    ver.validation_status = "valid" if report["valid"] else "invalid"
    if report["valid"] and report.get("warnings"):
        ver.validation_status = "warning"
    return report



def _pg_session():
    from src.platform.db.session import session_scope

    return session_scope()


def _repo(session):
    from src.platform.skills.repository import SkillsRepository

    return SkillsRepository(session)


_SEEDING = False
_PG_SEED_CHECKED = False


def reset_skills_seed_cache() -> None:
    global _PG_SEED_CHECKED
    _PG_SEED_CHECKED = False


def ensure_skills_seeded() -> None:
    global _SEEDING, _PG_SEED_CHECKED
    if skills_use_postgres():
        from src.platform.db.schema import ensure_schema

        ensure_schema()
        if _PG_SEED_CHECKED:
            return
        if _SEEDING:
            return
        _SEEDING = True
        try:
            records, versions = build_seed_catalog()
            with _pg_session() as session:
                seeded = _repo(session).seed_if_empty(records, versions)
                if seeded:
                    logger.info("Skills subsystem seeded into PostgreSQL")
            _PG_SEED_CHECKED = True
        finally:
            _SEEDING = False
        return

    marker = _path(".seeded_skills_v1")
    if marker.exists() and _path("skill_records.json").exists() and _path("skill_versions.json").exists():
        return
    if _SEEDING:
        return
    _SEEDING = True
    try:
        _seed_skills_unlocked()
    finally:
        _SEEDING = False



def _seed_skills_unlocked() -> None:
    marker = _path(".seeded_skills_v1")
    if marker.exists() and _path("skill_records.json").exists() and _path("skill_versions.json").exists():
        return

    records, versions = build_seed_catalog()
    _write_json("skill_records.json", {"skills": [r.model_dump(mode="json") for r in records]})
    _write_json("skill_versions.json", {"versions": [v.model_dump(mode="json") for v in versions]})
    marker.write_text(datetime.utcnow().isoformat() + "\n", encoding="utf-8")
    logger.info("Skills subsystem seeded")


def list_records() -> list[SkillRecord]:
    ensure_skills_seeded()
    if skills_use_postgres():
        with _pg_session() as session:
            return _repo(session).list_records()
    raw = _read_json("skill_records.json", {"skills": []}).get("skills", [])
    return [SkillRecord.model_validate(x) for x in raw]


def list_versions(skill_id: str | None = None) -> list[SkillVersion]:
    ensure_skills_seeded()
    if skills_use_postgres():
        with _pg_session() as session:
            return _repo(session).list_versions(skill_id)
    raw = _read_json("skill_versions.json", {"versions": []}).get("versions", [])
    items = [SkillVersion.model_validate(x) for x in raw]
    if skill_id:
        items = [v for v in items if str(v.skill_id) == skill_id]
    return items


def _save_records(items: list[SkillRecord]) -> None:
    _write_json("skill_records.json", {"skills": [i.model_dump(mode="json") for i in items]})


def _save_versions(items: list[SkillVersion]) -> None:
    _write_json("skill_versions.json", {"versions": [i.model_dump(mode="json") for i in items]})


def get_record(skill_id: str) -> SkillRecord | None:
    if skills_use_postgres():
        ensure_skills_seeded()
        with _pg_session() as session:
            return _repo(session).get_record(skill_id)
    for r in list_records():
        if str(r.id) == skill_id or r.key == skill_id:
            return r
    return None


def get_version(version_id: str) -> SkillVersion | None:
    if skills_use_postgres():
        ensure_skills_seeded()
        with _pg_session() as session:
            return _repo(session).get_version(version_id)
    for v in list_versions():
        if str(v.id) == version_id:
            return v
    return None


def _assert_mutable(rec: SkillRecord) -> None:
    if skill_is_immutable(rec.skill_type):
        raise PermissionError(
            f"Skill type {rec.skill_type} is sealed. Create a derived skill via inheritance."
        )


def _persist_version(ver: SkillVersion) -> SkillVersion:
    if skills_use_postgres():
        with _pg_session() as session:
            return _repo(session).save_version(ver)
    versions = list_versions()
    for i, v in enumerate(versions):
        if str(v.id) == str(ver.id):
            versions[i] = ver
            break
    else:
        versions.append(ver)
    _save_versions(versions)
    return ver


def _persist_record(rec: SkillRecord) -> SkillRecord:
    if skills_use_postgres():
        with _pg_session() as session:
            return _repo(session).save_record(rec)
    records = list_records()
    for i, r in enumerate(records):
        if str(r.id) == str(rec.id):
            records[i] = rec
            break
    else:
        records.append(rec)
    _save_records(records)
    return rec


def _insert_skill(rec: SkillRecord, ver: SkillVersion) -> None:
    if skills_use_postgres():
        with _pg_session() as session:
            _repo(session).insert_skill_with_version(rec, ver)
        return
    _save_records(list_records() + [rec])
    _save_versions(list_versions() + [ver])


def metrics() -> SkillMetrics:
    records = list_records()
    versions = list_versions()
    interfaces = {v.interface_key for v in versions if v.interface_key}
    published = [v for v in versions if v.status == "PUBLISHED"]
    ok = sum(1 for v in published if v.validation_status in ("valid", "warning"))
    pct = round(100.0 * ok / len(published), 1) if published else 100.0
    corporate = sum(1 for r in records if r.skill_type == "CORPORATE")
    return SkillMetrics(
        skills=len(records),
        published_versions=len(published),
        interfaces=len(interfaces),
        validation_pass_pct=pct,
        corporate_skills=corporate,
    )


def catalog_items(
    query: str = "",
    skill_type: str = "",
    status: str = "",
    interface_key: str = "",
) -> list[SkillCatalogItem]:
    from src.platform.executions import service as executions_svc

    versions = list_versions()
    records = list_records()
    by_skill: dict[str, list[SkillVersion]] = {}
    for v in versions:
        by_skill.setdefault(str(v.skill_id), []).append(v)
    by_id = {str(r.id): r for r in records}
    usage = executions_svc.usage_stats().get("skill", {})

    items: list[SkillCatalogItem] = []
    for r in records:
        vers = by_skill.get(str(r.id), [])
        published = next((v for v in vers if v.status == "PUBLISHED"), None)
        draft = next((v for v in vers if v.status == "DRAFT"), None)
        active = published or draft
        st = (
            "DEPRECATED" if r.status == "deprecated" or (published and published.status == "DEPRECATED")
            else ("PUBLISHED" if published else "DRAFT")
        )
        parent = by_id.get(str(r.parent_skill_id)) if r.parent_skill_id else None
        blob = " ".join([
            r.name, r.key, r.description, r.owner_team,
            active.interface_key if active else "",
            " ".join(active.allowed_capabilities if active else []),
            parent.key if parent else "",
            parent.name if parent else "",
        ]).lower()
        if query and query.lower() not in blob:
            continue
        if skill_type and skill_type.upper() not in ("", "ALL") and r.skill_type != skill_type.upper():
            continue
        if status and status.upper() not in ("", "ALL", "ALL STATUSES") and st != status.upper():
            continue
        if interface_key and active and active.interface_key != interface_key:
            continue
        stats = usage.get(r.key) or {}
        items.append(SkillCatalogItem(
            id=str(r.id),
            key=r.key,
            name=r.name,
            description=r.description,
            skill_type=r.skill_type,
            status=st,
            owner=r.owner_team,
            version=active.semantic_version if active else None,
            interfaces=[active.interface_key] if active and active.interface_key else [],
            capabilities=list(active.allowed_capabilities) if active else [],
            runtime_type=active.runtime_type if active else "",
            validation_status=active.validation_status if active else "unknown",
            runs_30d=int(stats.get("count") or 0),
            immutable=skill_is_immutable(r.skill_type),
            parent_skill_id=str(r.parent_skill_id) if r.parent_skill_id else None,
            parent_key=parent.key if parent else None,
        ))
    return items


def detail(skill_id: str) -> dict[str, Any]:
    from src.platform.executions import service as executions_svc

    rec = get_record(skill_id)
    if not rec:
        raise KeyError("Skill not found")
    versions = sorted(list_versions(str(rec.id)), key=lambda v: v.semantic_version, reverse=True)
    published = next((v for v in versions if v.status == "PUBLISHED"), None)
    draft = next((v for v in versions if v.status == "DRAFT"), None)
    current = published or draft or (versions[0] if versions else None)
    parent = get_record(str(rec.parent_skill_id)) if rec.parent_skill_id else None
    stats = executions_svc.stats_for("skill", rec.key)
    skill_payload = {
        **rec.model_dump(mode="json"),
        "immutable": skill_is_immutable(rec.skill_type),
        "runs_30d": int(stats.get("count") or 0),
        "success_rate": float(stats.get("success_rate") or 0.0),
    }
    return {
        "skill": skill_payload,
        "parent": (
            {
                "id": str(parent.id),
                "key": parent.key,
                "name": parent.name,
                "skill_type": parent.skill_type,
            }
            if parent
            else None
        ),
        "current_version": _version_payload(current),
        "published_version": _version_payload(published),
        "draft_version": _version_payload(draft),
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


def create_skill(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_skills_seeded()
    name = payload["name"]
    key = payload.get("key") or name.lower().replace(" ", "-")
    if get_record(key):
        raise ValueError(f"Skill key already exists: {key}")
    skill_type = (payload.get("skill_type") or payload.get("type") or "TEAM").upper()
    if skill_is_immutable(skill_type):
        raise ValueError(
            f"Cannot create {skill_type} skills from the catalog. "
            "Inherit from an existing Corporate/Core skill instead."
        )
    known, caps_map = _interface_index()
    interface_key = payload.get("interface_key") or "analysis.system_requirements.generate@1"
    if known and interface_key not in known:
        raise ValueError(f"Unknown interface: {interface_key}")
    caps = payload.get("allowed_capabilities") or caps_map.get(interface_key, ["context.read"])
    default_in, default_out = interface_contracts(interface_key)
    input_key = payload.get("input_contract_key") or default_in
    output_key = payload.get("output_contract_key") or default_out
    md = payload.get("skill_markdown") or default_skill_md(name, interface_key, caps)
    manifest = {
        "apiVersion": "platform.skills/v1",
        "kind": "Skill",
        "metadata": {"key": key},
        "spec": {
            "version": payload.get("semantic_version", "0.1.0"),
            "implements": [interface_key],
            "inputContract": input_key,
            "outputContract": output_key,
            "allowedCapabilities": list(caps),
        },
    }
    files = [
        SkillFile(path="SKILL.md", media_type="text/markdown", content_text=md),
        SkillFile(
            path="manifest.yaml",
            media_type="text/yaml",
            content_text=_manifest_to_yaml(manifest),
        ),
        SkillFile(path="templates/", kind="folder", media_type="inode/directory"),
        SkillFile(path="scripts/", kind="folder", media_type="inode/directory"),
        SkillFile(path="agents/", kind="folder", media_type="inode/directory"),
    ]
    files, tests = ensure_quality_scaffold(files, [])
    rec = SkillRecord(
        key=key,
        name=name,
        description=payload.get("description", ""),
        skill_type=skill_type,  # type: ignore[arg-type]
        owner_team=payload.get("owner_team") or payload.get("owner") or "Platform",
        status="draft",
    )
    ver = SkillVersion(
        skill_id=rec.id,
        semantic_version=payload.get("semantic_version", "0.1.0"),
        status="DRAFT",
        skill_markdown=md,
        manifest=manifest,
        package_checksum=_checksum(md, manifest, files),
        interface_key=interface_key,
        input_contract_key=input_key,
        output_contract_key=output_key,
        allowed_capabilities=list(caps),
        files=files,
        test_cases=tests,
        runtime_type=payload.get("runtime_type", "qwen-code-cli"),
    )
    _apply_validation(ver)
    rec.current_draft_version_id = ver.id
    _insert_skill(rec, ver)
    append_audit("create", "skill", str(rec.id), f"Created skill {rec.key}")
    return detail(str(rec.id))


def update_skill(skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    rec = get_record(skill_id)
    if not rec:
        raise KeyError("Skill not found")
    _assert_mutable(rec)
    name = payload.get("name")
    if name is not None:
        name = str(name).strip()
        if not name:
            raise ValueError("Name is required")
    data = rec.model_dump()
    if name is not None:
        data["name"] = name
    if "description" in payload:
        data["description"] = str(payload.get("description") or "")
    if payload.get("owner_team"):
        data["owner_team"] = str(payload["owner_team"]).strip()
    data["updated_at"] = datetime.utcnow()
    rec = SkillRecord.model_validate(data)
    _persist_record(rec)
    append_audit("update", "skill", str(rec.id), f"Updated skill {rec.key}")
    return detail(str(rec.id))


def delete_skill(skill_id: str) -> dict[str, Any]:
    rec = get_record(skill_id)
    if not rec:
        raise KeyError("Skill not found")
    _assert_mutable(rec)
    from src.platform.graphs.bindings import graphs_using_skill

    consumers = graphs_using_skill(rec.key)
    if consumers:
        raise ValueError(
            "Cannot delete: referenced in graphs "
            + ", ".join(consumers)
        )
    if skills_use_postgres():
        with _pg_session() as session:
            _repo(session).delete_skill(str(rec.id))
    else:
        records = [r for r in list_records() if str(r.id) != str(rec.id)]
        versions = [v for v in list_versions() if str(v.skill_id) != str(rec.id)]
        _save_records(records)
        _save_versions(versions)
    append_audit("delete", "skill", str(rec.id), f"Deleted skill {rec.key}")
    return {"ok": True, "id": str(rec.id), "key": rec.key}


def save_draft_content(skill_id: str, version_id: str, skill_markdown: str, if_match: str | None = None) -> SkillVersion:
    rec = get_record(skill_id)
    ver = get_version(version_id)
    if not rec or not ver or str(ver.skill_id) != str(rec.id):
        raise KeyError("Version not found")
    _assert_mutable(rec)
    if ver.status == "PUBLISHED":
        raise PermissionError("Cannot modify published version")
    if if_match is not None and if_match.strip('"') != str(ver.revision):
        raise RuntimeError("SKILL_VERSION_CONFLICT")
    ver.skill_markdown = skill_markdown
    for f in ver.files:
        if f.path == "SKILL.md":
            f.content_text = skill_markdown
            break
    else:
        ver.files.append(SkillFile(path="SKILL.md", media_type="text/markdown", content_text=skill_markdown))
    _sync_manifest_file(ver)
    ver.package_checksum = _checksum(skill_markdown, ver.manifest, ver.files)
    ver.revision += 1
    ver.updated_at = datetime.utcnow()
    _apply_validation(ver)
    _persist_version(ver)
    append_audit("draft_save", "skill_version", str(ver.id), f"Saved draft rev {ver.revision}")
    return ver


def upsert_package_entry(
    skill_id: str,
    version_id: str,
    *,
    path: str,
    content_text: str = "",
    kind: str = "file",
    if_match: str | None = None,
) -> SkillVersion:
    """Create or update a file/folder entry in a draft package."""
    rec = get_record(skill_id)
    ver = get_version(version_id)
    if not rec or not ver or str(ver.skill_id) != str(rec.id):
        raise KeyError("Version not found")
    _assert_mutable(rec)
    if ver.status != "DRAFT":
        raise PermissionError("Cannot modify published version")
    if if_match is not None and if_match.strip('"') != str(ver.revision):
        raise RuntimeError("SKILL_VERSION_CONFLICT")

    is_folder = kind == "folder" or path.endswith("/")
    normalized = _normalize_package_path(path, folder=is_folder)
    if is_folder:
        entry = SkillFile(path=normalized, kind="folder", media_type="inode/directory", content_text="")
    else:
        entry = SkillFile(
            path=normalized,
            kind="file",
            media_type=_media_type_for(normalized),
            content_text=content_text,
            content_hash=hashlib.sha256(content_text.encode()).hexdigest()[:16],
        )

    # Ensure parent folders exist as markers
    parts = normalized.rstrip("/").split("/")
    for i in range(1, len(parts)):
        folder_path = "/".join(parts[:i]) + "/"
        if not any(f.path == folder_path for f in ver.files):
            ver.files.append(SkillFile(path=folder_path, kind="folder", media_type="inode/directory"))

    replaced = False
    for i, existing in enumerate(ver.files):
        if existing.path == entry.path:
            ver.files[i] = entry
            replaced = True
            break
    if not replaced:
        ver.files.append(entry)

    if entry.path == "SKILL.md":
        ver.skill_markdown = entry.content_text
    elif entry.path == "manifest.yaml":
        parsed = _parse_manifest_text(entry.content_text)
        _apply_manifest_fields(ver, parsed)
        text = _manifest_to_yaml(ver.manifest)
        entry = entry.model_copy(
            update={
                "content_text": text,
                "content_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
            }
        )
        for i, existing in enumerate(ver.files):
            if existing.path == entry.path:
                ver.files[i] = entry
                break
        else:
            ver.files.append(entry)

    ver.package_checksum = _checksum(ver.skill_markdown, ver.manifest, ver.files)
    ver.revision += 1
    ver.updated_at = datetime.utcnow()
    _apply_validation(ver)
    _persist_version(ver)
    append_audit("package_upsert", "skill_version", str(ver.id), f"Upsert {entry.path}")
    return ver


def delete_package_entry(skill_id: str, version_id: str, path: str, if_match: str | None = None) -> SkillVersion:
    rec = get_record(skill_id)
    ver = get_version(version_id)
    if not rec or not ver or str(ver.skill_id) != str(rec.id):
        raise KeyError("Version not found")
    _assert_mutable(rec)
    if ver.status != "DRAFT":
        raise PermissionError("Cannot modify published version")
    if if_match is not None and if_match.strip('"') != str(ver.revision):
        raise RuntimeError("SKILL_VERSION_CONFLICT")

    normalized = path.strip().replace("\\", "/").lstrip("/")
    if normalized in ("SKILL.md",):
        raise ValueError("SKILL.md cannot be deleted")

    folder_prefix = normalized if normalized.endswith("/") else None
    remaining: list[SkillFile] = []
    removed = False
    for f in ver.files:
        if folder_prefix and (f.path == folder_prefix or f.path.startswith(folder_prefix)):
            removed = True
            continue
        if f.path == normalized or f.path == normalized.rstrip("/") + "/":
            removed = True
            continue
        remaining.append(f)
    if not removed:
        raise KeyError("Package entry not found")
    ver.files = remaining
    ver.package_checksum = _checksum(ver.skill_markdown, ver.manifest, ver.files)
    ver.revision += 1
    ver.updated_at = datetime.utcnow()
    _persist_version(ver)
    append_audit("package_delete", "skill_version", str(ver.id), f"Deleted {normalized}")
    return ver


def move_package_entry(
    skill_id: str,
    version_id: str,
    *,
    from_path: str,
    to_path: str,
    if_match: str | None = None,
) -> SkillVersion:
    """Move/rename a file or folder within a draft package."""
    rec = get_record(skill_id)
    ver = get_version(version_id)
    if not rec or not ver or str(ver.skill_id) != str(rec.id):
        raise KeyError("Version not found")
    _assert_mutable(rec)
    if ver.status != "DRAFT":
        raise PermissionError("Cannot modify published version")
    if if_match is not None and if_match.strip('"') != str(ver.revision):
        raise RuntimeError("SKILL_VERSION_CONFLICT")

    src_raw = (from_path or "").strip().replace("\\", "/").lstrip("/")
    dest_raw = (to_path or "").strip().replace("\\", "/").lstrip("/")
    if not src_raw or not dest_raw:
        raise ValueError("from_path and to_path are required")
    if src_raw in ("SKILL.md",) or dest_raw in ("SKILL.md",):
        raise ValueError("SKILL.md must stay at package root")

    src_is_folder = src_raw.endswith("/") or any(
        f.path == src_raw.rstrip("/") + "/" or (f.kind == "folder" and f.path.rstrip("/") == src_raw.rstrip("/"))
        for f in ver.files
    )
    # Destination may be a folder drop target: keep basename under that folder.
    if dest_raw.endswith("/") and not src_is_folder:
        base = src_raw.rstrip("/").split("/")[-1]
        dest_raw = f"{dest_raw}{base}"
    elif dest_raw.endswith("/") and src_is_folder:
        base = src_raw.rstrip("/").split("/")[-1]
        dest_raw = f"{dest_raw}{base}/"

    src = _normalize_package_path(src_raw, folder=src_is_folder)
    dest = _normalize_package_path(dest_raw, folder=src_is_folder)
    if src == dest:
        return ver

    if src_is_folder:
        src_prefix = src
        dest_prefix = dest
        if dest_prefix.startswith(src_prefix):
            raise ValueError("Cannot move a folder into itself")
        occupied = {
            f.path
            for f in ver.files
            if not (f.path == src_prefix or f.path.startswith(src_prefix))
        }
        relocated: list[SkillFile] = []
        for f in ver.files:
            if f.path == src_prefix or f.path.startswith(src_prefix):
                suffix = f.path[len(src_prefix):]
                new_path = dest_prefix + suffix
                if new_path in occupied:
                    raise ValueError(f"Target already exists: {new_path}")
                relocated.append(f.model_copy(update={"path": new_path}))
            else:
                relocated.append(f)
        if not any(f.path == dest_prefix for f in relocated):
            relocated.append(SkillFile(path=dest_prefix, kind="folder", media_type="inode/directory"))
        ver.files = relocated
    else:
        src_entry = next((f for f in ver.files if f.path == src), None)
        if not src_entry:
            raise KeyError("Package entry not found")
        if any(f.path == dest for f in ver.files):
            raise ValueError(f"Target already exists: {dest}")
        parts = dest.split("/")
        for i in range(1, len(parts)):
            folder_path = "/".join(parts[:i]) + "/"
            if not any(f.path == folder_path for f in ver.files):
                ver.files.append(SkillFile(path=folder_path, kind="folder", media_type="inode/directory"))
        for i, f in enumerate(ver.files):
            if f.path == src:
                ver.files[i] = f.model_copy(
                    update={"path": dest, "media_type": _media_type_for(dest)}
                )
                break

    ver.package_checksum = _checksum(ver.skill_markdown, ver.manifest, ver.files)
    ver.revision += 1
    ver.updated_at = datetime.utcnow()
    _apply_validation(ver)
    _persist_version(ver)
    append_audit("package_move", "skill_version", str(ver.id), f"Moved {src} -> {dest}")
    return ver


def list_package_files(skill_id: str, version_id: str) -> list[dict[str, Any]]:
    rec = get_record(skill_id)
    ver = get_version(version_id)
    if not rec or not ver or str(ver.skill_id) != str(rec.id):
        raise KeyError("Version not found")
    hydrated = ver.model_copy(deep=True)
    _hydrate_version_package(hydrated, persist=False, scaffold=False)
    return [f.model_dump(mode="json") for f in hydrated.files]


def validate_skill_version(skill_id: str, version_id: str) -> dict[str, Any]:
    rec = get_record(skill_id)
    ver = get_version(version_id)
    if not rec or not ver or str(ver.skill_id) != str(rec.id):
        raise KeyError("Version not found")
    # Repair empty manifest.yaml and quality scaffold before checking.
    _hydrate_version_package(ver, persist=False, scaffold=True)
    report = _apply_validation(ver)
    _persist_version(ver)
    return report


def publish_version(skill_id: str, version_id: str) -> dict[str, Any]:
    rec = get_record(skill_id)
    ver = get_version(version_id)
    if not rec or not ver or str(ver.skill_id) != str(rec.id):
        raise KeyError("Version not found")
    _assert_mutable(rec)
    report = validate_skill_version(skill_id, version_id)
    if not report["valid"]:
        raise ValueError("Cannot publish invalid skill version")
    if skills_use_postgres():
        with _pg_session() as session:
            _repo(session).publish_version(rec.id, ver.id)
    else:
        from src.platform.versioning import apply_json_publish

        versions = list_versions()
        records = list_records()
        apply_json_publish(
            versions,
            records,
            parent_id=str(rec.id),
            version_id=str(ver.id),
            parent_attr="skill_id",
        )
        _save_versions(versions)
        _save_records(records)
    append_audit("publish", "skill_version", str(ver.id), f"Published {rec.key}@{ver.semantic_version}")
    return detail(str(rec.id))


def create_draft(skill_id: str) -> dict[str, Any]:
    rec = get_record(skill_id)
    if not rec:
        raise KeyError("Skill not found")
    _assert_mutable(rec)
    versions = list_versions(str(rec.id))
    base = next((v for v in versions if v.status == "PUBLISHED"), None) or (versions[0] if versions else None)
    if not base:
        raise ValueError("No version to clone")
    parts = (base.semantic_version.split(".") + ["0", "0"])[:3]
    draft = SkillVersion(
        skill_id=rec.id,
        semantic_version=f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}",
        status="DRAFT",
        skill_markdown=base.skill_markdown,
        manifest=dict(base.manifest),
        package_checksum=base.package_checksum,
        runtime_type=base.runtime_type,
        interface_key=base.interface_key,
        input_contract_key=base.input_contract_key,
        output_contract_key=base.output_contract_key,
        allowed_capabilities=list(base.allowed_capabilities),
        files=[f.model_copy(deep=True) for f in base.files],
        test_cases=[t.model_copy(deep=True) for t in base.test_cases],
        validation_status=base.validation_status,
        validation_report=dict(base.validation_report),
    )
    _hydrate_version_package(draft, persist=False, scaffold=True)
    draft.package_checksum = _checksum(draft.skill_markdown, draft.manifest, draft.files)
    _apply_validation(draft)
    if skills_use_postgres():
        with _pg_session() as session:
            _repo(session).add_draft(rec.id, draft)
    else:
        records = list_records()
        for r in records:
            if str(r.id) == str(rec.id):
                r.current_draft_version_id = draft.id
                r.updated_at = datetime.utcnow()
        _save_versions(list_versions() + [draft])
        _save_records(records)
    return detail(str(rec.id))


def inherit_skill(source_skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a mutable TEAM skill inheriting a published Corporate/Core/Team package."""
    source = get_record(source_skill_id)
    if not source:
        raise KeyError("Skill not found")
    published = next(
        (version for version in list_versions(str(source.id)) if version.status == "PUBLISHED"),
        None,
    )
    if not published:
        raise ValueError("Source skill has no published version to inherit from")
    key = payload.get("key") or f"{source.key}-derived"
    key = re.sub(r"[^a-z0-9\-]+", "-", key.lower()).strip("-")
    if get_record(key):
        raise ValueError(f"Skill key already exists: {key}")
    name = payload.get("name") or f"{source.name} (наследник)"
    now = datetime.utcnow()
    record = SkillRecord(
        id=_id("skill", key) if not skills_use_postgres() else uuid4(),
        key=key,
        name=name,
        description=payload.get("description") or (
            f"Наследует {source.name}. Добавьте инструкции, шаблоны, скрипты или субагентов."
        ),
        skill_type="TEAM",
        status="draft",
        owner_team=payload.get("owner_team") or payload.get("owner") or source.owner_team,
        parent_skill_id=source.id,
        parent_version_id=published.id,
        runs_30d=0,
        success_rate=0.0,
        bindings=[],
        created_at=now,
        updated_at=now,
        revision=1,
    )
    manifest = json.loads(json.dumps(published.manifest))
    manifest.setdefault("metadata", {})["key"] = key
    manifest.setdefault("metadata", {})["inherits"] = {
        "parent_key": source.key,
        "parent_version": published.semantic_version,
    }
    manifest.setdefault("spec", {})["version"] = "0.1.0"
    files = [f.model_copy(deep=True) for f in published.files]
    # Ensure extensibility folders exist for derived skills
    for folder in ("templates/", "scripts/", "agents/", "examples/"):
        if not any(f.path == folder for f in files):
            files.append(SkillFile(path=folder, kind="folder", media_type="inode/directory"))
    tests = [t.model_copy(deep=True) for t in published.test_cases]
    files, tests = ensure_quality_scaffold(files, tests)

    draft = SkillVersion(
        id=_id("skv", f"{key}-0.1.0") if not skills_use_postgres() else uuid4(),
        skill_id=record.id,
        semantic_version="0.1.0",
        status="DRAFT",
        skill_markdown=published.skill_markdown,
        manifest=manifest,
        package_checksum=_checksum(published.skill_markdown, manifest, files),
        runtime_type=published.runtime_type,
        interface_key=published.interface_key,
        input_contract_key=published.input_contract_key,
        output_contract_key=published.output_contract_key,
        allowed_capabilities=list(published.allowed_capabilities),
        files=files,
        test_cases=tests,
        validation_status=published.validation_status,
        validation_report=dict(published.validation_report),
        revision=1,
        created_at=now,
        updated_at=now,
    )
    _sync_manifest_file(draft)
    draft.package_checksum = _checksum(draft.skill_markdown, draft.manifest, draft.files)
    _apply_validation(draft)
    record.current_draft_version_id = draft.id
    _insert_skill(record, draft)
    append_audit("inherit", "skill", str(record.id), f"Inherited {source.key} as {key}")
    return detail(str(record.id))
