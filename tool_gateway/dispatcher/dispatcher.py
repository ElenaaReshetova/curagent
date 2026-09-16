"""Dispatcher — executes ToolCall via adapters, no auth (CAP-014, BND-003, REL-004)."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from src.tool_gateway.audit.store import get_decision, inputs_hash, new_execution_id, persist_execution
from src.tool_gateway.models.audit import ExecutionRecord
from src.tool_gateway.models.envelopes import ToolCall
from src.tool_gateway.registry.store import get_manifest

logger = logging.getLogger(__name__)


class DispatcherError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


def _verify_tool_call(tool_call: ToolCall) -> None:
    decision = get_decision(tool_call.decision_id)
    if decision is None:
        raise DispatcherError("INVALID_TOOL_CALL", "Missing decision record for tool_call", retryable=False)
    if not decision.accepted:
        raise DispatcherError("INVALID_TOOL_CALL", "Decision was not accepted", retryable=False)
    if decision.tool_call_id != tool_call.tool_call_id:
        raise DispatcherError("INVALID_TOOL_CALL", "tool_call_id mismatch with decision", retryable=False)


async def _run_handler(tool_call: ToolCall, execution_context: dict[str, Any]) -> dict[str, Any]:
    from src.tool_gateway.adapters.handlers import run_handler
    binding = tool_call.adapter_binding
    return await run_handler(
        handler=binding.get("handler", tool_call.capability_id),
        handler_type=binding.get("type", "system"),
        inputs=tool_call.normalized_inputs,
        context=execution_context,
        binding=binding,
    )


async def dispatch(
    tool_call: ToolCall,
    execution_context: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Returns (outputs, execution_record_id)."""
    _verify_tool_call(tool_call)
    start = time.monotonic()
    manifest = get_manifest(tool_call.capability_id)
    timeout = manifest.timeout_seconds if manifest else 120

    logger.info(
        "Dispatch tool_call=%s capability=%s timeout=%ss",
        tool_call.tool_call_id, tool_call.capability_id, timeout,
    )

    try:
        outputs = await asyncio.wait_for(
            _run_handler(tool_call, execution_context),
            timeout=timeout,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        exec_id = new_execution_id()
        persist_execution(ExecutionRecord(
            execution_record_id=exec_id,
            decision_id=tool_call.decision_id,
            tool_call_id=tool_call.tool_call_id,
            capability_id=tool_call.capability_id,
            trace_id=tool_call.trace_id,
            success=True,
            outputs_hash=inputs_hash(outputs),
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=duration_ms,
        ))
        return outputs, exec_id
    except DispatcherError:
        raise
    except asyncio.TimeoutError as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        exec_id = new_execution_id()
        persist_execution(ExecutionRecord(
            execution_record_id=exec_id,
            decision_id=tool_call.decision_id,
            tool_call_id=tool_call.tool_call_id,
            capability_id=tool_call.capability_id,
            trace_id=tool_call.trace_id,
            success=False,
            error_code="TIMEOUT",
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=duration_ms,
        ))
        raise DispatcherError("ADAPTER_ERROR", f"Dispatch timeout after {timeout}s", retryable=True) from e
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        exec_id = new_execution_id()
        persist_execution(ExecutionRecord(
            execution_record_id=exec_id,
            decision_id=tool_call.decision_id,
            tool_call_id=tool_call.tool_call_id,
            capability_id=tool_call.capability_id,
            trace_id=tool_call.trace_id,
            success=False,
            error_code="ADAPTER_ERROR",
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=duration_ms,
        ))
        logger.exception("Dispatch failed tool_call=%s", tool_call.tool_call_id)
        raise DispatcherError("ADAPTER_ERROR", str(e), retryable=True) from e
