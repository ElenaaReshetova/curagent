"""Minimal template / path helpers used at Temporal activity input render time.

Not a separate product layer — just ``{{ .outputs.x }}`` substitution.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_PLACEHOLDER = re.compile(r"\{\{\s*(.*?)\s*\}\}")
_BRACKET = re.compile(r'\[["\']([^"\']+)["\']\]')
_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def resolve_path(obj: Any, path: str) -> Any:
    text = (path or "").strip().lstrip(".")
    text = _BRACKET.sub(r".\1", text)
    cur: Any = obj
    for part in [p for p in text.split(".") if p]:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, (list, tuple)) and part.isdigit():
            i = int(part)
            cur = cur[i] if 0 <= i < len(cur) else None
        else:
            cur = getattr(cur, part, None)
    return cur


def render_templates(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        if "{{" not in value:
            return value
        full = _PLACEHOLDER.fullmatch(value.strip())
        if full:
            path = full.group(1).strip()
            resolved = resolve_path(context, path)
            if resolved is not None:
                return resolved
            if path.lstrip(".").startswith("secrets"):
                return value

        def _repl(m: re.Match[str]) -> str:
            path = m.group(1).strip()
            v = resolve_path(context, path)
            if v is None:
                if path.lstrip(".").startswith("secrets"):
                    return m.group(0)
                return ""
            if isinstance(v, (dict, list)):
                return json.dumps(v, ensure_ascii=False)
            return str(v)

        return _PLACEHOLDER.sub(_repl, value)
    if isinstance(value, dict):
        return {k: render_templates(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [render_templates(v, context) for v in value]
    return value


def get_by_path(obj: Any, path: str) -> Any:
    cur: Any = obj
    for part in (path or "").split("."):
        if not part:
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def normalize_hitl_decision(decision: str) -> str:
    """Map UI / Temporal HITL keys onto INPUT outlets (approve | decline | reject)."""
    d = (decision or "").strip().lower().replace("-", "_").replace(" ", "_")
    if d in {"approve", "approved", "accept", "ok"}:
        return "approve"
    if d in {"request_changes", "request_change", "changes", "changes_requested", "refine"}:
        return "decline"
    if d in {"reject", "rejected", "decline", "declined", "deny"}:
        return "decline" if d in {"decline", "declined"} else "reject"
    return d


def skill_text(result: Any) -> str:
    """Pull visible text out of execute_skill_step_activity / LLM payloads."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if not isinstance(result, dict):
        return str(result).strip()
    for key in ("response", "message", "text", "content"):
        val = result.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, dict):
            nested = skill_text(val)
            if nested:
                return nested
    for key in ("artifact", "output"):
        nested = skill_text(result.get(key))
        if nested:
            return nested
    return ""


def enrich_run_input(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize Slack/task payload so templates can use ``.outputs.trigger.*``.

    Slack gateway stores ``source_id`` as ``slack:{channel}:{thread_ts}``.
    Self-serve Test run sends ``channel`` / ``thread_ts`` / ``text`` directly.
    """
    inp = dict(raw or {})
    source_id = str(inp.get("source_id") or "").strip()
    if source_id.startswith("slack:"):
        parts = source_id.split(":", 2)
        if len(parts) == 3:
            inp.setdefault("channel", parts[1])
            inp.setdefault("thread_ts", parts[2])
    if not str(inp.get("text") or "").strip():
        for key in ("description", "title"):
            val = str(inp.get(key) or "").strip()
            if val:
                inp["text"] = val
                break
    if not str(inp.get("channel") or "").strip():
        channels = (os.environ.get("SLACK_CHANNEL_IDS") or "").split(",")
        fallback = channels[0].strip() if channels else ""
        if fallback:
            inp["channel"] = fallback
    return inp


def workflow_secrets() -> dict[str, str]:
    """Secrets available as ``{{ .secrets["slack-bot-token"] }}`` in node configs."""
    token = (os.environ.get("SLACK_BOT_TOKEN") or "").strip()
    if not token:
        token = _slack_token_from_mcp()
    if not token:
        return {}
    return {"slack-bot-token": token}


def _slack_token_from_mcp() -> str:
    roots = [
        Path(os.environ["MCP_CONFIG_DIR"]) if os.environ.get("MCP_CONFIG_DIR") else None,
        Path("config/mcp"),
        Path(__file__).resolve().parents[3] / "config" / "mcp",
    ]
    for root in roots:
        if root is None:
            continue
        path = root / "servers.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for server in data.get("servers") or []:
            env = server.get("env") if isinstance(server, dict) else None
            if not isinstance(env, dict):
                continue
            token = str(env.get("SLACK_BOT_TOKEN") or "").strip()
            if token:
                return token
    return ""


def parse_structured_json(text: Any) -> dict[str, Any]:
    """Pull a JSON object out of an AI response (raw or fenced)."""
    if isinstance(text, dict):
        return text
    raw = str(text or "").strip()
    if not raw:
        return {}
    raw = _JSON_FENCE.sub("", raw).strip()
    for candidate in (raw,):
        parsed = _try_json_object(candidate)
        if parsed:
            return parsed
    match = _JSON_OBJECT.search(raw)
    if match:
        parsed = _try_json_object(match.group(0))
        if parsed:
            return parsed
    return {}


def _try_json_object(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}
