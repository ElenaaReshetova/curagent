"""MCP Slack server for agent-to-Slack interaction via Model Context Protocol."""

import logging
import os
from pathlib import Path
from typing import Optional

try:
    from agents.mcp import MCPServerStdio, MCPServerStdioParams
except ImportError:
    MCPServerStdio = None  # type: ignore
    MCPServerStdioParams = None  # type: ignore

logger = logging.getLogger(__name__)


def create_slack_mcp_server(
    project_root: Optional[Path] = None,
    slack_bot_token: Optional[str] = None,
    slack_team_id: Optional[str] = None,
    slack_channel_ids: Optional[str] = None,
) -> Optional[MCPServerStdio]:
    """
    Create MCP Slack server if SLACK_BOT_TOKEN is configured.

    The server is used by the agent to send replies to Slack threads via
    slack_reply_to_thread (instead of HTTP callback).

    Args:
        project_root: Path to project root (for mcp-slack location).
        slack_bot_token: Slack bot token (xoxb-*). Defaults to SLACK_BOT_TOKEN env.
        slack_team_id: Slack team ID. Defaults to SLACK_TEAM_ID env.
        slack_channel_ids: Comma-separated channel IDs. Defaults to SLACK_CHANNEL_IDS env.

    Returns:
        MCPServerStdio instance or None if token not configured or MCP unavailable.
    """
    if MCPServerStdio is None:
        logger.debug("MCP not available (requires Python 3.10+), skipping Slack MCP")
        return None

    token = slack_bot_token or os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        logger.info("SLACK_BOT_TOKEN not set, MCP Slack disabled")
        return None

    root = project_root or Path(__file__).resolve().parents[3]
    mcp_slack_path = root / "mcp-slack"
    server_script = mcp_slack_path / "node_modules" / "@modelcontextprotocol" / "server-slack" / "dist" / "index.js"

    if not server_script.exists():
        logger.warning("MCP Slack server script not found at %s", server_script)
        return None

    env = {
        "SLACK_BOT_TOKEN": token,
        "SLACK_TEAM_ID": slack_team_id or os.environ.get("SLACK_TEAM_ID", ""),
        "SLACK_CHANNEL_IDS": slack_channel_ids or os.environ.get("SLACK_CHANNEL_IDS", ""),
    }

    params: MCPServerStdioParams = {
        "command": "node",
        "args": [str(server_script)],
        "env": env,
        "cwd": str(mcp_slack_path),
    }

    return MCPServerStdio(
        params=params,
        cache_tools_list=True,
        name="slack",
        client_session_timeout_seconds=15,
    )
