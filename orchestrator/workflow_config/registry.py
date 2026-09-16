"""Registry: skills (manifest + SKILL.md) + model profiles."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from src.agent.infrastructure.skills_loader import list_skills_metadata
from src.orchestrator.workflow_config.models import ModelProfileDef, SkillDef
from src.orchestrator.workflow_config.skill_manifests import (
    SkillManifest,
    ensure_manifests_from_skills,
    get_skill_manifest,
    list_skill_manifests,
    save_skill_manifest,
)

logger = logging.getLogger(__name__)

_DEFAULT_REGISTRY = Path(__file__).resolve().parents[3] / "config" / "registry"


def get_registry_dir() -> Path:
    env = os.environ.get("REGISTRY_CONFIG_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return _DEFAULT_REGISTRY


def _read_json(name: str) -> dict:
    path = get_registry_dir() / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(name: str, data: dict) -> None:
    path = get_registry_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def list_skills() -> list[SkillDef]:
    """Merge SKILL.md discovery with skill manifests (allowed_capabilities)."""
    discovered = list_skills_metadata()
    ensure_manifests_from_skills(discovered)
    manifests = {m.id: m for m in list_skill_manifests()}
    legacy = {
        s["id"]: s
        for s in _read_json("skills.json").get("skills", [])
        if isinstance(s, dict) and s.get("id")
    }

    result: list[SkillDef] = []
    seen: set[str] = set()
    for meta in discovered:
        sid = meta["name"]
        seen.add(sid)
        m = manifests.get(sid)
        leg = legacy.get(sid, {})
        allowed = list(m.allowed_capabilities if m else (leg.get("allowed_capabilities") or []))
        result.append(SkillDef(
            id=sid,
            name=(m.name if m else None) or leg.get("name") or sid.replace("-", " ").title(),
            description=(m.description if m else None) or leg.get("description") or meta.get("description", ""),
            capability_id=None,
            allowed_capabilities=allowed,
            path=str(meta.get("path", "")),
        ))

    for sid, m in manifests.items():
        if sid in seen:
            continue
        result.append(SkillDef(
            id=sid,
            name=m.name,
            description=m.description,
            capability_id=None,
            allowed_capabilities=list(m.allowed_capabilities),
            path=m.skill_md,
        ))
    return result


def get_skill(skill_id: str) -> Optional[SkillDef]:
    return next((s for s in list_skills() if s.id == skill_id), None)


def save_skill(skill: SkillDef) -> SkillDef:
    """Persist skill metadata into skill manifest (source of truth)."""
    existing = get_skill_manifest(skill.id)
    manifest = SkillManifest(
        id=skill.id,
        version=existing.version if existing else "1.0",
        name=skill.name or skill.id,
        description=skill.description or "",
        allowed_capabilities=list(skill.allowed_capabilities or []),
        skill_md=(existing.skill_md if existing else f"skills/{skill.id}/SKILL.md"),
        tags=list(existing.tags) if existing else [],
        status=existing.status if existing else "published",
    )
    save_skill_manifest(manifest)
    return get_skill(skill.id) or skill


def save_skills(items: list[SkillDef]) -> None:
    for s in items:
        save_skill(s)


def list_model_profiles() -> list[ModelProfileDef]:
    data = _read_json("model_profiles.json")
    return [ModelProfileDef.model_validate(p) for p in data.get("profiles", [])]
