"""Integrations as protocol connections: MCP, A2A, ACP.

MCP JSON matches the emergent client standard:

  { "mcpServers": { "<name>": { "command", "args?", "env?" } | { "url", "headers?", "env?" } } }

A2A uses the a2a-cli client map: { "servers": { "<alias>": "<url>" } }
ACP uses Agent Client Protocol: { "agent_servers": { "<name>": { "command", "args?", "env?" } } }
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from src.platform.integrations.models import (
    IntegrationCatalogResponse,
    IntegrationConnection,
    IntegrationDetail,
    IntegrationMetrics,
)
from src.platform.integrations.validation import (
    validate_a2a_entry,
    validate_acp_entry,
    validate_mcp_entry,
)
from src.platform import mcp_inventory
from src.workflow_ui import mcp_config

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[3]
_INTEGRATIONS_DIR = _ROOT / "config" / "integrations"

# Known platform builtins → standard mcpServers launch config
_BUILTIN_MCP_LAUNCH: dict[str, dict[str, Any]] = {
    "jira": {
        "command": "node",
        "args": ["mcp-jira/build/index.js"],
    },
    "slack": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
    },
}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed reading %s: %s", path, exc)
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def a2a_config_path() -> Path:
    return _INTEGRATIONS_DIR / "a2a.json"


def acp_config_path() -> Path:
    return _INTEGRATIONS_DIR / "acp.json"


def load_a2a_document() -> dict[str, Any]:
    raw = _read_json(a2a_config_path(), {"servers": {}})
    servers = raw.get("servers") if isinstance(raw, dict) else {}
    if not isinstance(servers, dict):
        servers = {}
    return {"servers": {str(k): str(v) for k, v in servers.items()}}


def load_acp_document() -> dict[str, Any]:
    raw = _read_json(acp_config_path(), {"agent_servers": {}})
    agents = raw.get("agent_servers") if isinstance(raw, dict) else {}
    if not isinstance(agents, dict):
        agents = {}
    cleaned: dict[str, Any] = {}
    for name, entry in agents.items():
        if not isinstance(entry, dict):
            continue
        item: dict[str, Any] = {"command": str(entry.get("command") or "").strip()}
        args = entry.get("args") or []
        if isinstance(args, list) and args:
            item["args"] = [str(a) for a in args]
        env = entry.get("env") or {}
        if isinstance(env, dict) and env:
            item["env"] = {str(k): "" if v is None else str(v) for k, v in env.items()}
        cleaned[str(name)] = item
    return {"agent_servers": cleaned}


def save_a2a_document(doc: dict[str, Any]) -> dict[str, Any]:
    servers = doc.get("servers") if isinstance(doc.get("servers"), dict) else {}
    normalized = {"servers": {str(k): str(v) for k, v in servers.items()}}
    _write_json(a2a_config_path(), normalized)
    return load_a2a_document()


def save_acp_document(doc: dict[str, Any]) -> dict[str, Any]:
    agents = doc.get("agent_servers") if isinstance(doc.get("agent_servers"), dict) else {}
    normalized = {"agent_servers": {}}
    for name, entry in agents.items():
        if not isinstance(entry, dict):
            continue
        item: dict[str, Any] = {"command": str(entry.get("command") or "").strip()}
        args = entry.get("args") or []
        if isinstance(args, list) and args:
            item["args"] = [str(a) for a in args]
        env = entry.get("env") or {}
        if isinstance(env, dict) and env:
            item["env"] = {str(k): "" if v is None else str(v) for k, v in env.items()}
        normalized["agent_servers"][str(name)] = item
    _write_json(acp_config_path(), normalized)
    return load_acp_document()


def _public_env(env: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (env or {}).items():
        raw = "" if value is None else str(value)
        if mcp_config._is_secret_key(key):  # noqa: SLF001
            out[key] = ""
        else:
            out[key] = raw
    return out


def server_to_mcp_entry(server: dict[str, Any], *, mask_secrets: bool = True) -> dict[str, Any]:
    """Convert internal servers.json entry → standard mcpServers value."""
    stype = server.get("type") or "stdio"
    entry: dict[str, Any] = {}

    if stype in ("sse", "http") and server.get("url"):
        entry["url"] = str(server["url"])
        headers = server.get("headers") or {}
        if isinstance(headers, dict) and headers:
            entry["headers"] = {str(k): str(v) for k, v in headers.items()}
    else:
        command = str(server.get("command") or "").strip()
        args = list(server.get("args") or [])
        if not command and stype == "builtin":
            builtin = str(server.get("builtin") or server.get("id") or "")
            launch = _BUILTIN_MCP_LAUNCH.get(builtin) or _BUILTIN_MCP_LAUNCH.get(server.get("id", ""))
            if launch:
                command = launch["command"]
                args = list(launch.get("args") or [])
        if command:
            entry["command"] = command
            if args:
                entry["args"] = [str(a) for a in args]

    env = server.get("env") or {}
    if isinstance(env, dict) and env:
        entry["env"] = _public_env(env) if mask_secrets else {
            str(k): "" if v is None else str(v) for k, v in env.items()
        }

    return entry


def mcp_entry_to_server(name: str, entry: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Convert standard mcpServers value → internal servers.json entry."""
    existing = existing or {}
    if entry.get("url"):
        stype = "sse" if "sse" in str(entry.get("url", "")).lower() else "http"
        return mcp_config._normalize_server({  # noqa: SLF001
            "id": name,
            "name": existing.get("name") or name,
            "description": existing.get("description") or "",
            "enabled": existing.get("enabled", True),
            "type": stype,
            "url": entry.get("url"),
            "headers": entry.get("headers") if isinstance(entry.get("headers"), dict) else {},
            "env": entry.get("env") if isinstance(entry.get("env"), dict) else {},
            "tools": existing.get("tools") or [],
        }, name)

    command = str(entry.get("command") or "").strip()
    args = entry.get("args") if isinstance(entry.get("args"), list) else []
    builtin = ""
    stype = "stdio"
    for bid, launch in _BUILTIN_MCP_LAUNCH.items():
        if command == launch.get("command") and list(args) == list(launch.get("args") or []):
            builtin = bid
            stype = "builtin"
            break
    if existing.get("type") == "builtin" and (existing.get("builtin") or existing.get("id")) in _BUILTIN_MCP_LAUNCH:
        builtin = str(existing.get("builtin") or existing.get("id"))
        stype = "builtin"

    return mcp_config._normalize_server({  # noqa: SLF001
        "id": name,
        "name": existing.get("name") or name,
        "description": existing.get("description") or "",
        "enabled": existing.get("enabled", True),
        "type": stype,
        "builtin": builtin,
        "command": "" if stype == "builtin" else command,
        "args": [] if stype == "builtin" else args,
        "env": entry.get("env") if isinstance(entry.get("env"), dict) else {},
        "tools": existing.get("tools") or [],
    }, name)


