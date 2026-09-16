"""Shared task model for Kafka and API."""

from typing import Optional

from pydantic import BaseModel, Field


class TaskMessage(BaseModel):
    """Task message format for Kafka and agent."""

    task_id: str = Field(..., description="Unique task identifier")
    source: str = Field(..., description="Source: chat, jira, slack")
    source_id: str = Field(..., description="Source-specific ID (e.g. chat_session_123)")
    description: str = Field(..., description="Task description")
    created_at: str = Field(..., description="ISO8601 timestamp")
    callback_url: Optional[str] = Field(
        default=None,
        description="URL for agent to POST result (e.g. chat gateway callback)",
    )
