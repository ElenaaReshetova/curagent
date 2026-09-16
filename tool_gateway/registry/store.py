"""Capability registry with hot reload (CAP-001, CAP-024, REL-009)."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from src.tool_gateway.models.envelopes import ManifestStatus
from src.tool_gateway.models.manifest import CapabilityManifest

logger = logging.getLogger(__name__)

_DEFAULT_MANIFESTS = Path(__file__).resolve().parents[3] / "config" / "capabilities" / "manifests"

_lock = threading.RLock()
_snapshot: dict[str, CapabilityManifest] = {}
_snapshot_id: str = ""
_registry_available: bool = True


def get_manifests_dir() -> Path:
    env = os.environ.get("CAPABILITY_MANIFESTS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return _DEFAULT_MANIFESTS


def reload_registry() -> str:
    """Atomic snapshot reload (CAP-024, REL-008)."""
    global _snapshot, _snapshot_id, _registry_available
    manifests_dir = get_manifests_dir()
    new_snapshot: dict[str, CapabilityManifest] = {}

    if not manifests_dir.exists():
        logger.error("Manifests directory missing: %s", manifests_dir)
        with _lock:
            _registry_available = False
            _snapshot = {}
            _snapshot_id = "empty"
        return _snapshot_id

    try:
        for path in sorted(manifests_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            manifest = CapabilityManifest.model_validate(data)
            key = manifest.capability_id
            new_snapshot[key] = manifest
        snapshot_id = f"snap-{len(new_snapshot)}-{hash(tuple(sorted(new_snapshot.keys())))}"
        with _lock:
            _snapshot = new_snapshot
            _snapshot_id = snapshot_id
            _registry_available = True
        logger.info("Registry reloaded: %d capabilities, snapshot=%s", len(new_snapshot), snapshot_id)
        return snapshot_id
    except Exception as e:
        logger.exception("Registry reload failed: %s", e)
        with _lock:
            _registry_available = False
        raise


def is_registry_available() -> bool:
    with _lock:
        return _registry_available and bool(_snapshot)


def get_snapshot_id() -> str:
    with _lock:
        return _snapshot_id


def get_manifest(capability_id: str, version: Optional[int] = None) -> Optional[CapabilityManifest]:
    with _lock:
        if not _registry_available:
            return None
        m = _snapshot.get(capability_id)
        if m is None:
            return None
        if version is not None and m.manifest_version != version:
            return None
        return m


def list_manifests() -> list[CapabilityManifest]:
    with _lock:
        return list(_snapshot.values())


def ensure_loaded() -> None:
    with _lock:
        if not _snapshot:
            reload_registry()


def manifest_path(capability_id: str) -> Path:
    safe_id = capability_id.strip().replace("/", "-")
    return get_manifests_dir() / f"{safe_id}.json"


def save_manifest(manifest: CapabilityManifest) -> CapabilityManifest:
    """Persist manifest to disk and hot-reload registry (CAP-024)."""
    manifests_dir = get_manifests_dir()
    manifests_dir.mkdir(parents=True, exist_ok=True)
    path = manifest_path(manifest.capability_id)
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    reload_registry()
    saved = get_manifest(manifest.capability_id)
    if saved is None:
        raise RuntimeError(f"Failed to reload manifest {manifest.capability_id}")
    return saved


def delete_manifest(capability_id: str) -> bool:
    path = manifest_path(capability_id)
    if not path.exists():
        return False
    path.unlink()
    reload_registry()
    return True
