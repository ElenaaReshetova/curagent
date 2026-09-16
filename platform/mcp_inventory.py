"""Read-only inventory of configured MCP servers and capability manifests."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parents[2]
_MCP_SERVERS = _ROOT / "config" / "mcp" / "servers.json"
_MANIFESTS = _ROOT / "config" / "capabilities" / "manifests"


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read inventory file %s: %s", path, exc)
        return default


def list_mcp_servers() -> list[dict[str, Any]]:
    """Return a safe, UI-ready projection of configured MCP servers."""
    payload = _read_json(_MCP_SERVERS, {"servers": []})
    servers = payload.get("servers", []) if isinstance(payload, dict) else []
    return [
        {
            "id": server.get("id", ""),
            "name": server.get("name", server.get("id", "")),
            "description": server.get("description", ""),
            "enabled": bool(server.get("enabled", False)),
            "tools": list(server.get("tools") or []),
            "type": server.get("type", ""),
        }
        for server in servers
        if isinstance(server, dict) and server.get("id")
    ]


def list_capability_manifests() -> list[dict[str, Any]]:
    """Load all capability manifests, retaining their implementation records."""
    manifests: list[dict[str, Any]] = []
    for path in sorted(_MANIFESTS.glob("*.json")):
        manifest = _read_json(path, None)
        if isinstance(manifest, dict) and manifest.get("capability_id"):
            manifests.append(manifest)
    return manifests


def get_capability_manifest(capability_id: str) -> dict[str, Any] | None:
    return next(
        (manifest for manifest in list_capability_manifests()
         if manifest.get("capability_id") == capability_id),
        None,
    )


def implementations_for_capability(capability_id_or_key: str) -> list[dict[str, Any]]:
    manifest = get_capability_manifest(capability_id_or_key)
    if manifest is None:
        manifest = next(
            (item for item in list_capability_manifests()
             if item.get("key") == capability_id_or_key),
            None,
        )
    return list(manifest.get("implementations") or []) if manifest else []


def capabilities_for_mcp_server(server_id: str) -> list[dict[str, Any]]:
    return [
        manifest
        for manifest in list_capability_manifests()
        if any(
            implementation.get("server_id") == server_id
            for implementation in manifest.get("implementations") or []
            if isinstance(implementation, dict)
        )
    ]
