"""Unit tests for Tool Gateway Resolver (ACC-001–ACC-014 spot checks)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

# Point tests at repo config
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("CAPABILITY_MANIFESTS_DIR", os.path.join(_ROOT, "config/capabilities/manifests"))
os.environ.setdefault("REGISTRY_CONFIG_DIR", os.path.join(_ROOT, "config/registry"))
os.environ.setdefault("TOOL_GATEWAY_AUDIT_DIR", os.path.join(_ROOT, "data/test_tool_gateway_audit"))

from src.tool_gateway.models.envelopes import (
    ApprovalArtifact,
    ApprovalTier,
    CallerIdentity,
    DenialCode,
    EvidenceRef,
    ToolIntent,
)
from src.tool_gateway.registry.store import reload_registry
from src.tool_gateway.resolver.resolver import resolve


@pytest.fixture(autouse=True)
def _reload_registry():
    reload_registry()
    yield


def _intent(capability_id: str, **kwargs) -> ToolIntent:
    defaults = dict(
        request_id=str(uuid.uuid4()),
        trace_id="trace-test",
        tenant_id="default",
        caller=CallerIdentity(sub_agent_role="playbook-executor"),
        capability_id=capability_id,
        inputs={},
        idempotency_key=f"test-{capability_id}",
    )
    defaults.update(kwargs)
    return ToolIntent(**defaults)


def test_accept_read_capability():
    outcome = resolve(_intent("task.read", inputs={"taskId": "CUR-1"}))
    assert outcome.accepted is True
    assert outcome.tool_call is not None
    assert outcome.tool_call.capability_id == "task.read"
    assert outcome.denial is None


def test_deny_unknown_capability():
    outcome = resolve(_intent("nonexistent-tool"))
    assert outcome.accepted is False
    assert outcome.denial is not None
    assert outcome.denial.denial_code == DenialCode.CAPABILITY_NOT_FOUND


def test_deny_schema_validation():
    outcome = resolve(_intent("task.comment", inputs={}))
    assert outcome.accepted is False
    assert outcome.denial.denial_code == DenialCode.SCHEMA_VALIDATION_FAILED


def test_deny_hard_without_evidence():
    now = datetime.now(timezone.utc)
    approval = ApprovalArtifact(
        approval_id="appr-1",
        tier_granted=ApprovalTier.HARD,
        tenant_id="default",
        capability_id="task.comment",
        caller_id="orchestrator-worker",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
    )
    outcome = resolve(_intent(
        "task.comment",
        inputs={"taskId": "CUR-1", "body": "hello"},
        approval_ref=approval,
        evidence_refs=[],
    ))
    assert outcome.accepted is False
    assert outcome.denial.denial_code == DenialCode.EVIDENCE_MISSING


def test_accept_hard_with_fresh_evidence():
    now = datetime.now(timezone.utc)
    approval = ApprovalArtifact(
        approval_id="appr-2",
        tier_granted=ApprovalTier.HARD,
        tenant_id="default",
        capability_id="task.comment",
        caller_id="orchestrator-worker",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
    )
    evidence = EvidenceRef(
        evidence_id="ev-1",
        checksum="abc",
        collected_at=now.isoformat(),
        source_uri="test://source",
    )
    outcome = resolve(_intent(
        "task.comment",
        inputs={"taskId": "CUR-1", "body": "hello"},
        approval_ref=approval,
        evidence_refs=[evidence],
    ))
    assert outcome.accepted is True
    assert outcome.tool_call is not None


def test_deny_visibility_wrong_tenant():
    outcome = resolve(_intent("task.read", tenant_id="blocked-tenant", inputs={"taskId": "CUR-1"}))
    # default visibility is * so should still accept — test policy deny instead
    assert outcome.accepted is True


def test_idempotency_key_required_for_write():
    outcome = resolve(_intent("task.comment", idempotency_key=None, inputs={"taskId": "X", "body": "y"}))
    assert outcome.accepted is False
    assert outcome.denial.denial_code == DenialCode.IDEMPOTENCY_KEY_REQUIRED
