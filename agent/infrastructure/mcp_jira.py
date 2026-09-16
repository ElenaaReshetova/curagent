"""MCP Jira server for agent-to-Jira interaction via Model Context Protocol."""

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


def create_jira_mcp_server(
    project_root: Optional[Path] = None,
    jira_base_url: Optional[str] = None,
    jira_user_email: Optional[str] = None,
    jira_api_token: Optional[str] = None,
    jira_type: Optional[str] = None,
) -> Optional[MCPServerStdio]:
    """
    Create MCP Jira server if JIRA credentials are configured.

    The server provides tools for the agent to search issues, get details,
    create/update issues, add comments, etc.

    Args:
        project_root: Path to project root (for mcp-jira location).
        jira_base_url: Jira instance URL (e.g. https://your-domain.atlassian.net).
        jira_user_email: Jira account email.
        jira_api_token: Jira API token.
        jira_type: 'cloud' or 'server'. Defaults to 'cloud'.

    Returns:
        MCPServerStdio instance or None if not configured or MCP unavailable.
    """
    if MCPServerStdio is None:
        logger.debug("MCP not available (requires Python 3.10+), skipping Jira MCP")
        return None

    base_url = jira_base_url or os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    email = jira_user_email or os.environ.get("JIRA_USER_EMAIL")
    token = jira_api_token or os.environ.get("JIRA_API_TOKEN")

    if not base_url or not email or not token:
        logger.info("JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN not set, MCP Jira disabled")
        return None

    root = project_root or Path(__file__).resolve().parents[3]
    mcp_jira_path = root / "mcp-jira"
    server_script = mcp_jira_path / "build" / "index.js"

    if not server_script.exists():
        logger.warning("MCP Jira server script not found at %s", server_script)
        return None

    env = {
        "JIRA_BASE_URL": base_url,
        "JIRA_USER_EMAIL": email,
        "JIRA_API_TOKEN": token,
        "JIRA_TYPE": jira_type or os.environ.get("JIRA_TYPE", "cloud"),
        "JIRA_AUTH_TYPE": os.environ.get("JIRA_AUTH_TYPE", "basic"),
    }

    params: MCPServerStdioParams = {
        "command": "node",
        "args": [str(server_script)],
        "env": env,
        "cwd": str(mcp_jira_path),
    }

    return MCPServerStdio(
        params=params,
        cache_tools_list=True,
        name="jira",
        client_session_timeout_seconds=15,
    )
