"""Pre-execution Resolver — refusal-first (RES-001–RES-023)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from src.tool_gateway.audit.store import inputs_hash, new_decision_id, new_tool_call_id, persist_decision
from src.tool_gateway.models.audit import DecisionRecord
from src.tool_gateway.models.envelopes import (
    ApprovalTier,
    Denial,
    DenialCode,
    ResolutionOutcome,
    SideEffectClass,
    ToolCall,
    ToolIntent,
)
from src.tool_gateway.models.manifest import CapabilityManifest
from src.tool_gateway.policy.evaluator import check_policy, check_visibility, get_policy_version
from src.tool_gateway.registry.store import get_manifest, get_snapshot_id, is_registry_available

logger = logging.getLogger(__name__)

RESOLVER_VERSION = "1.0.0"


def _deny(
    intent: ToolIntent,
    code: DenialCode,
    message: str,
    details: dict[str, Any],
    retryable: bool = False,
    retry_after_ms: Optional[int] = None,
    manifest: Optional[CapabilityManifest] = None,
    explainability: Optional[dict[str, Any]] = None,
) -> ResolutionOutcome:
    decision_id = new_decision_id()
    policy_version = get_policy_version()
    denial = Denial(
        denial_code=code,
        message=message,
        details=details,
        retryable=retryable,
        retry_after_ms=retry_after_ms,
        policy_version=policy_version,
        resolver_version=RESOLVER_VERSION,
        decision_id=decision_id,
        explainability=explainability or {"stage": code.value, **details},
    )
    record = DecisionRecord(
        decision_id=decision_id,
        request_id=intent.request_id,
        trace_id=intent.trace_id,
        tenant_id=intent.tenant_id,
        capability_id=intent.capability_id,
        caller_identity=intent.caller.model_dump(),
        inputs_hash=inputs_hash(intent.inputs),
        accepted=False,
        denial_code=code.value,
        manifest_version=manifest.manifest_version if manifest else 0,
        policy_version=policy_version,
        resolver_version=RESOLVER_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        explainability=denial.explainability,
        registry_snapshot_id=get_snapshot_id(),
    )
    persist_decision(record)
    logger.info("Resolver DENY %s code=%s request=%s", decision_id, code.value, intent.request_id)
    return ResolutionOutcome(accepted=False, denial=denial, decision_id=decision_id)


def _validate_schema(manifest: CapabilityManifest, inputs: dict[str, Any]) -> tuple[bool, list[str]]:
    """RES-008: validate required fields + basic types from manifest."""
    errors: list[str] = []
    for field in manifest.required_input_fields:
        if field not in inputs or inputs[field] is None:
            errors.append(f"Missing required field: {field}")
    schema = manifest.input_schema
    if schema.get("type") == "object" and "properties" in schema:
        for key, spec in schema["properties"].items():
            if key in inputs and spec.get("type") == "string" and not isinstance(inputs[key], str):
                errors.append(f"Field {key} must be string")
    return len(errors) == 0, errors


def _validate_approval(intent: ToolIntent, manifest: CapabilityManifest) -> tuple[bool, Optional[DenialCode], dict[str, Any]]:
    """RES-010, RES-011, SEC-005."""
    tier = manifest.approval_tier
    if tier == ApprovalTier.NONE:
        return True, None, {}

    approval = intent.approval_ref
    if approval is None:
        return False, DenialCode.APPROVAL_MISSING, {"required_tier": tier.value}

    if approval.tenant_id != intent.tenant_id:
        return False, DenialCode.TENANT_MISMATCH, {"reason": "approval_tenant_mismatch"}

    if approval.capability_id != intent.capability_id:
        return False, DenialCode.APPROVAL_INVALID, {"reason": "capability_mismatch"}

    tier_order = [ApprovalTier.NONE, ApprovalTier.SOFT, ApprovalTier.HARD, ApprovalTier.DESTRUCTIVE]
    if tier_order.index(approval.tier_granted) < tier_order.index(tier):
        return False, DenialCode.APPROVAL_INVALID, {"required": tier.value, "granted": approval.tier_granted.value}

    try:
        expires = datetime.fromisoformat(approval.expires_at.replace("Z", "+00:00"))
        if expires < datetime.now(timezone.utc):
            return False, DenialCode.APPROVAL_EXPIRED, {"expires_at": approval.expires_at}
    except ValueError:
        return False, DenialCode.APPROVAL_INVALID, {"reason": "invalid_expires_at"}

    return True, None, {}


def _validate_evidence(intent: ToolIntent, manifest: CapabilityManifest) -> tuple[bool, Optional[DenialCode], dict[str, Any]]:
    """RES-012, RES-013, RES-014, SEC-006."""
    tier = manifest.approval_tier
    if tier not in (ApprovalTier.HARD, ApprovalTier.DESTRUCTIVE):
        return True, None, {}

    if not intent.evidence_refs:
        return False, DenialCode.EVIDENCE_MISSING, {"required_for_tier": tier.value}

    now = datetime.now(timezone.utc)
    max_age = manifest.evidence_max_age_seconds
    for ref in intent.evidence_refs:
        try:
            collected = datetime.fromisoformat(ref.collected_at.replace("Z", "+00:00"))
            age = (now - collected).total_seconds()
            if age > max_age:
                return False, DenialCode.EVIDENCE_STALE, {
                    "evidence_id": ref.evidence_id,
                    "age_seconds": age,
                    "max_age_seconds": max_age,
                }
        except ValueError:
            return False, DenialCode.EVIDENCE_MISSING, {"reason": "invalid_collected_at", "evidence_id": ref.evidence_id}

    return True, None, {}


def _validate_reversal(manifest: CapabilityManifest) -> tuple[bool, Optional[DenialCode], dict[str, Any]]:
    """RES-015."""
    if manifest.approval_tier != ApprovalTier.DESTRUCTIVE:
        return True, None, {}
    rev = manifest.reversal
    if manifest.side_effect_class == SideEffectClass.DESTRUCTIVE and not rev.reversible and not rev.reversal_capability_id:
        return False, DenialCode.REVERSAL_CONTRACT_MISSING, {"capability_id": manifest.capability_id}
    return True, None, {}


def resolve(intent: ToolIntent) -> ResolutionOutcome:
    """Main resolution entry point (RES-001–004)."""
    if not is_registry_available():
        return _deny(
            intent, DenialCode.REGISTRY_UNAVAILABLE,
            "Capability registry unavailable",
            {"snapshot": get_snapshot_id()},
            retryable=True, retry_after_ms=5000,
        )

    manifest = get_manifest(intent.capability_id, intent.manifest_version)
    if manifest is None:
        return _deny(
            intent, DenialCode.CAPABILITY_NOT_FOUND,
            f"Capability not found: {intent.capability_id}",
            {"capability_id": intent.capability_id},
        )

    from src.tool_gateway.models.envelopes import ManifestStatus
    if manifest.status.value == "disabled":
        return _deny(intent, DenialCode.CAPABILITY_DISABLED, "Capability disabled", {}, manifest=manifest)
    if manifest.status.value == "deprecated" and intent.execution_mode == "production":
        return _deny(
            intent, DenialCode.EXECUTION_MODE_INCOMPATIBLE,
            "Deprecated capability not allowed in production mode",
            {"status": manifest.status.value},
            manifest=manifest,
        )
    if manifest.status.value == "draft" and intent.execution_mode == "production":
        return _deny(
            intent, DenialCode.EXECUTION_MODE_INCOMPATIBLE,
            "Draft capability not allowed in production mode",
            {"status": manifest.status.value},
            manifest=manifest,
        )

    ok, code, details = check_visibility(manifest, intent)
    if not ok and code:
        return _deny(intent, code, "Capability not visible to caller", details, manifest=manifest)

    ok, code, details = check_policy(manifest, intent)
    if not ok and code:
        return _deny(intent, code, "Policy denied", details, manifest=manifest)

    if manifest.idempotency_required and not intent.idempotency_key:
        return _deny(
            intent, DenialCode.IDEMPOTENCY_KEY_REQUIRED,
            "Idempotency key required for this capability",
            {"side_effect": manifest.side_effect_class.value},
            manifest=manifest,
        )

    valid, schema_errors = _validate_schema(manifest, intent.inputs)
    if not valid:
        return _deny(
            intent, DenialCode.SCHEMA_VALIDATION_FAILED,
            "Input schema validation failed",
            {"errors": schema_errors},
            retryable=False,
            manifest=manifest,
            explainability={"failed_check": "schema", "errors": schema_errors},
        )

    ok, code, details = _validate_approval(intent, manifest)
    if not ok and code:
        return _deny(intent, code, "Approval validation failed", details, manifest=manifest)

    ok, code, details = _validate_evidence(intent, manifest)
    if not ok and code:
        return _deny(intent, code, "Evidence validation failed", details, manifest=manifest)

    ok, code, details = _validate_reversal(manifest)
    if not ok and code:
        return _deny(intent, code, "Reversal contract missing", details, manifest=manifest)

    # ACCEPT — RES-016: pick ToolImplementation, bind adapter for Dispatcher
    decision_id = new_decision_id()
    tool_call_id = new_tool_call_id()
    policy_version = get_policy_version()

    ctx = {
        "task_source": intent.inputs.get("task_source") or intent.inputs.get("source"),
        "project": intent.inputs.get("project"),
        "workspace": intent.inputs.get("workspace"),
        "taskSources": [intent.inputs.get("task_source") or intent.inputs.get("source")]
        if (intent.inputs.get("task_source") or intent.inputs.get("source"))
        else [],
        "projects": [intent.inputs["project"]] if intent.inputs.get("project") else [],
    }
    allowed_servers = list(getattr(intent.caller, "allowed_mcp_servers", None) or [])
    impl = manifest.resolve_implementation(
        allowed_servers=allowed_servers or None,
        context={k: v for k, v in ctx.items() if v},
    )
    if impl is None and not manifest.implementations:
        binding = manifest.adapter_binding
    elif impl is None:
        return _deny(
            intent,
            DenialCode.CAPABILITY_NOT_FOUND,
            f"No approved implementation for {manifest.capability_id}",
            {"capability_id": manifest.capability_id, "stage": "implementation_resolve"},
            manifest=manifest,
        )
    else:
        binding = impl.to_adapter_binding()

    tool_call = ToolCall(
        tool_call_id=tool_call_id,
        decision_id=decision_id,
        capability_id=manifest.capability_id,
        manifest_version=manifest.manifest_version,
        normalized_inputs=dict(intent.inputs),
        effective_approval_mode=manifest.approval_tier,
        adapter_binding=binding.model_dump(),
        idempotency_key=intent.idempotency_key,
        trace_id=intent.trace_id,
        policy_version=policy_version,
        tenant_id=intent.tenant_id,
    )

    reversal_meta = None
    if manifest.approval_tier == ApprovalTier.DESTRUCTIVE:
        reversal_meta = manifest.reversal.model_dump()

    record = DecisionRecord(
        decision_id=decision_id,
        request_id=intent.request_id,
        trace_id=intent.trace_id,
        tenant_id=intent.tenant_id,
        capability_id=manifest.capability_id,
        caller_identity=intent.caller.model_dump(),
        inputs_hash=inputs_hash(intent.inputs),
        accepted=True,
        manifest_version=manifest.manifest_version,
        policy_version=policy_version,
        resolver_version=RESOLVER_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        tool_call_id=tool_call_id,
        explainability={"snapshot_id": get_snapshot_id()},
        registry_snapshot_id=get_snapshot_id(),
        reversal_metadata=reversal_meta,
    )
    persist_decision(record)
    logger.info("Resolver ACCEPT %s capability=%s", decision_id, manifest.capability_id)

    return ResolutionOutcome(accepted=True, tool_call=tool_call, decision_id=decision_id)
