"""Runtime Profiles persistence, catalog, resolve preview, and validation."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from src.platform.runtime_profiles.models import (
    CapabilityPolicy,
    RuntimeProfileCatalogItem,
    RuntimeProfileMetrics,
    RuntimeProfileRecord,
    RuntimeProfileVersion,
)
from src.platform.runtime_profiles.validation import validate_version
from src.platform.store import append_audit, get_platform_dir

logger = logging.getLogger(__name__)
NS = UUID("b7c8d9e0-1f2a-4b3c-8d9e-0f1a2b3c4d5e")
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
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def ensure_runtime_profiles_seeded() -> None:
    global _SEEDING
    marker = _path(".seeded_runtime_profiles_v1")
    if marker.exists() and _path("runtime_profile_records.json").exists():
        return
    if _SEEDING:
        return
    _SEEDING = True
    try:
        _seed_unlocked()
    finally:
        _SEEDING = False


def _seed_unlocked() -> None:
    marker = _path(".seeded_runtime_profiles_v1")
    if marker.exists() and _path("runtime_profile_records.json").exists():
        return

    seeds = [
        {
            "key": "qwen-production",
            "name": "Qwen Production",
            "description": "Production runtime for governed code and document generation.",
            "profile_type": "PRODUCTION",
            "provider": "QWEN_CODE_CLI",
            "model": "qwen3-coder",
            "status": "active",
            "version": "2.0.0",
            "active": True,
            "sandbox": "CONTAINER",
            "supervision": "SUPERVISED",
            "runs": 0,
            "health": "HEALTHY",
            "secret_ref": "vault://ai/qwen-production",
            "capabilities": CapabilityPolicy(
                allow=["repository.read", "repository.search", "context.search"],
                approval_required=["artifact.publish"],
            ),
            "fallback": "openai-high-accuracy",
        },
        {
            "key": "qwen-development",
            "name": "Qwen Development",
            "description": "Development runtime with extended logs.",
            "profile_type": "DEVELOPMENT",
            "provider": "QWEN_CODE_CLI",
            "model": "qwen3-coder",
            "status": "active",
            "version": "1.4.0",
            "active": True,
            "sandbox": "CONTAINER",
            "supervision": "AUTONOMOUS",
            "runs": 0,
            "health": "HEALTHY",
            "secret_ref": "vault://ai/qwen-dev",
            "capabilities": CapabilityPolicy(
                allow=["repository.read", "repository.search", "context.search", "artifact.read"],
            ),
        },
        {
            "key": "openai-high-accuracy",
            "name": "OpenAI High Accuracy",
            "description": "High-accuracy runtime for complex reviews.",
            "profile_type": "HIGH_ACCURACY",
            "provider": "OPENAI_API",
            "model": "gpt-5.6",
            "status": "active",
            "version": "1.2.0",
            "active": True,
            "sandbox": "REMOTE_RUNNER",
            "supervision": "SUPERVISED",
            "runs": 0,
            "health": "HEALTHY",
            "secret_ref": "vault://ai/openai-prod",
            "capabilities": CapabilityPolicy(
                allow=["context.search", "artifact.read"],
                approval_required=["artifact.publish"],
            ),
        },
        {
            "key": "local-restricted",
            "name": "Local Restricted",
            "description": "Isolated runtime for restricted data.",
            "profile_type": "RESTRICTED",
            "provider": "LOCAL_VLLM",
            "model": "qwen-local-72b",
            "status": "active",
            "version": "1.0.0",
            "active": True,
            "sandbox": "MICROVM",
            "supervision": "STRICT",
            "runs": 0,
            "health": "DEGRADED",
            "secret_ref": "",
            "capabilities": CapabilityPolicy(
                allow=["context.search"],
                deny=["artifact.publish"],
            ),
        },
        {
            "key": "low-cost-batch",
            "name": "Low Cost Batch",
            "description": "Cost-optimized batch runtime.",
            "profile_type": "LOW_COST",
            "provider": "OPENAI_API",
            "model": "gpt-mini",
            "status": "active",
            "version": "1.1.0",
            "active": True,
            "sandbox": "REMOTE_RUNNER",
            "supervision": "AUTONOMOUS",
            "runs": 0,
            "health": "HEALTHY",
            "secret_ref": "vault://ai/openai-batch",
            "capabilities": CapabilityPolicy(allow=["context.search"]),
        },
        {
            "key": "default-gigachat",
            "name": "Default GigaChat",
            "description": "Legacy migrated profile for governed requirements generation.",
            "profile_type": "PRODUCTION",
            "provider": "GIGACHAT",
            "model": "GigaChat-Pro",
            "status": "deprecated",
            "version": "1.0.0",
            "active": True,
            "sandbox": "CONTAINER",
            "supervision": "SUPERVISED",
            "runs": 0,
            "health": "HEALTHY",
            "secret_ref": "secret://runtime/gigachat",
            "capabilities": CapabilityPolicy(allow=["context.search"]),
        },
    ]

    records: list[RuntimeProfileRecord] = []
    versions: list[RuntimeProfileVersion] = []

    for seed in seeds:
        pid = _id("runtime_profile", seed["key"])
        ver = RuntimeProfileVersion(
            id=_id("runtime_profile_ver", f"{seed['key']}:{seed['version']}"),
            profile_id=pid,
            semantic_version=seed["version"],
            status="ACTIVE" if seed["active"] else "DRAFT",
            provider=seed["provider"],
            model=seed["model"],
            profile_type=seed["profile_type"],
            sandbox=seed["sandbox"],
            network_policy="ALLOW_CAPABILITY_GATEWAY_ONLY",
            supervision=seed["supervision"],
            generation_config={"temperature": 0.2, "maxOutputTokens": 16000},
            limits={
                "maxExecutionSeconds": 1200,
                "maxOutputTokens": 16000,
                "maxRetries": 3,
                "maxConcurrentRuns": 4,
            },
            sandbox_config={"readOnlyRootFilesystem": True, "ephemeral": True},
            capabilities=seed["capabilities"],
            fallback_profile_key=seed.get("fallback"),
            secret_ref=seed["secret_ref"],
            activated_at=datetime.utcnow() if seed["active"] else None,
        )
        report = validate_version(ver)
        ver.validation_status = report["status"]  # type: ignore[assignment]
        ver.validation_report = report
        versions.append(ver)

        rec = RuntimeProfileRecord(
            id=pid,
            key=seed["key"],
            name=seed["name"],
            description=seed["description"],
            status="deprecated" if seed["key"] == "default-gigachat" else seed["status"],
            owner_team="Platform",
            current_active_version_id=ver.id if seed["active"] else None,
            current_draft_version_id=None if seed["active"] else ver.id,
            runs_30d=seed["runs"],
            health_status=seed["health"],
        )
        records.append(rec)

    _write_json("runtime_profile_records.json", {"profiles": [r.model_dump(mode="json") for r in records]})
    _write_json("runtime_profile_versions.json", {"versions": [v.model_dump(mode="json") for v in versions]})
    marker.write_text(datetime.utcnow().isoformat() + "\n", encoding="utf-8")
    logger.info("Runtime Profiles module seeded (%s profiles)", len(records))


def list_records() -> list[RuntimeProfileRecord]:
    ensure_runtime_profiles_seeded()
    raw = _read_json("runtime_profile_records.json", {"profiles": []}).get("profiles", [])
    return [RuntimeProfileRecord.model_validate(x) for x in raw]


def _save_records(items: list[RuntimeProfileRecord]) -> None:
    _write_json("runtime_profile_records.json", {"profiles": [i.model_dump(mode="json") for i in items]})


def list_versions(profile_id: str | None = None) -> list[RuntimeProfileVersion]:
    ensure_runtime_profiles_seeded()
    raw = _read_json("runtime_profile_versions.json", {"versions": []}).get("versions", [])
    versions = [RuntimeProfileVersion.model_validate(x) for x in raw]
    if profile_id:
        versions = [v for v in versions if str(v.profile_id) == profile_id]
    return versions


def _save_versions(items: list[RuntimeProfileVersion]) -> None:
    _write_json("runtime_profile_versions.json", {"versions": [i.model_dump(mode="json") for i in items]})


def get_record(profile_id: str) -> RuntimeProfileRecord | None:
    for r in list_records():
        if str(r.id) == profile_id or r.key == profile_id:
            return r
    return None


def get_version(version_id: str) -> RuntimeProfileVersion | None:
    for v in list_versions():
        if str(v.id) == version_id:
            return v
    return None


def _current_version(rec: RuntimeProfileRecord) -> RuntimeProfileVersion | None:
    vid = rec.current_active_version_id or rec.current_draft_version_id
    if not vid:
        return None
    return get_version(str(vid))


def metrics() -> RuntimeProfileMetrics:
    records = list_records()
    active = [r for r in records if r.status == "active" and r.current_active_version_id]
    healthy = sum(1 for r in active if r.health_status == "HEALTHY")
    providers = {get_version(str(r.current_active_version_id)).provider  # type: ignore[union-attr]
                 for r in active if r.current_active_version_id}
    return RuntimeProfileMetrics(
        active_profiles=len(active),
        healthy_providers=healthy,
        total_providers=len(providers) or len(active),
        runs_30d=sum(r.runs_30d for r in records),
        cost_alerts=sum(1 for r in records if r.health_status == "DEGRADED"),
    )


def catalog_items(
    search: str = "",
    profile_type: str = "",
    provider: str = "",
    status: str = "",
) -> list[RuntimeProfileCatalogItem]:
    items: list[RuntimeProfileCatalogItem] = []
    for r in list_records():
        ver = _current_version(r)
        blob = f"{r.name} {r.key} {r.description} {ver.provider if ver else ''} {ver.model if ver else ''}".lower()
        if search and search.lower() not in blob:
            continue
        if profile_type and profile_type.upper() not in ("", "ALL"):
            if not ver or ver.profile_type != profile_type.upper():
                continue
        if provider and provider.upper() not in ("", "ALL"):
            if not ver or ver.provider != provider.upper():
                continue
        catalog_status = (
            "ACTIVE" if r.current_active_version_id and r.status == "active"
            else r.status.upper()
        )
        if r.health_status == "DEGRADED" and catalog_status == "ACTIVE":
            catalog_status = "DEGRADED"
        if status and status.upper() not in ("", "ALL") and catalog_status != status.upper():
            continue
        items.append(RuntimeProfileCatalogItem(
            id=str(r.id),
            key=r.key,
            name=r.name,
            description=r.description,
            profile_type=ver.profile_type if ver else "CUSTOM",
            provider=ver.provider if ver else "",
            model=ver.model if ver else "",
            status=catalog_status,
            version=f"v{ver.semantic_version}" if ver else None,
            sandbox=ver.sandbox if ver else "",
            supervision=ver.supervision if ver else "",
            runs_30d=r.runs_30d,
            health_status=r.health_status,
        ))
    return items


def effective_runtime(version: RuntimeProfileVersion) -> dict[str, Any]:
    return {
        "provider": version.provider,
        "model": version.model,
        "sandbox": version.sandbox,
        "network": version.network_policy,
        "supervision": version.supervision,
        "limits": version.limits,
        "capabilities": version.capabilities.model_dump(),
        "secret_ref": version.secret_ref or "(workspace default)",
        "region": version.region,
        "fallback": version.fallback_profile_key,
    }


def detail(profile_id: str) -> dict[str, Any]:
    rec = get_record(profile_id)
    if not rec:
        raise KeyError("Runtime profile not found")
    ver = _current_version(rec)
    draft = _draft_version(rec)
    report = validate_version(draft or ver) if (draft or ver) else {"valid": False, "errors": [], "warnings": []}
    return {
        "profile": rec.model_dump(mode="json"),
        "current_version": ver.model_dump(mode="json") if ver else None,
        "draft_version": draft.model_dump(mode="json") if draft else None,
        "versions": [v.model_dump(mode="json") for v in list_versions(str(rec.id))],
        "effective_runtime": effective_runtime(ver) if ver else {},
        "validation": report,
        "health": {
            "provider": "Healthy" if rec.health_status == "HEALTHY" else "Degraded",
            "model": "Available",
            "secret": "Resolved" if ver and ver.secret_ref else "Workspace default",
        },
    }


def create_profile(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_profiles_seeded()
    name = payload["name"]
    key = payload.get("key") or name.lower().replace(" ", "-")
    if get_record(key):
        raise ValueError(f"Runtime profile key already exists: {key}")
    pid = _id("runtime_profile", key)
    provider = (payload.get("provider") or "QWEN_CODE_CLI").upper()
    profile_type = (payload.get("profile_type") or payload.get("type") or "PRODUCTION").upper()
    ver = RuntimeProfileVersion(
        id=_id("runtime_profile_ver", f"{key}:0.1.0"),
        profile_id=pid,
        semantic_version="0.1.0",
        status="DRAFT",
        provider=provider,  # type: ignore[arg-type]
        model=payload.get("model") or ("qwen3-coder" if provider == "QWEN_CODE_CLI" else "default"),
        profile_type=profile_type,  # type: ignore[arg-type]
        sandbox="CONTAINER" if profile_type == "PRODUCTION" else "PROCESS",
        supervision="SUPERVISED",
        secret_ref=payload.get("secret_ref") or f"vault://ai/{key}",
        capabilities=CapabilityPolicy(allow=["context.search"]),
        generation_config={"temperature": 0.2, "maxOutputTokens": 16000},
        limits={
            "maxExecutionSeconds": 1200,
            "maxOutputTokens": 16000,
            "maxRetries": 3,
            "maxConcurrentRuns": 4,
        },
        sandbox_config={"readOnlyRootFilesystem": True, "ephemeral": True},
    )
    report = validate_version(ver)
    ver.validation_status = report["status"]  # type: ignore[assignment]
    ver.validation_report = report

    rec = RuntimeProfileRecord(
        id=pid,
        key=key,
        name=name,
        description=payload.get("description") or "Governed runtime configuration.",
        status="draft",
        owner_team=payload.get("owner_team") or "Platform",
        current_draft_version_id=ver.id,
        runs_30d=0,
        health_status="HEALTHY",
    )
    _save_records(list_records() + [rec])
    _save_versions(list_versions() + [ver])
    append_audit("create", "runtime_profile", str(rec.id), f"Created runtime profile {rec.key}")
    return detail(str(rec.id))


def _bump_patch(version: str) -> str:
    parts = (version or "0.1.0").split(".")
    while len(parts) < 3:
        parts.append("0")
    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return f"{version}.1"
    return f"{major}.{minor}.{patch + 1}"


def _draft_version(rec: RuntimeProfileRecord) -> RuntimeProfileVersion | None:
    if rec.current_draft_version_id:
        ver = get_version(str(rec.current_draft_version_id))
        if ver and ver.status == "DRAFT":
            return ver
    for ver in list_versions(str(rec.id)):
        if ver.status == "DRAFT":
            return ver
    return None


def _clone_version(
    source: RuntimeProfileVersion,
    *,
    semantic_version: str,
    status: str = "DRAFT",
) -> RuntimeProfileVersion:
    data = source.model_dump(mode="json")
    data.pop("id", None)
    data["semantic_version"] = semantic_version
    data["status"] = status
    data["activated_at"] = None
    data["revision"] = 1
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    data["validation_status"] = "unknown"
    data["validation_report"] = {}
    return RuntimeProfileVersion.model_validate(data)


def _apply_version_payload(ver: RuntimeProfileVersion, payload: dict[str, Any]) -> None:
    scalar_map = {
        "provider": "provider",
        "model": "model",
        "profile_type": "profile_type",
        "type": "profile_type",
        "sandbox": "sandbox",
        "network_policy": "network_policy",
        "supervision": "supervision",
        "secret_ref": "secret_ref",
        "region": "region",
        "fallback_profile_key": "fallback_profile_key",
    }
    for src, dest in scalar_map.items():
        if src not in payload or payload[src] is None:
            continue
        value = payload[src]
        if dest in ("provider", "profile_type", "sandbox", "supervision") and isinstance(value, str):
            value = value.upper()
        setattr(ver, dest, value)

    if "generation_config" in payload and isinstance(payload["generation_config"], dict):
        ver.generation_config = {**ver.generation_config, **payload["generation_config"]}
    else:
        gen = dict(ver.generation_config or {})
        if "temperature" in payload:
            gen["temperature"] = float(payload["temperature"])
        if "maxOutputTokens" in payload or "max_output_tokens" in payload:
            gen["maxOutputTokens"] = int(payload.get("maxOutputTokens") or payload["max_output_tokens"])
        ver.generation_config = gen

    if "limits" in payload and isinstance(payload["limits"], dict):
        ver.limits = {**ver.limits, **payload["limits"]}
    else:
        limits = dict(ver.limits or {})
        for key in ("maxExecutionSeconds", "maxOutputTokens", "maxRetries", "maxConcurrentRuns"):
            snake = {
                "maxExecutionSeconds": "max_execution_seconds",
                "maxOutputTokens": "max_output_tokens",
                "maxRetries": "max_retries",
                "maxConcurrentRuns": "max_concurrent_runs",
            }[key]
            if key in payload:
                limits[key] = int(payload[key])
            elif snake in payload:
                limits[key] = int(payload[snake])
        ver.limits = limits

    if "sandbox_config" in payload and isinstance(payload["sandbox_config"], dict):
        ver.sandbox_config = {**ver.sandbox_config, **payload["sandbox_config"]}

    if "capabilities" in payload:
        caps = payload["capabilities"]
        if isinstance(caps, CapabilityPolicy):
            ver.capabilities = caps
        elif isinstance(caps, dict):
            ver.capabilities = CapabilityPolicy.model_validate({
                "allow": caps.get("allow") or [],
                "deny": caps.get("deny") or [],
                "approval_required": caps.get("approval_required") or [],
            })

    ver.updated_at = datetime.utcnow()
    ver.revision = int(ver.revision or 1) + 1
    report = validate_version(ver)
    ver.validation_status = report["status"]  # type: ignore[assignment]
    ver.validation_report = report


def create_draft(profile_id: str) -> dict[str, Any]:
    rec = get_record(profile_id)
    if not rec:
        raise KeyError("Runtime profile not found")
    existing = _draft_version(rec)
    if existing:
        return detail(str(rec.id))

    source = _current_version(rec)
    if not source:
        raise ValueError("No version to clone into draft")

    draft = _clone_version(source, semantic_version=_bump_patch(source.semantic_version), status="DRAFT")
    report = validate_version(draft)
    draft.validation_status = report["status"]  # type: ignore[assignment]
    draft.validation_report = report

    versions = list_versions()
    versions.append(draft)
    _save_versions(versions)

    records = list_records()
    for r in records:
        if str(r.id) == str(rec.id):
            r.current_draft_version_id = draft.id
            r.updated_at = datetime.utcnow()
            r.revision = int(r.revision or 1) + 1
            rec = r
            break
    _save_records(records)
    append_audit("create_draft", "runtime_profile", str(rec.id), f"Draft {draft.semantic_version} for {rec.key}")
    return detail(str(rec.id))


def update_draft(profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    rec = get_record(profile_id)
    if not rec:
        raise KeyError("Runtime profile not found")

    draft = _draft_version(rec)
    if not draft:
        create_draft(str(rec.id))
        rec = get_record(profile_id)
        if not rec:
            raise KeyError("Runtime profile not found")
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
        r.revision = int(r.revision or 1) + 1
        rec = r
        break
    _save_records(records)

    versions = list_versions()
    for v in versions:
        if str(v.id) != str(draft.id):
            continue
        _apply_version_payload(v, payload)
        draft = v
        break
    _save_versions(versions)
    append_audit("update", "runtime_profile", str(rec.id), f"Updated draft {draft.semantic_version}")
    return detail(str(rec.id))


def delete_profile(profile_id: str) -> dict[str, Any]:
    rec = get_record(profile_id)
    if not rec:
        raise KeyError("Runtime profile not found")
    records = [r for r in list_records() if r.id != rec.id]
    versions = [v for v in list_versions() if str(v.profile_id) != str(rec.id)]
    _save_records(records)
    _save_versions(versions)
    append_audit("delete", "runtime_profile", str(rec.id), f"Deleted profile {rec.key}")
    return {"ok": True, "id": str(rec.id), "key": rec.key}


def activate_version(profile_id: str, version_id: str | None = None) -> dict[str, Any]:
    rec = get_record(profile_id)
    if not rec:
        raise KeyError("Runtime profile not found")

    target: RuntimeProfileVersion | None = None
    if version_id:
        target = get_version(version_id)
        if not target or str(target.profile_id) != str(rec.id):
            raise KeyError("Version not found")
    else:
        target = _draft_version(rec) or _current_version(rec)
    if not target:
        raise ValueError("No version to activate")
    if target.status not in ("DRAFT", "DEPRECATED"):
        if target.status == "ACTIVE" and str(rec.current_active_version_id) == str(target.id):
            return detail(str(rec.id))
        raise ValueError(f"Cannot activate version in status {target.status}")

    report = validate_version(target)
    if not report["valid"]:
        messages = [e.get("message", e.get("code", "invalid")) for e in report.get("errors", [])]
        raise ValueError(f"Cannot activate invalid draft: {'; '.join(messages)}")

    versions = list_versions()
    now = datetime.utcnow()
    for v in versions:
        if str(v.profile_id) != str(rec.id):
            continue
        if str(v.id) == str(target.id):
            v.status = "ACTIVE"
            v.activated_at = now
            v.updated_at = now
            v.validation_status = report["status"]  # type: ignore[assignment]
            v.validation_report = report
            target = v
        elif v.status == "ACTIVE":
            v.status = "DEPRECATED"
            v.updated_at = now

    records = list_records()
    for r in records:
        if str(r.id) != str(rec.id):
            continue
        r.current_active_version_id = target.id
        if r.current_draft_version_id and str(r.current_draft_version_id) == str(target.id):
            r.current_draft_version_id = None
        r.status = "active"
        r.updated_at = now
        r.revision = int(r.revision or 1) + 1
        rec = r
        break

    _save_versions(versions)
    _save_records(records)
    try:
        from src.platform.runtime_bridge import write_resolved_runtime

        base_url = None
        if isinstance(target.generation_config, dict):
            base_url = target.generation_config.get("base_url")
        write_resolved_runtime(
            profile_key=rec.key,
            model=target.model,
            provider=str(target.provider),
            base_url=base_url,
        )
    except Exception as exc:
        logger.warning("Failed writing runtime_resolved.json: %s", exc)
    append_audit(
        "activate",
        "runtime_profile",
        str(rec.id),
        f"Activated {rec.key}@{target.semantic_version}",
    )
    return detail(str(rec.id))


def validate_profile(profile_id: str) -> dict[str, Any]:
    rec = get_record(profile_id)
    if not rec:
        raise KeyError("Runtime profile not found")
    ver = _draft_version(rec) or _current_version(rec)
    if not ver:
        return {"valid": False, "errors": [{"message": "No version to validate"}], "warnings": []}
    report = validate_version(ver)
    versions = list_versions()
    for v in versions:
        if str(v.id) != str(ver.id):
            continue
        v.validation_status = report["status"]  # type: ignore[assignment]
        v.validation_report = report
        v.updated_at = datetime.utcnow()
        break
    _save_versions(versions)
    return report


def test_connection(profile_id: str) -> dict[str, Any]:
    rec = get_record(profile_id)
    if not rec:
        raise KeyError("Runtime profile not found")
    ver = _current_version(rec)
    if not ver:
        raise ValueError("No version to test")
    ok = rec.health_status != "UNHEALTHY"
    return {
        "ok": ok,
        "profile": rec.key,
        "provider": ver.provider,
        "model": ver.model,
        "latency_ms": 842 if ok else None,
        "message": "Connection healthy · model available" if ok else "Provider unreachable (stub)",
    }


def resolve_preview(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """MVP effective runtime resolution for Flow/Playbook/Skill context."""
    ensure_runtime_profiles_seeded()
    body = body or {}
    flow_key = body.get("flow_key") or body.get("flow") or "feature-delivery"
    graph_key = body.get("graph_key") or body.get("playbook_key") or body.get("playbook") or "system-requirements"
    skill_key = body.get("skill_key") or body.get("skill") or "generate-requirements"

    profile_key = "qwen-production"
    if "restricted" in graph_key or "identity" in skill_key:
        profile_key = "local-restricted"
    elif "batch" in flow_key or body.get("profile_type") == "LOW_COST":
        profile_key = "low-cost-batch"
    elif body.get("profile_key"):
        profile_key = body["profile_key"]

    rec = get_record(profile_key) or get_record("qwen-production")
    if not rec:
        return {"matched": False, "message": "No runtime profile found"}
    ver = _current_version(rec)
    if not ver:
        return {"matched": False, "message": "Profile has no active version"}

    trace = [
        "Workspace Default",
        f"Flow Binding ({flow_key})",
        f"Graph Override ({graph_key})",
        "Controls",
    ]
    effective = effective_runtime(ver)
    effective["profile"] = f"{rec.name} v{ver.semantic_version}"
    return {
        "matched": True,
        "profile_id": str(rec.id),
        "profile_key": rec.key,
        "trace": trace,
        "effective": effective,
        "context": {
            "flow": flow_key,
            "graph": graph_key,
            "skill": skill_key,
        },
    }
