"""Runtime Profiles domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


ProfileType = Literal[
    "DEVELOPMENT", "TEST", "PRODUCTION", "RESTRICTED", "BATCH",
    "INTERACTIVE", "HIGH_ACCURACY", "LOW_COST", "CUSTOM",
]
ProfileStatus = Literal["draft", "active", "deprecated", "disabled", "archived"]
VersionStatus = Literal["DRAFT", "ACTIVE", "DEPRECATED", "DISABLED", "ARCHIVED"]
ProviderType = Literal[
    "OPENAI_API", "AZURE_OPENAI", "ANTHROPIC_API", "GOOGLE_VERTEX_AI",
    "QWEN_CODE_CLI", "LOCAL_OLLAMA", "LOCAL_VLLM", "CUSTOM_HTTP", "CUSTOM_CLI",
    "GIGACHAT", "LM_STUDIO",
]
SandboxType = Literal["NONE", "PROCESS", "CONTAINER", "MICROVM", "REMOTE_RUNNER"]
SupervisionMode = Literal["AUTONOMOUS", "SUPERVISED", "STRICT"]
ValidationStatus = Literal["unknown", "valid", "invalid", "warning"]


class CapabilityPolicy(BaseModel):
    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)
    approval_required: list[str] = Field(default_factory=list)


class RuntimeProfileVersion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID
    semantic_version: str = "1.0.0"
    status: VersionStatus = "DRAFT"
    provider: ProviderType = "QWEN_CODE_CLI"
    model: str = "qwen3-coder"
    profile_type: ProfileType = "PRODUCTION"
    sandbox: SandboxType = "CONTAINER"
    network_policy: str = "ALLOW_CAPABILITY_GATEWAY_ONLY"
    supervision: SupervisionMode = "SUPERVISED"
    generation_config: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)
    sandbox_config: dict[str, Any] = Field(default_factory=dict)
    capabilities: CapabilityPolicy = Field(default_factory=CapabilityPolicy)
    fallback_profile_key: Optional[str] = None
    secret_ref: str = ""
    region: str = "ru-central"
    validation_status: ValidationStatus = "unknown"
    validation_report: dict[str, Any] = Field(default_factory=dict)
    revision: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RuntimeProfileRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str = "default"
    key: str
    name: str
    description: str = ""
    status: ProfileStatus = "draft"
    owner_team: str = "Platform"
    current_active_version_id: Optional[UUID] = None
    current_draft_version_id: Optional[UUID] = None
    runs_30d: int = 0
    health_status: Literal["HEALTHY", "DEGRADED", "UNHEALTHY"] = "HEALTHY"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    revision: int = 1


class RuntimeProfileCatalogItem(BaseModel):
    id: str
    key: str
    name: str
    description: str = ""
    profile_type: str
    provider: str
    model: str
    status: str
    version: Optional[str] = None
    sandbox: str = ""
    supervision: str = ""
    runs_30d: int = 0
    health_status: str = "HEALTHY"


class RuntimeProfileMetrics(BaseModel):
    active_profiles: int = 0
    healthy_providers: int = 0
    total_providers: int = 0
    runs_30d: int = 0
    cost_alerts: int = 0
