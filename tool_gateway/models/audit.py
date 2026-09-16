"""Audit models (AUD-001, RES-020)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class DecisionRecord(BaseModel):
    decision_id: str
    request_id: str
    trace_id: str
    tenant_id: str
    capability_id: str
    caller_identity: dict[str, Any]
    inputs_hash: str
    accepted: bool
    denial_code: Optional[str] = None
    manifest_version: int
    policy_version: str
    resolver_version: str
    timestamp: str
    tool_call_id: Optional[str] = None
    explainability: dict[str, Any] = Field(default_factory=dict)
    registry_snapshot_id: str = ""
    reversal_metadata: Optional[dict[str, Any]] = None


class ExecutionRecord(BaseModel):
    execution_record_id: str
    decision_id: str
    tool_call_id: str
    capability_id: str
    trace_id: str
    success: bool
    outputs_hash: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: str
    duration_ms: Optional[int] = None
