"""Resolve delivery tool from task source and available MCP servers.

The agent is source-agnostic: it receives a task with delivery instructions
built by this resolver. The resolver maps (source, source_id) + available MCPs
to (tool_name, params). No hardcoded source logic in the agent or runner.
"""

import logging
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class DeliveryInstruction:
    """Tool to call and its parameters for delivering the agent's response."""

    tool: str
    params: dict
    content_param: str = "text"  # param name for message content (text for slack, body for jira)


def _parse_slack_source_id(source_id: str) -> Optional[dict]:
    """Parse slack:channel_id:thread_ts -> {channel_id, thread_ts}."""
    parts = source_id.split(":", 2)
    if len(parts) != 3 or parts[0] != "slack":
        return None
    return {"channel_id": parts[1], "thread_ts": parts[2]}


def _parse_jira_source_id(source_id: str) -> Optional[dict]:
    """Parse jira:ISSUE_KEY -> {issue_key} for add_comment tool."""
    parts = source_id.split(":", 1)
    if len(parts) != 2 or parts[0] != "jira":
        return None
    return {"issueIdOrKey": parts[1]}


# Registry: source -> (mcp_name, tool_name, params_parser) or (tool_name for non-MCP)
# When MCP is available: use MCP tool. When not: use fallback (send_to_chat via callback).
_DELIVERY_REGISTRY: dict[str, dict] = {
    "slack": {
        "mcp_name": "slack",
        "mcp_tool": "slack_reply_to_thread",
        "params_from_source_id": _parse_slack_source_id,
        "fallback_tool": "send_to_chat",
    },
    "chat": {
        "tool": "send_to_chat",
    },
    "jira": {
        "mcp_name": "jira",
        "mcp_tool": "add_comment",
        "params_from_source_id": _parse_jira_source_id,
        "fallback_tool": "send_to_chat",
        "content_param": "body",  # add_comment uses body, slack uses text
    },
}


def resolve_delivery(
    source: str,
    source_id: str,
    available_mcp_names: list[str],
) -> Optional[DeliveryInstruction]:
    """
    Resolve which tool the agent should use to deliver the response.

    Args:
        source: Task source (slack, chat, jira, ...)
        source_id: Source-specific ID (e.g. slack:channel:ts, session_id)
        available_mcp_names: Names of connected MCP servers (e.g. ["slack"])

    Returns:
        DeliveryInstruction with tool name and params, or None if source unknown.
    """
    config = _DELIVERY_REGISTRY.get(source)
    if not config:
        logger.warning("Unknown source %r, no delivery config", source)
        return None

    # Non-MCP source (e.g. chat): use built-in tool
    if "tool" in config:
        return DeliveryInstruction(tool=config["tool"], params={})

    # MCP source: use MCP tool if available, else fallback
    mcp_name = config.get("mcp_name")
    mcp_tool = config.get("mcp_tool")
    params_fn: Optional[Callable[[str], Optional[dict]]] = config.get("params_from_source_id")
    fallback = config.get("fallback_tool", "send_to_chat")

    if mcp_name in available_mcp_names and mcp_tool and params_fn:
        params = params_fn(source_id)
        if params:
            content_param = config.get("content_param", "text")
            return DeliveryInstruction(tool=mcp_tool, params=params, content_param=content_param)

    # Fallback to callback-based delivery
    return DeliveryInstruction(tool=fallback, params={})


_FULL_DELIVERY_NOTE = """
CRITICAL — delivery rules:
0. LANGUAGE: Respond in the SAME language as the user's message. If they write in Russian — answer in Russian. If in English — in English. Never switch to English when the user wrote in Russian.
1. Call the delivery tool EXACTLY ONCE when you have the complete answer. Never call it again.
2. The message parameter (text/body) must contain the ACTUAL content INLINE — the full document, not a description or reference. Put the entire PRD/BRD/document body in the text argument. Never write "I've outlined...", "Here's a breakdown...", "Does this address..." — write the actual document sections (Problem Statement, Goals, Requirements, etc.) with real content.
3. Never send status messages like "Task completed", "Delivered", or "Here is the result".
4. When a Skill applies (e.g. PRD, BRD, user stories), produce and deliver the FULL structured document as specified in that Skill.
"""


def format_delivery_instructions(delivery: DeliveryInstruction) -> str:
    """Format delivery instruction as text for the agent's task."""
    if delivery.tool == "send_to_chat":
        return (
            "[RESPONSE INSTRUCTIONS] To deliver your answer, call send_to_chat with your message."
            + _FULL_DELIVERY_NOTE
            + "\n"
        )
    # MCP tool with params (e.g. slack_reply_to_thread, add_comment)
    params_str = ", ".join(f"{k}={v!r}" for k, v in delivery.params.items())
    content_param = getattr(delivery, "content_param", "text")
    return (
        f"[RESPONSE INSTRUCTIONS] To deliver your answer, call {delivery.tool} with "
        f"{params_str}, and {content_param}=<your complete answer>."
        + _FULL_DELIVERY_NOTE
        + "\n\n"
    )
