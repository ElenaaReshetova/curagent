"""Skills subsystem domain models (versioned packages)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


SkillType = Literal["CORE", "CORPORATE", "TEAM", "IMPORTED"]
SkillStatus = Literal["draft", "active", "deprecated", "archived"]
VersionStatus = Literal["DRAFT", "VALIDATING", "PUBLISHED", "DEPRECATED", "ARCHIVED"]
ValidationStatus = Literal["unknown", "valid", "invalid", "warning"]
SkillFileKind = Literal["file", "folder"]

# Platform / org catalog skills — packages are sealed; customise via inheritance only.
IMMUTABLE_SKILL_TYPES = frozenset({"CORE", "CORPORATE"})


def skill_is_immutable(skill_type: str) -> bool:
    return skill_type.upper() in IMMUTABLE_SKILL_TYPES


class SkillFile(BaseModel):
    path: str
    media_type: str = "text/plain"
    content_text: str = ""
    content_hash: str = ""
    kind: SkillFileKind = "file"


class SkillTestCase(BaseModel):
    key: str
    name: str
    mode: Literal["SANDBOX", "MOCK_CAPABILITIES", "CONTRACT"] = "CONTRACT"
    status: Literal["PASSED", "FAILED", "MISSING", "PENDING"] = "PENDING"
    duration_s: Optional[float] = None


class SkillBindingRef(BaseModel):
    scope: str
    target: str
    priority: int = 100
    status: str = "ACTIVE"


class SkillVersion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    skill_id: UUID
    semantic_version: str = "0.1.0"
    status: VersionStatus = "DRAFT"
    skill_markdown: str = ""
    manifest: dict[str, Any] = Field(default_factory=dict)
    package_checksum: str = ""
    runtime_type: str = "qwen-code-cli"
    interface_key: str = ""
    input_contract_key: str = ""
    output_contract_key: str = ""
    allowed_capabilities: list[str] = Field(default_factory=list)
    files: list[SkillFile] = Field(default_factory=list)
    test_cases: list[SkillTestCase] = Field(default_factory=list)
    validation_status: ValidationStatus = "unknown"
    validation_report: dict[str, Any] = Field(default_factory=dict)
    revision: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SkillRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str = "default"
    key: str
    name: str
    description: str = ""
    skill_type: SkillType = "TEAM"
    status: SkillStatus = "draft"
    owner_team: str = "Platform"
    parent_skill_id: Optional[UUID] = None
    parent_version_id: Optional[UUID] = None
    current_published_version_id: Optional[UUID] = None
    current_draft_version_id: Optional[UUID] = None
    runs_30d: int = 0
    success_rate: float = 0.0
    bindings: list[SkillBindingRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    revision: int = 1

    @property
    def immutable(self) -> bool:
        return skill_is_immutable(self.skill_type)


class SkillCatalogItem(BaseModel):
    id: str
    key: str
    name: str
    description: str = ""
    skill_type: str
    status: str
    owner: str
    version: Optional[str] = None
    interfaces: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    runtime_type: str = ""
    validation_status: str = "unknown"
    runs_30d: int = 0
    immutable: bool = False
    parent_skill_id: Optional[str] = None
    parent_key: Optional[str] = None


class SkillMetrics(BaseModel):
    skills: int = 0
    published_versions: int = 0
    interfaces: int = 0
    validation_pass_pct: float = 100.0
    corporate_skills: int = 0
