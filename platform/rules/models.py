"""Rules subsystem domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


RuleCategory = Literal[
    "STYLE", "TERMINOLOGY", "FORMAT", "NAMING", "DOMAIN", "QUALITY",
    "CODING_STANDARD", "DOCUMENT_TEMPLATE", "OUTPUT_CONSTRAINT", "LANGUAGE",
]
ScopeType = Literal[
    "PLATFORM", "ORGANIZATION", "WORKSPACE", "DOMAIN", "TEAM", "PLAYBOOK", "SKILL",
]
RuleStatus = Literal["draft", "active", "deprecated", "archived"]
VersionStatus = Literal["DRAFT", "PUBLISHED", "DEPRECATED", "ARCHIVED"]
ConflictStrategy = Literal["OVERRIDE", "MERGE", "ERROR", "WARN"]
ValidationStatus = Literal["unknown", "valid", "invalid", "warning"]

SCOPE_WEIGHTS: dict[str, int] = {
    "PLATFORM": 100,
    "ORGANIZATION": 200,
    "WORKSPACE": 300,
    "DOMAIN": 400,
    "TEAM": 500,
    "PLAYBOOK": 800,
    "SKILL": 900,
}


class RuleVersion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    rule_id: UUID
    semantic_version: str = "0.1.0"
    version_number: int = 1
    status: VersionStatus = "DRAFT"
    content_markdown: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    scope_type: ScopeType = "ORGANIZATION"
    scope_selector: dict[str, Any] = Field(default_factory=dict)
    scope_weight: int = 200
    priority: int = 50
    conflict_strategy: ConflictStrategy = "OVERRIDE"
    conflict_key: str = ""
    language: str = "ru"
    checksum: str = ""
    validation_status: ValidationStatus = "unknown"
    validation_report: dict[str, Any] = Field(default_factory=dict)
    revision: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RuleRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str = "default"
    key: str
    name: str
    description: str = ""
    category: RuleCategory = "STYLE"
    owner_team: str = "Platform"
    status: RuleStatus = "draft"
    current_published_version_id: Optional[UUID] = None
    current_draft_version_id: Optional[UUID] = None
    usage_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    revision: int = 1


class RuleCatalogItem(BaseModel):
    id: str
    key: str
    name: str
    description: str = ""
    category: str
    scope: str
    priority: int = 50
    version: Optional[str] = None
    status: str
    owner: str = ""
    usage_count: int = 0
    conflict_strategy: str = "OVERRIDE"


class RuleMetrics(BaseModel):
    published: int = 0
    drafts: int = 0
    conflicts: int = 0
    executions_30d: int = 0
    valid_pct: float = 100.0
    conflict_free_pct: float = 100.0