def build_mcp_servers_document(*, mask_secrets: bool = True) -> dict[str, Any]:
    """Exact Claude Desktop / Cursor mcp.json shape."""
    doc = mcp_config.load_mcp_document()
    mcp_servers: dict[str, Any] = {}
    for server in doc.get("servers") or []:
        if not isinstance(server, dict) or not server.get("id"):
            continue
        entry = server_to_mcp_entry(server, mask_secrets=mask_secrets)
        if entry.get("command") or entry.get("url"):
            mcp_servers[server["id"]] = entry
    return {"mcpServers": mcp_servers}


def apply_mcp_servers_document(document: dict[str, Any]) -> dict[str, Any]:
    """Persist a standard {mcpServers:{...}} document into servers.json."""
    incoming = document.get("mcpServers")
    if not isinstance(incoming, dict):
        raise ValueError("Document must contain mcpServers object")
    current = mcp_config.load_mcp_document()
    existing_by_id = {s["id"]: s for s in current.get("servers") or []}
    servers: list[dict[str, Any]] = []
    for name, entry in incoming.items():
        if not isinstance(entry, dict):
            raise ValueError(f"mcpServers.{name} must be an object")
        report = validate_mcp_entry(str(name), entry)
        if not report["valid"]:
            raise ValueError("; ".join(e["message"] for e in report["errors"]))
        prev = existing_by_id.get(str(name))
        server = mcp_entry_to_server(str(name), entry, prev)
        if prev:
            env = dict(prev.get("env") or {})
            for key, value in (server.get("env") or {}).items():
                if mcp_config._is_secret_key(key) and not value:  # noqa: SLF001
                    continue
                env[key] = value
            server["env"] = env
            server["tools"] = prev.get("tools") or server.get("tools") or []
            server["description"] = prev.get("description") or server.get("description") or ""
            server["name"] = prev.get("name") or server.get("name") or name
            server["enabled"] = prev.get("enabled", True)
        servers.append(server)
    mcp_config.save_mcp_document({"version": current.get("version", 1), "servers": servers})
    return build_mcp_servers_document()


