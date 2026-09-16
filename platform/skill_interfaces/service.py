"""Skill interface catalog with platform/custom mutability rules."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from src.platform.contracts.registry import known_contract_keys
from src.platform.domain.models import SkillInterface
from src.platform.store import (
    append_audit,
    delete_skill_interface,
    get_skill_interface,
    list_skill_interfaces,
    save_skill_interface,
)

_KEY_RE = re.compile(r"^[a-z][a-z0-9_.]*\.[a-z0-9_.]+@[0-9]+$")


def _platform_keys() -> set[str]:
    try:
        from src.platform.seed.governed_catalog import INTERFACE_SPECS

        return {key for key, _, _ in INTERFACE_SPECS}
    except Exception:
        return set()


def is_platform_interface(iface: SkillInterface) -> bool:
    if iface.source == "platform":
        return True
    return iface.key in _platform_keys()


def normalize_interface(iface: SkillInterface) -> SkillInterface:
    data = iface.model_dump()
    data["source"] = "platform" if is_platform_interface(iface) else "custom"
    if not data.get("version") and "@" in iface.key:
        data["version"] = iface.key.rsplit("@", 1)[-1]
    return SkillInterface.model_validate(data)


def list_interfaces() -> list[SkillInterface]:
    return [normalize_interface(item) for item in list_skill_interfaces()]


def get_interface(entity_id: str) -> SkillInterface | None:
    item = get_skill_interface(entity_id)
    return normalize_interface(item) if item else None


def _validate_payload(payload: dict[str, Any], *, existing: SkillInterface | None = None) -> None:
    key = str(payload.get("key") or (existing.key if existing else "")).strip()
    name = str(payload.get("name") or (existing.name if existing else "")).strip()
    if not key:
        raise ValueError("key is required")
    if not name:
        raise ValueError("name is required")
    if not _KEY_RE.match(key):
        raise ValueError("key must look like domain.action@1")
    input_key = str(payload.get("input_contract_key") or "").strip()
    output_key = str(payload.get("output_contract_key") or "").strip()
    if not input_key or not output_key:
        raise ValueError("input_contract_key and output_contract_key are required")
    known = known_contract_keys()
    if input_key not in known:
        raise ValueError(f"Unknown input contract: {input_key}")
    if output_key not in known:
        raise ValueError(f"Unknown output contract: {output_key}")
    if existing is None:
        for item in list_interfaces():
            if item.key == key:
                raise ValueError(f"Interface key already exists: {key}")


def _skills_using_interface(interface_key: str) -> list[str]:
    try:
        from src.platform.skills.service import list_records, list_versions
    except Exception:
        return []
    keys: list[str] = []
    for rec in list_records():
        for ver in list_versions(str(rec.id)):
            if ver.interface_key == interface_key:
                keys.append(rec.key)
                break
    return keys


def create_interface(payload: dict[str, Any]) -> SkillInterface:
    data = dict(payload)
    data.pop("id", None)
    data["source"] = "custom"
    if "@" in str(data.get("key", "")):
        data.setdefault("version", str(data["key"]).rsplit("@", 1)[-1])
    _validate_payload(data)
    iface = SkillInterface.model_validate(data)
    saved = save_skill_interface(iface)
    append_audit("create", "skill_interface", str(saved.id), f"Created interface {saved.key}")
    return normalize_interface(saved)


def update_interface(entity_id: str, payload: dict[str, Any]) -> SkillInterface:
    existing = get_interface(entity_id)
    if not existing:
        raise KeyError("Skill interface not found")
    if is_platform_interface(existing):
        raise PermissionError("Platform interfaces are read-only")
    data = {**existing.model_dump(mode="json"), **payload, "id": str(existing.id)}
    data["source"] = "custom"
    data["key"] = existing.key
    _validate_payload(data, existing=existing)
    data["updated_at"] = datetime.utcnow()
    saved = save_skill_interface(SkillInterface.model_validate(data))
    append_audit("update", "skill_interface", str(saved.id), f"Updated interface {saved.key}")
    return normalize_interface(saved)


def delete_interface(entity_id: str) -> dict[str, Any]:
    existing = get_interface(entity_id)
    if not existing:
        raise KeyError("Skill interface not found")
    if is_platform_interface(existing):
        raise PermissionError("Platform interfaces cannot be deleted")
    consumers = _skills_using_interface(existing.key)
    if consumers:
        raise ValueError(
            "Cannot delete: referenced by skills " + ", ".join(sorted(consumers))
        )
    if not delete_skill_interface(str(existing.id)):
        raise KeyError("Skill interface not found")
    append_audit("delete", "skill_interface", str(existing.id), f"Deleted interface {existing.key}")
    return {"ok": True, "id": str(existing.id), "key": existing.key}
