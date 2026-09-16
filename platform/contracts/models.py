"""Artifact contract models — typed I/O between skills and graphs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ArtifactContract(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    name: str
    description: str = ""
    kind: Literal["artifact", "patch", "work_item", "decision"] = "artifact"
    # JSON schema used for lightweight payload shape validation.
    json_schema: dict[str, Any] = Field(default_factory=dict)
    # Keys this contract can satisfy (e.g. SlackWorkItem@1 satisfies WorkItem@1).
    satisfies: list[str] = Field(default_factory=list)
    # Keys accepted as compatible input (e.g. ProblemUnderstandingPatch@1 for Artifact@1).
    accepts: list[str] = Field(default_factory=list)
    status: Literal["draft", "active", "deprecated"] = "active"
    updated_at: datetime = Field(default_factory=datetime.utcnow)
