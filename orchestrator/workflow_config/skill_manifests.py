"""Skill manifests — allowed Capabilities API for each skill."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_MANIFESTS = _ROOT / "config" / "skills" / "manifests"


class SkillManifest(BaseModel):
    id: str
    version: str = "1.0"
    name: str
    description: str = ""
    allowed_capabilities: list[str] = Field(default_factory=list)
    skill_md: Optional[str] = None  # relative path e.g. skills/general/SKILL.md
    tags: list[str] = Field(default_factory=list)
    status: str = "published"  # draft | published | deprecated


def get_skill_manifests_dir() -> Path:
    env = os.environ.get("SKILL_MANIFESTS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return _DEFAULT_MANIFESTS


def _path_for(skill_id: str) -> Path:
    safe = skill_id.strip().replace("/", "-").replace("..", "_")
    return get_skill_manifests_dir() / f"{safe}.json"


def list_skill_manifests() -> list[SkillManifest]:
    d = get_skill_manifests_dir()
    d.mkdir(parents=True, exist_ok=True)
    out: list[SkillManifest] = []
    for path in sorted(d.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append(SkillManifest.model_validate(data))
        except Exception as e:
            logger.warning("Skip skill manifest %s: %s", path, e)
    return out


def get_skill_manifest(skill_id: str) -> Optional[SkillManifest]:
    path = _path_for(skill_id)
    if not path.exists():
        return None
    return SkillManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))


def save_skill_manifest(manifest: SkillManifest) -> SkillManifest:
    d = get_skill_manifests_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = _path_for(manifest.id)
    path.write_text(
        json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return get_skill_manifest(manifest.id) or manifest


def delete_skill_manifest(skill_id: str) -> bool:
    path = _path_for(skill_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def ensure_manifests_from_skills(skills_meta: list[dict[str, Any]]) -> None:
    """Create stub manifests for discovered skills that have none yet."""
    existing = {m.id for m in list_skill_manifests()}
    for meta in skills_meta:
        sid = meta.get("name") or meta.get("id")
        if not sid or sid in existing:
            continue
        save_skill_manifest(SkillManifest(
            id=sid,
            name=str(sid).replace("-", " ").title(),
            description=meta.get("description") or "",
            skill_md=f"skills/{sid}/SKILL.md",
            allowed_capabilities=[],
        ))
