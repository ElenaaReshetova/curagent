"""FastAPI application for the agent: /health and POST /task."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agent.core.runner import build_agent, run_task
from src.agent.core.task_context import TaskContext
from src.agent.infrastructure.mcp_jira import create_jira_mcp_server
from src.agent.infrastructure.mcp_slack import create_slack_mcp_server

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# State
_busy = False
_agent = None
_mcp_manager = None
_project_root = Path(__file__).resolve().parents[3]
_skills_dir = os.environ.get("SKILLS_DIR")  # Optional: single path or comma-separated
_gigachat_credentials = os.environ.get("GIGACHAT_CREDENTIALS")
_gigachat_model = os.environ.get("GIGACHAT_MODEL", "GigaChat")
_lm_studio_url = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1")
_lm_studio_model = os.environ.get("LM_STUDIO_MODEL", "local-model")
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage MCP server lifecycle (connect on startup, cleanup on shutdown)."""
    global _mcp_manager
    try:
        try:
            from agents.mcp import MCPServerManager
        except ImportError:
            logger.info("MCP not available (requires Python 3.10+), Slack replies will use HTTP callback")
            yield
            return

        slack_server = create_slack_mcp_server(project_root=_project_root)
        jira_server = create_jira_mcp_server(project_root=_project_root)
        servers = [s for s in [slack_server, jira_server] if s is not None]
        if servers:
            async with MCPServerManager(servers, drop_failed_servers=True, strict=False) as manager:
                _mcp_manager = manager
                logger.info("MCP servers connected: %s", [s.name for s in manager.active_servers])
                yield
        else:
            yield
    finally:
        _mcp_manager = None


app = FastAPI(title="Autonomous Agent API", lifespan=lifespan)


def get_agent():
    """Lazy init agent."""
    global _agent
    if _agent is None:
        skills_dir = Path(_skills_dir).expanduser() if _skills_dir else None
        skills_dirs = None
        if _skills_dir and "," in _skills_dir:
            skills_dirs = [Path(p.strip()).expanduser() for p in _skills_dir.split(",")]
            skills_dir = None
        mcp_servers = []
        if _mcp_manager:
            mcp_servers = _mcp_manager.active_servers
        _agent = build_agent(
            skills_dir=skills_dir,
            skills_dirs=skills_dirs,
            project_root=_project_root,
            gigachat_credentials=_gigachat_credentials,
            gigachat_model=_gigachat_model,
            lm_studio_url=_lm_studio_url,
            lm_studio_model=_lm_studio_model,
            mcp_servers=mcp_servers,
        )
    return _agent


class TaskRequest(BaseModel):
    """Task payload for POST /task."""

    task_id: str = Field(..., description="Unique task ID")
    source: str = Field(..., description="Source: chat, jira, slack")
    source_id: str = Field(..., description="Source-specific ID")
    description: str = Field(..., description="Task description")
    callback_url: Optional[str] = Field(default=None, description="Callback URL for result")


@app.get("/health")
async def health():
    """Return agent status: free or busy."""
    return {"status": "busy" if _busy else "free"}


@app.post("/task")
async def accept_task(req: TaskRequest):
    """
    Accept a task and process it in the background.

    Returns 202 immediately. The agent processes the task asynchronously.
    """
    global _busy
    if _busy:
        raise HTTPException(status_code=503, detail="Agent is busy")

    _busy = True

    async def _run():
        global _busy
        try:
            agent = get_agent()
            ctx = TaskContext(
                task_id=req.task_id,
                source=req.source,
                source_id=req.source_id,
                callback_url=req.callback_url,
            )
            # MCP tools not yet integrated with LangChain ReAct agent; always use send_to_chat
            available_mcp_names: list[str] = []
            await run_task(agent, req.description, ctx, available_mcp_names=available_mcp_names)
        except Exception as e:
            logger.exception("Task execution failed: %s", e)
        finally:
            _busy = False

    asyncio.create_task(_run())
    return {"status": "accepted", "task_id": req.task_id}


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