def build_full_config_document(*, mask_secrets: bool = True) -> dict[str, Any]:
    """Combined JSON view: MCP standard root + A2A + ACP sections."""
    mcp = build_mcp_servers_document(mask_secrets=mask_secrets)
    a2a = load_a2a_document()
    acp = load_acp_document()
    return {
        "mcpServers": mcp.get("mcpServers", {}),
        "servers": a2a.get("servers", {}),
        "agent_servers": acp.get("agent_servers", {}),
    }


def apply_full_config_document(document: dict[str, Any]) -> dict[str, Any]:
    if "mcpServers" in document:
        apply_mcp_servers_document({"mcpServers": document.get("mcpServers") or {}})
    if "servers" in document:
        save_a2a_document({"servers": document.get("servers") or {}})
    if "agent_servers" in document:
        save_acp_document({"agent_servers": document.get("agent_servers") or {}})
    return build_full_config_document()


def _mcp_status(server: dict[str, Any]) -> str:
    return mcp_config._server_status(server)  # noqa: SLF001


def _list_mcp_connections(search: str = "", status: str = "") -> list[IntegrationConnection]:
    status_payload = mcp_config.build_mcp_status()
    items: list[IntegrationConnection] = []
    for server in status_payload.get("servers") or []:
        sid = server.get("id") or ""
        entry = server_to_mcp_entry(server)
        if not (entry.get("command") or entry.get("url")):
            continue
        st = server.get("status") or _mcp_status(server)
        conn = IntegrationConnection(
            id=f"mcp:{sid}",
            key=sid,
            name=server.get("name") or sid,
            protocol="MCP",
            description=server.get("description") or "MCP server",
            enabled=bool(server.get("enabled", True)),
            status=st if st in {"ready", "misconfigured", "disabled"} else "unknown",
            transport=str(server.get("type") or ("url" if entry.get("url") else "stdio")),
            tools=[str(t) if not isinstance(t, dict) else str(t.get("name") or t) for t in (server.get("tools") or [])],
            linked_capabilities=list(server.get("linked_capabilities") or []),
            config=entry,
        )
        blob = f"{conn.name} {conn.key} {conn.description} {' '.join(conn.tools)}".lower()
        if search and search.lower() not in blob:
            continue
        if status and conn.status != status.lower():
            continue
        items.append(conn)
    return items


def _list_a2a_connections(search: str = "", status: str = "") -> list[IntegrationConnection]:
    doc = load_a2a_document()
    items: list[IntegrationConnection] = []
    for name, url in (doc.get("servers") or {}).items():
        report = validate_a2a_entry(name, url)
        st = "ready" if report["valid"] else "misconfigured"
        conn = IntegrationConnection(
            id=f"a2a:{name}",
            key=name,
            name=name,
            protocol="A2A",
            description="Agent-to-Agent endpoint",
            enabled=True,
            status=st,  # type: ignore[arg-type]
            transport="http",
            config={"url": url},
        )
        blob = f"{conn.name} {url}".lower()
        if search and search.lower() not in blob:
            continue
        if status and conn.status != status.lower():
            continue
        items.append(conn)
    return items


