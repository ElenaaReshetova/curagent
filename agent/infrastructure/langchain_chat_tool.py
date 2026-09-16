"""LangChain tool for sending agent response to chat via HTTP callback."""

import logging
from typing import TYPE_CHECKING

import httpx
from langchain_core.tools import tool

if TYPE_CHECKING:
    from src.agent.core.task_context import TaskContext

logger = logging.getLogger(__name__)


def create_send_to_chat_tool(task_context: "TaskContext"):
    """
    Create send_to_chat LangChain tool bound to task context.

    The tool sends the agent's response to the chat gateway via callback_url.
    """

    @tool
    async def send_to_chat(message: str) -> str:
        """Send the task result to the chat. Call this EXACTLY ONCE with your complete answer. Do NOT call again. Do NOT send status messages like "Task completed" — only the actual content.

        Args:
            message: Your full result or answer (the actual content, never a status or confirmation).
        """
        if not task_context.callback_url:
            logger.warning("No callback_url in task context, cannot send to chat")
            return "Callback URL not configured. Result was not sent."
        if task_context.chat_delivered:
            return "Already delivered."
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    task_context.callback_url,
                    json={
                        "task_id": task_context.task_id,
                        "source_id": task_context.source_id,
                        "message": message,
                    },
                )
                if resp.is_success:
                    task_context.chat_delivered = True
                    return "Delivered."
                return f"Failed to send: {resp.status_code} {resp.text}"
        except Exception as e:
            logger.exception("Failed to send to chat callback")
            return f"Error sending message: {e}"

    return send_to_chat
