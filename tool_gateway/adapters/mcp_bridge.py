"""MCP adapter bridge — thin HTTP integrations for Jira/Slack (BND-006)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _jira_creds() -> tuple[str, str, str]:
    from src.workflow_ui.mcp_config import load_mcp_settings
    cfg = load_mcp_settings().get("jira", {})
    base = os.environ.get("JIRA_BASE_URL", "") or cfg.get("base_url", "")
    email = os.environ.get("JIRA_USER_EMAIL", "") or cfg.get("user_email", "")
    token = os.environ.get("JIRA_API_TOKEN", "") or cfg.get("api_token", "")
    return base.rstrip("/"), email, token


def _slack_token() -> str:
    from src.workflow_ui.mcp_config import load_mcp_settings
    cfg = load_mcp_settings().get("slack", {})
    return os.environ.get("SLACK_BOT_TOKEN", "") or cfg.get("bot_token", "")


async def jira_add_comment(issue_key: str, body: str) -> dict[str, Any]:
    base, email, token = _jira_creds()
    if not base or not email or not token:
        raise RuntimeError("Jira MCP not configured (JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN)")
    adf_body = {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}],
    }
    async with httpx.AsyncClient(
        base_url=base,
        auth=(email, token),
        timeout=30.0,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    ) as client:
        resp = await client.post(f"/rest/api/3/issue/{issue_key}/comment", json={"body": adf_body})
        resp.raise_for_status()
        data = resp.json()
        return {"issue_key": issue_key, "comment_id": data.get("id"), "status": "posted"}


async def slack_reply_to_thread(channel_id: str, thread_ts: str, text: str) -> dict[str, Any]:
    token = _slack_token()
    if not token:
        raise RuntimeError("Slack MCP not configured (SLACK_BOT_TOKEN)")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"channel": channel_id, "thread_ts": thread_ts, "text": text},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("error", "slack_api_error"))
        return {"channel_id": channel_id, "thread_ts": thread_ts, "ts": data.get("ts"), "status": "posted"}


async def invoke_mcp(server: str, tool_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    if server == "jira" and tool_name == "add_comment":
        return await jira_add_comment(inputs["issue_key"], inputs["body"])
    if server == "slack" and tool_name == "slack_reply_to_thread":
        return await slack_reply_to_thread(inputs["channel_id"], inputs["thread_ts"], inputs["text"])
    raise RuntimeError(f"Unsupported MCP tool: {server}/{tool_name}")