def _list_acp_connections(search: str = "", status: str = "") -> list[IntegrationConnection]:
    doc = load_acp_document()
    items: list[IntegrationConnection] = []
    for name, entry in (doc.get("agent_servers") or {}).items():
        report = validate_acp_entry(name, entry if isinstance(entry, dict) else {})
        st = "ready" if report["valid"] else "misconfigured"
        public_entry = dict(entry) if isinstance(entry, dict) else {}
        if isinstance(public_entry.get("env"), dict):
            public_entry["env"] = _public_env(public_entry["env"])
        conn = IntegrationConnection(
            id=f"acp:{name}",
            key=name,
            name=name,
            protocol="ACP",
            description="Agent Client Protocol server",
            enabled=True,
            status=st,  # type: ignore[arg-type]
            transport="stdio",
            config=public_entry,
        )
        blob = f"{conn.name} {public_entry.get('command', '')}".lower()
        if search and search.lower() not in blob:
            continue
        if status and conn.status != status.lower():
            continue
        items.append(conn)
    return items


def catalog(
    search: str = "",
    protocol: str = "",
    status: str = "",
) -> IntegrationCatalogResponse:
    protocol_u = (protocol or "").upper()
    connections: list[IntegrationConnection] = []
    if not protocol_u or protocol_u == "MCP":
        connections.extend(_list_mcp_connections(search=search, status=status))
    if not protocol_u or protocol_u == "A2A":
        connections.extend(_list_a2a_connections(search=search, status=status))
    if not protocol_u or protocol_u == "ACP":
        connections.extend(_list_acp_connections(search=search, status=status))

    connections.sort(key=lambda c: (c.protocol, c.key.lower()))
    metrics = IntegrationMetrics(
        total=len(connections),
        mcp=sum(1 for c in connections if c.protocol == "MCP"),
        a2a=sum(1 for c in connections if c.protocol == "A2A"),
        acp=sum(1 for c in connections if c.protocol == "ACP"),
        ready=sum(1 for c in connections if c.status == "ready"),
        misconfigured=sum(1 for c in connections if c.status == "misconfigured"),
        disabled=sum(1 for c in connections if c.status == "disabled"),
    )
    return IntegrationCatalogResponse(
        connections=connections,
        metrics=metrics,
        config=build_full_config_document(),
    )


def _parse_id(integration_id: str) -> tuple[str, str]:
    if ":" in integration_id:
        proto, key = integration_id.split(":", 1)
        return proto.upper(), key
    # bare key → try MCP first, then A2A, ACP
    for proto, finder in (
        ("MCP", lambda: next((c for c in _list_mcp_connections() if c.key == integration_id), None)),
        ("A2A", lambda: next((c for c in _list_a2a_connections() if c.key == integration_id), None)),
        ("ACP", lambda: next((c for c in _list_acp_connections() if c.key == integration_id), None)),
    ):
        if finder():
            return proto, integration_id
    raise KeyError("Integration not found")


def detail(integration_id: str) -> IntegrationDetail:
    protocol, key = _parse_id(integration_id)
    if protocol == "MCP":
        conn = next((c for c in _list_mcp_connections() if c.key == key), None)
        if not conn:
            raise KeyError("Integration not found")
        caps = mcp_inventory.capabilities_for_mcp_server(key)
        return IntegrationDetail(
            connection=conn,
            config_document={"mcpServers": {key: conn.config}},
            linked_capabilities=caps,
        )
    if protocol == "A2A":
        conn = next((c for c in _list_a2a_connections() if c.key == key), None)
        if not conn:
            raise KeyError("Integration not found")
        return IntegrationDetail(
            connection=conn,
            config_document={"servers": {key: conn.config.get("url", "")}},
        )
    if protocol == "ACP":
        conn = next((c for c in _list_acp_connections() if c.key == key), None)
        if not conn:
            raise KeyError("Integration not found")
        return IntegrationDetail(
            connection=conn,
            config_document={"agent_servers": {key: conn.config}},
        )
    raise KeyError("Integration not found")


