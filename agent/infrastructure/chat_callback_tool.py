"""Function tool for sending agent response to chat via HTTP callback."""

import logging
from typing import Any

import httpx
from agents import RunContextWrapper, function_tool

from src.agent.core.task_context import TaskContext

logger = logging.getLogger(__name__)


def create_send_to_chat_tool() -> Any:
    """
    Create send_to_chat function tool.

    The tool sends the agent's response to the chat gateway via callback_url from context.
    """

    @function_tool
    async def send_to_chat(ctx: RunContextWrapper[TaskContext], message: str) -> str:
        """Send the task result to the chat. Call this EXACTLY ONCE with your complete answer. Do NOT call again. Do NOT send status messages like "Task completed" — only the actual content.

        Args:
            message: Your full result or answer (the actual content, never a status or confirmation).
        """
        task_ctx = ctx.context
        if not task_ctx.callback_url:
            logger.warning("No callback_url in task context, cannot send to chat")
            return "Callback URL not configured. Result was not sent."
        if task_ctx.chat_delivered:
            return "Already delivered."
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    task_ctx.callback_url,
                    json={
                        "task_id": task_ctx.task_id,
                        "source_id": task_ctx.source_id,
                        "message": message,
                    },
                )
                if resp.is_success:
                    task_ctx.chat_delivered = True
                    return "Delivered."
                return f"Failed to send: {resp.status_code} {resp.text}"
        except Exception as e:
            logger.exception("Failed to send to chat callback")
            return f"Error sending message: {e}"

    return send_to_chat
