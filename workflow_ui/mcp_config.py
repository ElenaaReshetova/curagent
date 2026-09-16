"""MCP server registry — editable via UI form or config JSON."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "config" / "mcp"
_SERVERS_FILE = "servers.json"
_LOCAL_FILE = "servers.local.json"
_SECRET_KEYS = {
    "token", "api_token", "bot_token", "password", "secret", "api_key",
    "SLACK_BOT_TOKEN", "JIRA_API_TOKEN",
}


def get_mcp_config_dir() -> Path:
    env = os.environ.get("MCP_CONFIG_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return _DEFAULT_DIR


def servers_json_path() -> Path:
    return get_mcp_config_dir() / _SERVERS_FILE


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _normalize_server(raw: dict[str, Any], fallback_id: str = "") -> dict[str, Any]:
    sid = str(raw.get("id") or fallback_id or "").strip()
    if not sid:
        raise ValueError("MCP server requires id")
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$", sid):
        raise ValueError(f"Invalid MCP server id: {sid}")

    stype = raw.get("type") or "stdio"
    if stype not in ("builtin", "stdio", "sse", "http"):
        stype = "stdio"

    env = raw.get("env") or {}
    if not isinstance(env, dict):
        env = {}
    env = {str(k): "" if v is None else str(v) for k, v in env.items()}

    args = raw.get("args") or []
    if isinstance(args, str):
        args = [a for a in args.split() if a]
    elif not isinstance(args, list):
        args = []
    args = [str(a) for a in args]

    tools = raw.get("tools") or []
    if isinstance(tools, str):
        tools = [t.strip() for t in tools.split(",") if t.strip()]
    elif not isinstance(tools, list):
        tools = []
    tools = [str(t) for t in tools]

    return {
        "id": sid,
        "name": str(raw.get("name") or sid).strip(),
        "description": str(raw.get("description") or "").strip(),
        "enabled": bool(raw.get("enabled", True)),
        "type": stype,
        "builtin": str(raw.get("builtin") or (sid if stype == "builtin" else "")).strip(),
        "command": str(raw.get("command") or "").strip(),
        "args": args,
        "url": str(raw.get("url") or "").strip(),
        "headers": raw.get("headers") if isinstance(raw.get("headers"), dict) else {},
        "env": env,
        "tools": tools,
    }


def _migrate_legacy(data: dict[str, Any]) -> dict[str, Any]:
    """Convert old {slack: {...}, jira: {...}} shape to {version, servers: [...]}."""
    if "servers" in data and isinstance(data["servers"], list):
        return data

    servers: list[dict[str, Any]] = []
    if "slack" in data and isinstance(data["slack"], dict):
        s = data["slack"]
        servers.append(_normalize_server({
            "id": "slack",
            "name": "Slack",
            "description": "Ответы в Slack threads",
            "enabled": s.get("enabled", True),
            "type": "builtin",
            "builtin": "slack",
            "env": {
                "SLACK_BOT_TOKEN": s.get("bot_token", ""),
                "SLACK_TEAM_ID": s.get("team_id", ""),
                "SLACK_CHANNEL_IDS": s.get("channel_ids", ""),
            },
            "tools": ["slack_reply_to_thread"],
        }))
    if "jira" in data and isinstance(data["jira"], dict):
        j = data["jira"]
        servers.append(_normalize_server({
            "id": "jira",
            "name": "Jira",
            "description": "Комментарии и операции с Jira",
            "enabled": j.get("enabled", True),
            "type": "builtin",
            "builtin": "jira",
            "env": {
                "JIRA_BASE_URL": j.get("base_url", ""),
                "JIRA_USER_EMAIL": j.get("user_email", ""),
                "JIRA_API_TOKEN": j.get("api_token", ""),
                "JIRA_PROJECT": j.get("project", "CUR"),
                "JIRA_TYPE": j.get("type", "cloud"),
            },
            "tools": ["add_comment", "search_issues", "get_issue"],
        }))
    return {"version": 1, "servers": servers}


def _default_document() -> dict[str, Any]:
    return {
        "version": 1,
        "servers": [
            _normalize_server({
                "id": "slack",
                "name": "Slack",
                "description": "Ответы в Slack threads",
                "type": "builtin",
                "builtin": "slack",
                "env": {
                    "SLACK_BOT_TOKEN": "",
                    "SLACK_TEAM_ID": "",
                    "SLACK_CHANNEL_IDS": "",
                },
                "tools": ["slack_reply_to_thread"],
            }),
            _normalize_server({
                "id": "jira",
                "name": "Jira",
                "description": "Комментарии и операции с Jira",
                "type": "builtin",
                "builtin": "jira",
                "env": {
                    "JIRA_BASE_URL": "",
                    "JIRA_USER_EMAIL": "",
                    "JIRA_API_TOKEN": "",
                    "JIRA_PROJECT": "CUR",
                    "JIRA_TYPE": "cloud",
                },
                "tools": ["add_comment", "search_issues", "get_issue"],
            }),
        ],
    }


def _merge_server_lists(base: list[dict], overlay: list[dict]) -> list[dict]:
    by_id = {s["id"]: dict(s) for s in base}
    for s in overlay:
        sid = s["id"]
        if sid in by_id:
            merged = {**by_id[sid], **s}
            env = {**(by_id[sid].get("env") or {}), **(s.get("env") or {})}
            # empty secret in overlay should not wipe existing
            for k, v in list(env.items()):
                if _is_secret_key(k) and not v and by_id[sid].get("env", {}).get(k):
                    env[k] = by_id[sid]["env"][k]
            merged["env"] = env
            by_id[sid] = merged
        else:
            by_id[sid] = s
    # preserve overlay order when possible, then remaining
    order = [s["id"] for s in overlay] + [s["id"] for s in base if s["id"] not in {x["id"] for x in overlay}]
    seen = set()
    result = []
    for sid in order:
        if sid in by_id and sid not in seen:
            result.append(_normalize_server(by_id[sid], sid))
            seen.add(sid)
    return result


def load_mcp_document() -> dict[str, Any]:
    cfg_dir = get_mcp_config_dir()
    base = _migrate_legacy(_read_json(cfg_dir / _SERVERS_FILE))
    local = _migrate_legacy(_read_json(cfg_dir / _LOCAL_FILE))
    if not base.get("servers") and not local.get("servers"):
        return _default_document()
    if not base.get("servers"):
        return {"version": 1, "servers": [_normalize_server(s) for s in local.get("servers", [])]}
    if not local.get("servers"):
        return {"version": 1, "servers": [_normalize_server(s) for s in base.get("servers", [])]}
    return {
        "version": local.get("version") or base.get("version") or 1,
        "servers": _merge_server_lists(
            [_normalize_server(s) for s in base.get("servers", [])],
            [_normalize_server(s) for s in local.get("servers", [])],
        ),
    }


def load_mcp_settings() -> dict[str, Any]:
    """Backward-compatible dict: server_id -> config (for mcp_bridge builtins)."""
    doc = load_mcp_document()
    out: dict[str, Any] = {}
    for s in doc.get("servers", []):
        sid = s["id"]
        env = s.get("env") or {}
        if s.get("builtin") == "slack" or sid == "slack":
            out["slack"] = {
                "enabled": s.get("enabled", True),
                "bot_token": env.get("SLACK_BOT_TOKEN", ""),
                "team_id": env.get("SLACK_TEAM_ID", ""),
                "channel_ids": env.get("SLACK_CHANNEL_IDS", ""),
            }
        elif s.get("builtin") == "jira" or sid == "jira":
            out["jira"] = {
                "enabled": s.get("enabled", True),
                "base_url": env.get("JIRA_BASE_URL", ""),
                "user_email": env.get("JIRA_USER_EMAIL", ""),
                "api_token": env.get("JIRA_API_TOKEN", ""),
                "project": env.get("JIRA_PROJECT", ""),
                "type": env.get("JIRA_TYPE", "cloud"),
            }
        out[sid] = s
    return out


def save_mcp_document(doc: dict[str, Any], *, write_local: bool = True) -> dict[str, Any]:
    """Normalize and persist MCP config. Primary file: servers.json; secrets mirror to local."""
    servers = [_normalize_server(s) for s in doc.get("servers", [])]
    ids = [s["id"] for s in servers]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate MCP server id")
    normalized = {"version": int(doc.get("version") or 1), "servers": servers}

    cfg_dir = get_mcp_config_dir()
    _write_json(cfg_dir / _SERVERS_FILE, normalized)
    if write_local:
        _write_json(cfg_dir / _LOCAL_FILE, normalized)
    return load_mcp_document()


def get_server(server_id: str) -> Optional[dict[str, Any]]:
    for s in load_mcp_document().get("servers", []):
        if s["id"] == server_id:
            return s
    return None


def list_server_ids() -> list[str]:
    return [s["id"] for s in load_mcp_document().get("servers", []) if s.get("enabled", True)]


def _is_secret_key(key: str) -> bool:
    kl = key.lower()
    if key in _SECRET_KEYS:
        return True
    return any(x in kl for x in ("token", "password", "secret", "api_key", "apikey"))


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    return value[:4] + "••••" + value[-4:]


def _server_status(server: dict[str, Any]) -> str:
    if not server.get("enabled", True):
        return "disabled"
    stype = server.get("type")
    env = server.get("env") or {}
    if stype == "builtin":
        builtin = server.get("builtin") or server.get("id")
        if builtin == "slack":
            ok = bool(os.environ.get("SLACK_BOT_TOKEN") or env.get("SLACK_BOT_TOKEN")) and bool(
                os.environ.get("SLACK_TEAM_ID") or env.get("SLACK_TEAM_ID")
            )
            return "ready" if ok else "misconfigured"
        if builtin == "jira":
            ok = all([
                os.environ.get("JIRA_BASE_URL") or env.get("JIRA_BASE_URL"),
                os.environ.get("JIRA_USER_EMAIL") or env.get("JIRA_USER_EMAIL"),
                os.environ.get("JIRA_API_TOKEN") or env.get("JIRA_API_TOKEN"),
            ])
            return "ready" if ok else "misconfigured"
        return "ready"
    if stype in ("sse", "http"):
        return "ready" if server.get("url") else "misconfigured"
    # stdio
    return "ready" if server.get("command") else "misconfigured"


def _linked_capabilities() -> dict[str, list[str]]:
    linked: dict[str, list[str]] = {}
    try:
        from src.tool_gateway.registry.store import ensure_loaded, list_manifests
        ensure_loaded()
        for m in list_manifests():
            for impl in m.implementations or []:
                if impl.type == "mcp" and impl.server_id:
                    linked.setdefault(impl.server_id, []).append(m.capability_id)
            b = m.adapter_binding
            if b and b.type == "mcp" and b.mcp_server:
                linked.setdefault(b.mcp_server, []).append(m.capability_id)
    except Exception:
        pass
    return linked


def _public_env(env: dict[str, str]) -> dict[str, Any]:
    out = {}
    for k, v in env.items():
        env_val = os.environ.get(k, "")
        effective = env_val or v
        out[k] = {
            "value": _mask(effective) if _is_secret_key(k) and effective else ("" if _is_secret_key(k) else effective),
            "has_value": bool(effective),
            "source": "env" if env_val else ("config" if v else "unset"),
            "secret": _is_secret_key(k),
        }
    return out


def build_mcp_status() -> dict[str, Any]:
    doc = load_mcp_document()
    linked = _linked_capabilities()
    servers_out = []
    for s in doc.get("servers", []):
        status = _server_status(s)
        servers_out.append({
            **s,
            "status": status,
            "linked_capabilities": linked.get(s["id"], []),
            "env_status": _public_env(s.get("env") or {}),
            # do not leak raw secrets in API list view
            "env": {
                k: ("" if _is_secret_key(k) else v)
                for k, v in (s.get("env") or {}).items()
            },
        })
    return {
        "version": doc.get("version", 1),
        "servers": servers_out,
        "config_dir": str(get_mcp_config_dir()),
        "config_file": str(servers_json_path()),
        "local_file": str(get_mcp_config_dir() / _LOCAL_FILE),
        "document": {
            "version": doc.get("version", 1),
            "servers": [
                {
                    **s,
                    "env": {
                        k: ("" if _is_secret_key(k) and v else v)
                        for k, v in (s.get("env") or {}).items()
                    },
                }
                for s in doc.get("servers", [])
            ],
        },
    }


def apply_mcp_save(body: dict[str, Any]) -> dict[str, Any]:
    """
    Accept either:
    - { "servers": [...] } full document
    - { "document": { "servers": [...] } }
    - { "upsert": {server} } single server upsert
    - { "delete": "server-id" }
    """
    current = load_mcp_document()
    servers = list(current.get("servers", []))

    if "delete" in body and body["delete"]:
        sid = str(body["delete"])
        servers = [s for s in servers if s["id"] != sid]
        save_mcp_document({"version": current.get("version", 1), "servers": servers})
        return build_mcp_status()

    if "upsert" in body and isinstance(body["upsert"], dict):
        incoming = _normalize_server(body["upsert"])
        # preserve secrets if empty in upsert
        existing = next((s for s in servers if s["id"] == incoming["id"]), None)
        if existing:
            env = dict(existing.get("env") or {})
            for k, v in (incoming.get("env") or {}).items():
                if _is_secret_key(k) and not v:
                    continue
                env[k] = v
            incoming["env"] = env
            servers = [incoming if s["id"] == incoming["id"] else s for s in servers]
        else:
            servers.append(incoming)
        save_mcp_document({"version": current.get("version", 1), "servers": servers})
        return build_mcp_status()

    doc = body.get("document") if isinstance(body.get("document"), dict) else body
    if "servers" not in doc:
        # legacy patch {slack:..., jira:...}
        if any(k in body for k in ("slack", "jira")):
            migrated = _migrate_legacy({**load_mcp_settings(), **body})
            # merge secrets carefully into current servers list by id
            by_id = {s["id"]: s for s in servers}
            for s in migrated.get("servers", []):
                if s["id"] in by_id:
                    env = {**by_id[s["id"]].get("env", {}), **s.get("env", {})}
                    for k, v in list(env.items()):
                        if _is_secret_key(k) and not v:
                            env[k] = by_id[s["id"]].get("env", {}).get(k, "")
                    by_id[s["id"]] = {**by_id[s["id"]], **s, "env": env}
                else:
                    by_id[s["id"]] = s
            servers = list(by_id.values())
            save_mcp_document({"version": 1, "servers": servers})
            return build_mcp_status()
        raise ValueError("Body must include servers[] or upsert/delete")

    incoming_servers = [_normalize_server(s) for s in doc["servers"]]
    existing_by_id = {s["id"]: s for s in servers}
    merged = []
    for s in incoming_servers:
        prev = existing_by_id.get(s["id"])
        if prev:
            env = dict(prev.get("env") or {})
            for k, v in (s.get("env") or {}).items():
                if _is_secret_key(k) and not v:
                    continue
                env[k] = v
            s["env"] = env
        merged.append(s)
    save_mcp_document({"version": int(doc.get("version") or 1), "servers": merged})
    return build_mcp_status()


def get_raw_config_for_editor() -> dict[str, Any]:
    """Full document for JSON editor (secrets blanked if set — leave empty to keep)."""
    doc = load_mcp_document()
    return {
        "version": doc.get("version", 1),
        "servers": [
            {
                **s,
                "env": {
                    k: ("" if _is_secret_key(k) else v)
                    for k, v in (s.get("env") or {}).items()
                },
            }
            for s in doc.get("servers", [])
        ],
    }
