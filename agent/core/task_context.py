"""Task context passed to agent run."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TaskContext:
    """Context for a single task execution."""

    task_id: str
    source: str
    source_id: str
    callback_url: Optional[str] = None
    chat_delivered: bool = False