def upsert_connection(payload: dict[str, Any]) -> IntegrationDetail:
    protocol = str(payload.get("protocol") or "MCP").upper()
    key = str(payload.get("key") or payload.get("id") or payload.get("name") or "").strip()
    if not key:
        raise ValueError("Connection key is required")
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", key):
        raise ValueError("Invalid connection key")

    if protocol == "MCP":
        entry = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        if payload.get("command") or payload.get("url"):
            entry = {k: v for k, v in payload.items() if k in {"command", "args", "env", "url", "headers"}}
        report = validate_mcp_entry(key, entry)
        if not report["valid"]:
            raise ValueError("; ".join(e["message"] for e in report["errors"]))
        current = build_mcp_servers_document(mask_secrets=False)
        servers = dict(current.get("mcpServers") or {})
        servers[key] = entry
        apply_mcp_servers_document({"mcpServers": servers})
        # enrich metadata
        if payload.get("name") or payload.get("description") or payload.get("tools") is not None:
            doc = mcp_config.load_mcp_document()
            for server in doc.get("servers") or []:
                if server.get("id") == key:
                    if payload.get("name"):
                        server["name"] = str(payload["name"])
                    if payload.get("description") is not None:
                        server["description"] = str(payload.get("description") or "")
                    if payload.get("tools") is not None:
                        server["tools"] = list(payload.get("tools") or [])
                    if payload.get("enabled") is not None:
                        server["enabled"] = bool(payload["enabled"])
            mcp_config.save_mcp_document(doc)
        return detail(f"mcp:{key}")

    if protocol == "A2A":
        url = str(payload.get("url") or (payload.get("config") or {}).get("url") or "").strip()
        report = validate_a2a_entry(key, url)
        if not report["valid"]:
            raise ValueError("; ".join(e["message"] for e in report["errors"]))
        doc = load_a2a_document()
        doc["servers"][key] = url
        save_a2a_document(doc)
        return detail(f"a2a:{key}")

    if protocol == "ACP":
        entry = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        if payload.get("command"):
            entry = {k: v for k, v in payload.items() if k in {"command", "args", "env"}}
        report = validate_acp_entry(key, entry)
        if not report["valid"]:
            raise ValueError("; ".join(e["message"] for e in report["errors"]))
        doc = load_acp_document()
        doc["agent_servers"][key] = entry
        save_acp_document(doc)
        return detail(f"acp:{key}")

    raise ValueError("protocol must be MCP, A2A, or ACP")


def delete_connection(integration_id: str) -> None:
    protocol, key = _parse_id(integration_id)
    if protocol == "MCP":
        mcp_config.apply_mcp_save({"delete": key})
        return
    if protocol == "A2A":
        doc = load_a2a_document()
        doc["servers"].pop(key, None)
        save_a2a_document(doc)
        return
    if protocol == "ACP":
        doc = load_acp_document()
        doc["agent_servers"].pop(key, None)
        save_acp_document(doc)
        return
    raise KeyError("Integration not found")


def ensure_integrations_seeded() -> None:
    """Ensure A2A/ACP config files exist (MCP lives in config/mcp)."""
    if not a2a_config_path().exists():
        save_a2a_document({"servers": {}})
    if not acp_config_path().exists():
        save_acp_document({"agent_servers": {}})


# Back-compat aliases used by older call sites / tests
def catalog_items(**kwargs: Any) -> list[IntegrationConnection]:
    return catalog(
        search=kwargs.get("search", ""),
        protocol=kwargs.get("protocol") or kwargs.get("category", ""),
        status=kwargs.get("status") or kwargs.get("health", ""),
    ).connections


def metrics() -> IntegrationMetrics:
    return catalog().metrics
