"""Reusable node presets — save a configured step and drop it onto another graph."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.platform.store import get_platform_dir

logger = logging.getLogger(__name__)

_FILE = "node_presets.json"


class NodePreset(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    node_type: str
    label: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    kind: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


def _path() -> Path:
    return get_platform_dir() / _FILE


def _load() -> list[NodePreset]:
    path = _path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed reading %s: %s", path, exc)
        return []
    items = raw.get("presets") if isinstance(raw, dict) else raw
    out: list[NodePreset] = []
    for item in items or []:
        try:
            out.append(NodePreset.model_validate(item))
        except Exception:
            continue
    return out


def _save(items: list[NodePreset]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"presets": [i.model_dump(mode="json") for i in items]},
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )


def sanitize_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Drop canvas-only fields; keep prompts, URLs, options, notifications."""
    cfg = dict(config or {})
    cfg.pop("position", None)
    return json.loads(json.dumps(cfg, default=str))


def list_presets(*, kind: str | None = None) -> list[NodePreset]:
    items = _load()
    items.sort(key=lambda p: (p.name.lower(), str(p.updated_at)), reverse=False)
    if not kind:
        return items
    return [p for p in items if not p.kind or p.kind == kind]


def get_preset(preset_id: UUID) -> NodePreset:
    for p in _load():
        if p.id == preset_id:
            return p
    raise KeyError(preset_id)


def save_preset(
    *,
    name: str,
    node_type: str,
    label: str = "",
    config: dict[str, Any] | None = None,
    kind: str | None = None,
    preset_id: UUID | None = None,
    replace_same_name: bool = True,
) -> NodePreset:
    title = (name or label or node_type).strip() or node_type
    ntype = (node_type or "webhook").strip()
    if not ntype:
        raise ValueError("node_type required")
    items = _load()
    now = datetime.utcnow()
    cfg = sanitize_config(config)
    target: NodePreset | None = None
    if preset_id:
        for p in items:
            if p.id == preset_id:
                target = p
                break
        if target is None:
            raise KeyError(preset_id)
    elif replace_same_name:
        for p in items:
            if p.name.lower() == title.lower() and p.node_type == ntype:
                target = p
                break
    if target:
        target.name = title
        target.node_type = ntype
        target.label = (label or title).strip()
        target.config = cfg
        if kind is not None:
            target.kind = kind or None
        target.updated_at = now
        _save(items)
        return target
    rec = NodePreset(
        name=title,
        node_type=ntype,
        label=(label or title).strip(),
        config=cfg,
        kind=kind or None,
        created_at=now,
        updated_at=now,
    )
    items.append(rec)
    _save(items)
    return rec


def delete_preset(preset_id: UUID) -> None:
    items = _load()
    next_items = [p for p in items if p.id != preset_id]
    if len(next_items) == len(items):
        raise KeyError(preset_id)
    _save(next_items)
