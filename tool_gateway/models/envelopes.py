"""Tool Gateway typed envelopes (CAP-011, CAP-012, RES-017)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ApprovalTier(str, Enum):
    NONE = "none"
    SOFT = "soft"
    HARD = "hard"
    DESTRUCTIVE = "destructive"


class SideEffectClass(str, Enum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    EXTERNAL_PUBLISH = "external_publish"


class ManifestStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


class DenialCode(str, Enum):
    CAPABILITY_NOT_FOUND = "CAPABILITY_NOT_FOUND"
    CAPABILITY_NOT_VISIBLE = "CAPABILITY_NOT_VISIBLE"
    CAPABILITY_DISABLED = "CAPABILITY_DISABLED"
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
    EXECUTION_MODE_INCOMPATIBLE = "EXECUTION_MODE_INCOMPATIBLE"
    POLICY_DENIED = "POLICY_DENIED"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    APPROVAL_MISSING = "APPROVAL_MISSING"
    APPROVAL_INVALID = "APPROVAL_INVALID"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    REVERSAL_CONTRACT_MISSING = "REVERSAL_CONTRACT_MISSING"
    IDEMPOTENCY_KEY_REQUIRED = "IDEMPOTENCY_KEY_REQUIRED"
    REGISTRY_UNAVAILABLE = "REGISTRY_UNAVAILABLE"
    INTEGRITY_CHECK_FAILED = "INTEGRITY_CHECK_FAILED"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class CallerIdentity(BaseModel):
    agent_id: str = "orchestrator-worker"
    sub_agent_role: str = "skill-executor"
    service_account: Optional[str] = None
    playbook_run_id: Optional[str] = None
    skill_id: Optional[str] = None


class ApprovalArtifact(BaseModel):
    approval_id: str
    tier_granted: ApprovalTier
    tenant_id: str
    capability_id: str
    caller_id: str
    issued_at: str
    expires_at: str
    signature: Optional[str] = None


class EvidenceRef(BaseModel):
    evidence_id: str
    checksum: str
    collected_at: str
    source_uri: str = ""


class ToolIntent(BaseModel):
    """Agent-proposed tool invocation (CAP-011)."""
    request_id: str
    trace_id: str
    tenant_id: str = "default"
    caller: CallerIdentity = Field(default_factory=CallerIdentity)
    capability_id: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    idempotency_key: Optional[str] = None
    approval_ref: Optional[ApprovalArtifact] = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    execution_mode: str = "production"
    manifest_version: Optional[int] = None
    task_id: Optional[str] = None
    playbook_id: Optional[str] = None


class ToolCall(BaseModel):
    """Canonical executable command (RES-016)."""
    tool_call_id: str
    decision_id: str
    capability_id: str
    manifest_version: int
    normalized_inputs: dict[str, Any]
    effective_approval_mode: ApprovalTier
    adapter_binding: dict[str, Any]
    idempotency_key: Optional[str] = None
    trace_id: str
    policy_version: str
    tenant_id: str


class Denial(BaseModel):
    """Typed refusal (RES-017)."""
    denial_code: DenialCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    retry_after_ms: Optional[int] = None
    policy_version: str = "1"
    resolver_version: str = "1.0.0"
    decision_id: str
    explainability: dict[str, Any] = Field(default_factory=dict)


class NormalizedResult(BaseModel):
    """Gateway response after successful dispatch (CAP-013)."""
    request_id: str
    decision_id: str
    tool_call_id: str
    capability_id: str
    trace_id: str
    outputs: dict[str, Any]
    cached: bool = False
    execution_record_id: Optional[str] = None


class ResolutionOutcome(BaseModel):
    """Resolver output: ACCEPT or DENY."""
    accepted: bool
    tool_call: Optional[ToolCall] = None
    denial: Optional[Denial] = None
    decision_id: str


class InvokeResponse(BaseModel):
    """Gateway API response to caller."""
    success: bool
    result: Optional[NormalizedResult] = None
    denial: Optional[Denial] = None
