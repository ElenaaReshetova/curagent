"""Tool Gateway orchestration (CAP-011–CAP-026)."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from src.tool_gateway.audit.store import cache_result, get_cached_result
from src.tool_gateway.dispatcher.dispatcher import DispatcherError, dispatch
from src.tool_gateway.models.envelopes import InvokeResponse, NormalizedResult, ToolIntent
from src.tool_gateway.registry.store import ensure_loaded, get_manifest, reload_registry
from src.tool_gateway.resolver.resolver import resolve
from src.tool_gateway import telemetry

logger = logging.getLogger(__name__)


class ToolGateway:
    """Single entry point for tool invocation (SEC-002)."""

    def __init__(self) -> None:
        ensure_loaded()

    def reload(self) -> str:
        return reload_registry()

    async def invoke(
        self,
        intent: ToolIntent,
        execution_context: Optional[dict[str, Any]] = None,
    ) -> InvokeResponse:
        ctx = execution_context or {}
        manifest = get_manifest(intent.capability_id, intent.manifest_version)

        telemetry.inc("gateway_invoke_total")
        if manifest and intent.idempotency_key and manifest.idempotent:
            cached = get_cached_result(intent.tenant_id, intent.capability_id, intent.idempotency_key)
            if cached:
                telemetry.inc("idempotency_cache_hit_total")
                logger.info("Idempotent cache hit %s", intent.idempotency_key)
                return InvokeResponse(success=True, result=cached)

        outcome = resolve(intent)
        if not outcome.accepted or outcome.tool_call is None:
            if outcome.denial:
                telemetry.inc_deny(outcome.denial.denial_code.value)
            return InvokeResponse(success=False, denial=outcome.denial)

        tool_call = outcome.tool_call
        telemetry.inc("resolution_accept_total")

        if manifest and intent.idempotency_key and manifest.idempotency_required:
            cached = get_cached_result(intent.tenant_id, intent.capability_id, intent.idempotency_key)
            if cached:
                telemetry.inc("idempotency_cache_hit_total")
                return InvokeResponse(success=True, result=cached)

        try:
            outputs, exec_id = await dispatch(tool_call, ctx)
        except DispatcherError as e:
            from src.tool_gateway.models.envelopes import Denial, DenialCode
            code = DenialCode.INTEGRITY_CHECK_FAILED if e.code == "INVALID_TOOL_CALL" else DenialCode.EXECUTION_FAILED
            denial = Denial(
                denial_code=code,
                message=e.message,
                details={"adapter_error": e.code, "retryable": e.retryable},
                retryable=e.retryable,
                decision_id=outcome.decision_id,
            )
            return InvokeResponse(success=False, denial=denial)

        result = NormalizedResult(
            request_id=intent.request_id,
            decision_id=outcome.decision_id,
            tool_call_id=tool_call.tool_call_id,
            capability_id=intent.capability_id,
            trace_id=intent.trace_id,
            outputs=outputs,
            execution_record_id=exec_id,
        )

        telemetry.inc("dispatch_success_total")

        if intent.idempotency_key and manifest and (manifest.idempotent or manifest.idempotency_required):
            cache_result(intent.tenant_id, intent.capability_id, intent.idempotency_key, result)

        return InvokeResponse(success=True, result=result)


def build_intent_from_legacy(
    tool_id: str,
    trace_id: str,
    task_id: str,
    tenant_id: str = "default",
    inputs: Optional[dict] = None,
    caller_role: str = "playbook-executor",
    skill_id: Optional[str] = None,
    playbook_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> ToolIntent:
    """Bridge legacy tool_id → ToolIntent for orchestrator activities."""
    from src.tool_gateway.models.envelopes import CallerIdentity
    return ToolIntent(
        request_id=str(uuid.uuid4()),
        trace_id=trace_id,
        tenant_id=tenant_id,
        caller=CallerIdentity(
            agent_id="orchestrator-worker",
            sub_agent_role=caller_role,
            skill_id=skill_id,
            playbook_run_id=task_id,
        ),
        capability_id=tool_id,
        inputs=inputs or {},
        task_id=task_id,
        playbook_id=playbook_id,
        idempotency_key=idempotency_key or f"{task_id}:{tool_id}",
    )


_gateway: Optional[ToolGateway] = None


def get_gateway() -> ToolGateway:
    global _gateway
    if _gateway is None:
        _gateway = ToolGateway()
    return _gateway
