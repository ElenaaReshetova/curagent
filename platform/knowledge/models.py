"""Knowledge Spaces domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


SpaceType = Literal["DOMAIN", "PRODUCT", "TEAM", "SYSTEM", "REGULATORY", "TEMPORARY"]
SpaceStatus = Literal["DRAFT", "ACTIVE", "DEGRADED", "DISABLED", "ARCHIVED"]
Classification = Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
SourceStatus = Literal["ACTIVE", "DISABLED", "DEGRADED", "ERROR"]
ProviderKind = Literal[
    "jira", "confluence", "slack", "git", "api_catalog", "policy_library", "audit_repo", "other",
]


class SourceBinding(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    provider: ProviderKind
    name: str
    selector: dict[str, Any] = Field(default_factory=dict)
    priority: int = 50
    status: SourceStatus = "ACTIVE"
    health_pct: float = 100.0
    last_checked_at: Optional[datetime] = None


class KnowledgeSpaceRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str = "default"
    key: str
    name: str
    purpose: str = ""
    space_type: SpaceType = "DOMAIN"
    status: SpaceStatus = "DRAFT"
    classification: Classification = "INTERNAL"
    owner_team: str = "Platform"
    project_areas: list[str] = Field(default_factory=list)
    team_names: list[str] = Field(default_factory=list)
    additional_context: str = ""
    sources: list[SourceBinding] = Field(default_factory=list)
    search_policy: dict[str, Any] = Field(default_factory=dict)
    access_policy: dict[str, Any] = Field(default_factory=dict)
    freshness_hours: int = 24
    usage_30d: int = 0
    search_success_pct: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    revision: int = 1


class KnowledgeCatalogItem(BaseModel):
    id: str
    key: str
    name: str
    purpose: str = ""
    space_type: str
    status: str
    classification: str
    owner: str = ""
    source_count: int = 0
    source_labels: list[str] = Field(default_factory=list)
    health_pct: float = 100.0
    usage_30d: int = 0


class KnowledgeMetrics(BaseModel):
    active_spaces: int = 0
    connected_sources: int = 0
    healthy_sources: int = 0
    search_success_pct: float = 0.0
    stale_sources: int = 0
