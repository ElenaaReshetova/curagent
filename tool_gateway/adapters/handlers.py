"""Thin adapter handlers — no policy decisions (BND-004)."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def run_handler(
    handler: str,
    handler_type: str,
    inputs: dict[str, Any],
    context: dict[str, Any],
    binding: dict[str, Any],
) -> dict[str, Any]:
    """Route to system/script/mcp handler implementation."""
    if handler_type == "system":
        return await _system_handler(handler, inputs, context)
    if handler_type == "script":
        return await _script_handler(handler, inputs, context)
    if handler_type == "mcp":
        return await _mcp_handler(binding, inputs, context)
    return {"output": inputs, "status": "noop", "handler": handler}


async def _system_handler(handler: str, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    from src.orchestrator.classifier import classify_task
    from src.orchestrator.models import (
        ArtifactDraft,
        EvidenceBundle,
        ExecutionPlan,
        ExecutionStep,
        NormalizedTaskSpec,
        RoutingDecision,
    )

    spec_data = context.get("spec")
    if spec_data is None:
        raise ValueError("execution context missing spec")
    spec = spec_data if isinstance(spec_data, NormalizedTaskSpec) else NormalizedTaskSpec.model_validate(spec_data)

    routing = context.get("routing")
    if routing and not isinstance(routing, RoutingDecision):
        routing = RoutingDecision.model_validate(routing)

    plan = context.get("plan")
    evidence = context.get("evidence")
    artifact = context.get("artifact")

    if handler == "normalize":
        return {"output": spec.model_dump()}

    if handler == "classify":
        if routing is None:
            routing = classify_task(spec.description, spec.title)
        return {"routing": routing.model_dump(), "output": routing.model_dump()}

    if handler == "collect_evidence":
        from src.orchestrator.activities import collect_evidence
        if plan is None:
            plan = ExecutionPlan(
                task_id=spec.task_id,
                steps=[ExecutionStep(step_id="s1", skill="general", description=spec.description, done_criteria="done")],
            )
        elif not isinstance(plan, ExecutionPlan):
            plan = ExecutionPlan.model_validate(plan)
        bundle = await collect_evidence(spec, plan)
        return {"evidence": bundle.model_dump(), "output": bundle.model_dump()}

    if handler == "compress_context":
        brief_src = inputs.get("evidence") or (evidence.model_dump() if isinstance(evidence, EvidenceBundle) else evidence or {})
        items = brief_src.get("items", []) if isinstance(brief_src, dict) else []
        excerpt = "\n".join(i.get("excerpt", "")[:1500] for i in items[:5]) if items else spec.description[:4000]
        return {"evidence_brief": excerpt, "output": excerpt}

    if handler == "compliance":
        from src.orchestrator.validators import run_compliance_checks
        if artifact is None:
            art_data = inputs.get("artifact")
            if art_data is None:
                raise ValueError("Compliance requires artifact")
            artifact = ArtifactDraft.model_validate(art_data) if isinstance(art_data, dict) else art_data
        report = run_compliance_checks(artifact)
        return {"report": report.model_dump(), "output": report.model_dump()}

    if handler == "http_callback":
        from src.orchestrator.delivery import publish_via_callback
        if artifact is None:
            art_data = inputs.get("artifact")
            if art_data is None:
                raise ValueError("Publish requires artifact")
            artifact = ArtifactDraft.model_validate(art_data) if isinstance(art_data, dict) else art_data
        receipt = await publish_via_callback(spec, artifact)
        return {"receipt": receipt.model_dump(), "output": receipt.model_dump()}

    return {"output": inputs, "handler": handler}


async def _script_handler(handler: str, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if handler == "truncate_to_token_budget" or handler == "compress_context":
        return await _system_handler("compress_context", inputs, context)
    return {"output": inputs, "script": handler}


async def _mcp_handler(binding: dict[str, Any], inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    from src.tool_gateway.adapters.mcp_bridge import invoke_mcp
    server = binding.get("mcp_server", "")
    tool_name = binding.get("tool_name", "")
    result = await invoke_mcp(server, tool_name, inputs)
    return {"output": result, **result}
