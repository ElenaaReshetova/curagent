"""Configurable pipeline step runner — graph-aware playbook execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

from src.orchestrator.models import (
    ArtifactDraft,
    NormalizedTaskSpec,
    RoutingDecision,
    TaskStatus,
    VerificationFinding,
    VerificationReport,
    VerificationStatus,
    WorkflowInput,
    WorkflowResult,
)
from src.orchestrator.workflow_config.models import StepType, WorkflowSettings, WorkflowStepConfig, WorkflowTemplate
from src.orchestrator.routing_graph import (
    is_classify_step as _is_classify_step,
    is_skill_router as _is_skill_router,
    next_step_id as _next_step_id,
    resolve_skill_id as _resolve_skill_id,
)


def _artifact_content(artifact: Any) -> str:
    """Read artifact body whether Temporal returned a model or a plain dict."""
    if artifact is None:
        return ""
    if isinstance(artifact, dict):
        return str(artifact.get("content") or "")
    content = getattr(artifact, "content", None)
    if content is None and hasattr(artifact, "model_dump"):
        try:
            dumped = artifact.model_dump()
            if isinstance(dumped, dict):
                return str(dumped.get("content") or "")
        except Exception:
            pass
    return str(content or "")


def _coerce_artifact(value: Any) -> Any:
    """Normalize activity / step-output payloads into ArtifactDraft when possible."""
    if value is None:
        return None
    if isinstance(value, ArtifactDraft):
        return value
    if isinstance(value, dict):
        if "content" in value or "artifact_id" in value:
            try:
                return ArtifactDraft.model_validate(value)
            except Exception:
                return value
        nested = value.get("artifact")
        if isinstance(nested, dict):
            try:
                return ArtifactDraft.model_validate(nested)
            except Exception:
                return nested
    return value


def _resolve_artifact_preview(ctx: "PipelineContext", *, limit: int = 8000) -> str:
    """Best-effort artifact text for human checkpoints."""
    candidates: list[Any] = [ctx.artifact]
    stored = ctx.step_outputs.get("artifact")
    if stored is not None:
        candidates.append(stored)
    # Prefer newest skill-step outputs that embed an artifact payload.
    for step_id, payload in reversed(list(ctx.step_outputs.items())):
        if step_id in {"artifact", "output"}:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("artifact"), dict):
            candidates.append(payload["artifact"])
    for candidate in candidates:
        text = _artifact_content(candidate).strip()
        if text:
            return text[:limit]
    return ""


with workflow.unsafe.imports_passed_through():
    from src.orchestrator.activities import (
        check_compliance_activity,
        classify_task_activity,
        collect_evidence,
        execute_skill_activity,
        execute_skill_step_activity,
        execute_tool_activity,
        normalize_task,
        notify_escalation_activity,
        open_human_checkpoint_activity,
        plan_task,
        publish_artifact_activity,
        record_execution_progress_activity,
        verify_artifact_activity,
    )

_DEFAULT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=2,
)

_EXECUTE_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_attempts=1,
)

_LLM_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=3),
    maximum_attempts=1,
)


@dataclass
class PipelineContext:
    raw: WorkflowInput
    trace_id: str
    spec: Any = None
    routing: Any = None
    plan: Any = None
    evidence: Any = None
    artifact: Any = None
    artifact_version: int = 1
    rework_fixes: list[str] = field(default_factory=list)
    receipt: Any = None
    status: TaskStatus = TaskStatus.NEW
    error: Optional[str] = None
    halted: bool = False
    step_outputs: dict[str, Any] = field(default_factory=dict)
    last_decision: str = "yes"
    last_verification: Any = None
    rework_count: int = 0

    def to_result(self) -> WorkflowResult:
        return WorkflowResult(
            task_id=self.raw.task_id,
            trace_id=self.trace_id,
            status=self.status,
            artifact=self.artifact,
            receipt=self.receipt,
            error=self.error,
        )


def _timeout(step: WorkflowStepConfig, settings: WorkflowSettings) -> timedelta:
    minutes = step.config.get("timeout_minutes", settings.default_timeout_minutes)
    return timedelta(minutes=float(minutes))


def _resolve_inputs(step: WorkflowStepConfig, ctx: PipelineContext) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    for m in step.input_mappings:
        src = ctx.step_outputs.get(m.source_step, {})
        if isinstance(src, dict):
            inputs[m.param] = src.get(m.source_output, src.get("output"))
        else:
            inputs[m.param] = src
    return inputs


def _store_output(ctx: PipelineContext, step: WorkflowStepConfig, result: dict) -> None:
    ctx.step_outputs[step.id] = result
    key = step.output_key or "output"
    if key in result:
        ctx.step_outputs[key] = result[key]


def _entry_step_id(template: WorkflowTemplate) -> str:
    for s in template.steps:
        if s.enabled and StepType(s.type) == StepType.START:
            return s.id
    incoming = {e.to_step for e in template.edges}
    for s in template.steps:
        if s.enabled and s.id not in incoming:
            return s.id
    return template.steps[0].id if template.steps else ""


async def _ensure_spec(ctx: PipelineContext, settings: WorkflowSettings) -> None:
    if ctx.spec is None:
        ctx.spec = await workflow.execute_activity(
            normalize_task,
            ctx.raw,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )


async def _run_script(
    step: WorkflowStepConfig,
    ctx: PipelineContext,
    settings: WorkflowSettings,
    inputs: dict,
) -> PipelineContext:
    """Deterministic playbook scripts — not Capabilities (MCP APIs)."""
    handler = (
        step.script_id
        or step.system_handler
        or step.config.get("handler")
        or step.tool_id
        or ""
    )
    handler = str(handler).replace("-", "_")
    await _ensure_spec(ctx, settings)

    if handler in ("collect_evidence",):
        if ctx.routing is None:
            ctx.routing = await workflow.execute_activity(
                classify_task_activity,
                ctx.spec,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=_DEFAULT_RETRY,
            )
        plan = ctx.plan
        if plan is None:
            plan = await workflow.execute_activity(
                plan_task,
                args=[ctx.spec, ctx.routing],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=_DEFAULT_RETRY,
            )
            ctx.plan = plan
        bundle = await workflow.execute_activity(
            collect_evidence,
            args=[ctx.spec, plan],
            start_to_close_timeout=_timeout(step, settings),
            retry_policy=_DEFAULT_RETRY,
        )
        ctx.evidence = bundle
        _store_output(ctx, step, {"evidence": bundle.model_dump(), "output": bundle.model_dump()})
        return ctx

    if handler in ("compress_context",):
        brief_src = inputs.get("evidence") or (ctx.evidence.model_dump() if ctx.evidence else {})
        items = brief_src.get("items", []) if isinstance(brief_src, dict) else []
        excerpt = (
            "\n".join(i.get("excerpt", "")[:1500] for i in items[:5])
            if items
            else (ctx.spec.description[:4000] if ctx.spec else "")
        )
        _store_output(ctx, step, {"evidence_brief": excerpt, "output": excerpt})
        return ctx

    if handler in ("verify", "validation"):
        art = _coerce_artifact(ctx.artifact)
        if inputs.get("artifact"):
            art = _coerce_artifact(inputs["artifact"])
        if art is None:
            ctx.error = "Script verify missing artifact"
            ctx.halted = True
            return ctx
        report = await workflow.execute_activity(
            verify_artifact_activity,
            args=[ctx.spec, art],
            start_to_close_timeout=_timeout(step, settings),
            retry_policy=_LLM_RETRY,
        )
        ctx.last_verification = report
        ctx.artifact = art
        _store_output(ctx, step, {"verification_report": report.model_dump(), "output": report.model_dump()})
        ctx.status = TaskStatus.UNDER_REVIEW
        return ctx

    if handler in ("compliance",):
        if ctx.artifact is None:
            ctx.error = "Compliance script missing artifact"
            ctx.halted = True
            return ctx
        report = await workflow.execute_activity(
            check_compliance_activity,
            args=[ctx.artifact],
            start_to_close_timeout=_timeout(step, settings),
            retry_policy=_DEFAULT_RETRY,
        )
        # Expose as verification so gateway_or can branch yes/no (data-protection gate).
        passed = report.status == VerificationStatus.PASS or report.status == "pass"
        findings = [
            VerificationFinding(
                section="data_protection",
                severity=v.severity if hasattr(v, "severity") else (v.get("severity") if isinstance(v, dict) else "blocking"),
                message=v.message if hasattr(v, "message") else str(v.get("message", v)),
            )
            for v in (report.violations or [])
        ]
        ctx.last_verification = VerificationReport(
            artifact_id=getattr(report, "artifact_id", "") or getattr(ctx.artifact, "artifact_id", ""),
            artifact_version=getattr(ctx.artifact, "version", None) or ctx.artifact_version,
            status=VerificationStatus.PASS if passed else VerificationStatus.REWORK,
            findings=findings,
            required_fixes=(
                ["Удалите персональные данные и секреты из артефакта перед human review."]
                if not passed
                else []
            ),
        )
        _store_output(ctx, step, {"compliance": report.model_dump(), "output": report.model_dump()})
        return ctx

    if handler in ("publish", "http_callback", "publication"):
        retries = int(step.config.get("retries", settings.publish_retries))
        if ctx.artifact is None and inputs.get("artifact"):
            ctx.artifact = _coerce_artifact(inputs["artifact"])
        last_error = ""
        for pub_attempt in range(retries):
            try:
                ctx.receipt = await workflow.execute_activity(
                    publish_artifact_activity,
                    args=[ctx.spec, ctx.artifact],
                    start_to_close_timeout=_timeout(step, settings),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
                ctx.status = TaskStatus.DELIVERED
                _store_output(ctx, step, {"receipt": ctx.receipt.model_dump(), "output": ctx.receipt.model_dump()})
                return ctx
            except Exception as e:
                last_error = str(e)
                if pub_attempt < retries - 1:
                    await workflow.sleep(timedelta(seconds=2 ** pub_attempt))
        ctx.status = TaskStatus.FAILED
        ctx.error = last_error
        ctx.halted = True
        return ctx

    workflow.logger.warning("Unknown script handler %s on step %s", handler, step.id)
    _store_output(ctx, step, {"output": None, "warning": f"unknown script {handler}"})
    return ctx


async def run_step(
    step: WorkflowStepConfig,
    ctx: PipelineContext,
    settings: WorkflowSettings,
    template: WorkflowTemplate,
    workflow_ref: Any = None,
) -> PipelineContext:
    if ctx.halted or not step.enabled:
        return ctx

    st = StepType(step.type)
    inputs = _resolve_inputs(step, ctx)

    if st == StepType.START:
        await _ensure_spec(ctx, settings)
        _store_output(ctx, step, {"output": "started"})
        return ctx

    if st == StepType.START_PLAYBOOK:
        await _ensure_spec(ctx, settings)
        _store_output(
            ctx,
            step,
            {
                "output": "playbook_started",
                "routing": ctx.routing.model_dump() if ctx.routing else None,
            },
        )
        return ctx

    if st == StepType.END_PLAYBOOK:
        _store_output(ctx, step, {"output": "playbook_ended"})
        return ctx

    if st == StepType.SKILL:
        await _ensure_spec(ctx, settings)
        skill_id = _resolve_skill_id(step, ctx)

        # Deterministic classify skill (not an MCP Capability)
        if skill_id in ("classify", "classify-task"):
            # Pre-scenario classify already decided — do not overwrite inside the template.
            if ctx.routing is not None and not bool(step.config.get("force_reclassify")):
                if isinstance(ctx.routing, dict):
                    ctx.routing = RoutingDecision.model_validate(ctx.routing)
                ctx.last_decision = ctx.routing.primary_skill
                workflow.logger.info(
                    "Skipping in-scenario classify (pre-routed to %s) task=%s",
                    ctx.routing.primary_skill,
                    ctx.raw.task_id,
                )
                _store_output(
                    ctx,
                    step,
                    {
                        "routing": ctx.routing.model_dump(),
                        "output": ctx.routing.model_dump(),
                        "skipped": True,
                        "reason": "pre_scenario_route",
                    },
                )
                ctx.status = TaskStatus.EXECUTING
                return ctx

            raw_routing = await workflow.execute_activity(
                classify_task_activity,
                ctx.spec,
                start_to_close_timeout=_timeout(step, settings),
                retry_policy=_DEFAULT_RETRY,
            )
            ctx.routing = (
                raw_routing
                if isinstance(raw_routing, RoutingDecision)
                else RoutingDecision.model_validate(raw_routing)
            )
            ctx.last_decision = ctx.routing.primary_skill
            workflow.logger.info(
                "Classify step → %s (confidence=%s) task=%s",
                ctx.routing.primary_skill,
                ctx.routing.confidence,
                ctx.raw.task_id,
            )
            await workflow.execute_activity(
                record_execution_progress_activity,
                {
                    "task_id": ctx.raw.task_id,
                    "status": "RUNNING",
                    "stage": "Classify",
                    "activity": f"Routed to {ctx.routing.primary_skill}",
                    "progress_pct": 20,
                    "skill": ctx.routing.primary_skill,
                    "stage_key": "classify",
                    "stage_status": "COMPLETED",
                    "detail": f"confidence={ctx.routing.confidence}",
                },
                start_to_close_timeout=timedelta(minutes=1),
            )
            _store_output(ctx, step, {"routing": ctx.routing.model_dump(), "output": ctx.routing.model_dump()})
            ctx.status = TaskStatus.EXECUTING
            return ctx

        evidence_text = ""
        for v in inputs.values():
            if isinstance(v, str):
                evidence_text += v + "\n"
            elif isinstance(v, dict):
                evidence_text += str(v.get("excerpt", v.get("content", ""))) + "\n"

        # Preserve human reviewer feedback; merge verification fixes (do not wipe comments).
        prior_fixes = [str(f).strip() for f in (ctx.rework_fixes or []) if str(f).strip()]
        if step.config.get("mode") == "rework" and ctx.last_verification:
            rep = ctx.last_verification
            fixes = getattr(rep, "required_fixes", None) or []
            if isinstance(rep, dict):
                fixes = rep.get("required_fixes", []) or []
            ver_fixes = [str(f).strip() for f in fixes if str(f).strip()]
            merged: list[str] = []
            for item in [*prior_fixes, *ver_fixes]:
                if item not in merged:
                    merged.append(item)
            ctx.rework_fixes = merged
            # Approval path already bumps version; quality-gate → refine bumps here.
            if not prior_fixes:
                ctx.artifact_version += 1

        previous_artifact = ""
        consume_prior = bool(step.config.get("consume_prior_artifact"))
        if ctx.artifact is not None and (
            ctx.rework_fixes or step.config.get("mode") == "rework" or consume_prior
        ):
            previous_artifact = _artifact_content(ctx.artifact)
            if consume_prior and previous_artifact and "APPROVED BUSINESS REQUIREMENTS" not in evidence_text:
                evidence_text = (
                    f"[APPROVED BUSINESS REQUIREMENTS]\n{previous_artifact[:12000]}\n\n{evidence_text}"
                ).strip()

        if step.config.get("reset_artifact_version"):
            ctx.artifact_version = 1

        result = await workflow.execute_activity(
            execute_skill_step_activity,
            args=[
                ctx.spec,
                skill_id,
                evidence_text,
                ctx.rework_fixes or None,
                ctx.artifact_version,
                ctx.routing,
                previous_artifact or None,
                [str(k).strip() for k in (step.config.get("rule_keys") or []) if str(k).strip()],
                (step.config.get("graph_key") or step.config.get("playbook_key") or skill_id),
            ],
            start_to_close_timeout=_timeout(step, settings),
            retry_policy=_EXECUTE_RETRY,
        )
        _store_output(ctx, step, result)
        if "artifact" in result:
            ctx.artifact = _coerce_artifact(result["artifact"])
        ctx.status = TaskStatus.EXECUTING
        ctx.rework_fixes = []

    elif st == StepType.SCRIPT:
        ctx = await _run_script(step, ctx, settings, inputs)

    elif st == StepType.WAIT_CONTEXT:
        # Interrupt: pause for external signal / additional context
        await workflow.execute_activity(
            notify_escalation_activity,
            args=[ctx.spec, f"Waiting for context/signal: {step.label}", ctx.artifact_version],
            start_to_close_timeout=timedelta(minutes=2),
        )
        ctx.status = TaskStatus.ESCALATED
        if not step.config.get("auto_continue", False):
            ctx.halted = True
        _store_output(ctx, step, {"output": "wait_context"})

    elif st in (StepType.TOOL, StepType.SYSTEM):
        # Legacy capability-as-step (compat)
        await _ensure_spec(ctx, settings)
        tool_id = step.capability_id or step.tool_id or step.system_handler or "task.read"
        result = await workflow.execute_activity(
            execute_tool_activity,
            args=[tool_id, ctx.spec, ctx.routing, ctx.plan, ctx.evidence, ctx.artifact, inputs],
            start_to_close_timeout=_timeout(step, settings),
            retry_policy=_DEFAULT_RETRY,
        )
        _store_output(ctx, step, result)
        if "routing" in result:
            ctx.routing = RoutingDecision.model_validate(result["routing"])
        if "evidence" in result:
            from src.orchestrator.models import EvidenceBundle
            ctx.evidence = EvidenceBundle.model_validate(result["evidence"])

    elif st == StepType.VALIDATION:
        await _ensure_spec(ctx, settings)
        art = _coerce_artifact(ctx.artifact)
        if inputs.get("artifact"):
            art = _coerce_artifact(inputs["artifact"])
        if art is None:
            ctx.error = "Validation step missing artifact"
            ctx.halted = True
            return ctx
        report = await workflow.execute_activity(
            verify_artifact_activity,
            args=[ctx.spec, art],
            start_to_close_timeout=_timeout(step, settings),
            retry_policy=_LLM_RETRY,
        )
        ctx.last_verification = report
        ctx.artifact = art
        _store_output(ctx, step, {"verification_report": report.model_dump(), "output": report.model_dump()})
        ctx.status = TaskStatus.UNDER_REVIEW

    elif st in (StepType.DECISION, StepType.GATEWAY_OR):
        route_mode = str(step.config.get("mode", "")).lower() in ("route_skill", "route_by_skill", "classify")
        if route_mode:
            if ctx.routing is None:
                await _ensure_spec(ctx, settings)
                raw_routing = await workflow.execute_activity(
                    classify_task_activity,
                    ctx.spec,
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=_DEFAULT_RETRY,
                )
                ctx.routing = (
                    raw_routing
                    if isinstance(raw_routing, RoutingDecision)
                    else RoutingDecision.model_validate(raw_routing)
                )
            elif isinstance(ctx.routing, dict):
                ctx.routing = RoutingDecision.model_validate(ctx.routing)
            ctx.last_decision = ctx.routing.primary_skill
            workflow.logger.info(
                "Route gateway → %s task=%s",
                ctx.last_decision,
                ctx.raw.task_id,
            )
            _store_output(
                ctx,
                step,
                {
                    "decision": ctx.last_decision,
                    "routing": ctx.routing.model_dump(),
                    "output": ctx.last_decision,
                },
            )
        else:
            report = ctx.last_verification
            if report is None and inputs.get("report"):
                report = VerificationReport.model_validate(inputs["report"])
            passed = False
            if report is not None:
                st_val = report.status if hasattr(report, "status") else report.get("status")
                passed = st_val == VerificationStatus.PASS or st_val == "pass"
            max_rework = int(settings.max_rework)
            if not passed and ctx.rework_count >= max_rework:
                workflow.logger.warning(
                    "Max rework (%d) reached for task %s — publishing best effort",
                    max_rework, ctx.raw.task_id,
                )
                ctx.last_decision = "yes"
            else:
                ctx.last_decision = "yes" if passed else "no"
                if not passed:
                    ctx.rework_count += 1
            _store_output(ctx, step, {"decision": ctx.last_decision, "output": ctx.last_decision})

    elif st == StepType.GATEWAY_AND:
        # Marker for fork/join; walker follows first unlabeled / first edge.
        # Full parallel fan-out is sequential fallback (same as PARALLEL).
        _store_output(ctx, step, {"decision": "and", "output": "and"})
        workflow.logger.info("Gateway AND %s — sequential edge follow", step.id)

    elif st == StepType.APPROVAL:
        if step.config.get("auto_approve", True):
            ctx.status = TaskStatus.APPROVED
            ctx.last_decision = "approve"
            _store_output(ctx, step, {"decision": "approve", "output": "approve"})
        else:
            preview = _resolve_artifact_preview(ctx, limit=8000)
            if not preview:
                workflow.logger.warning(
                    "Human checkpoint opening without artifact preview task=%s artifact_type=%s",
                    ctx.raw.task_id,
                    type(ctx.artifact).__name__ if ctx.artifact is not None else None,
                )
            art_type = None
            if isinstance(ctx.artifact, dict):
                art_type = ctx.artifact.get("type")
            else:
                raw_type = getattr(ctx.artifact, "type", None)
                art_type = raw_type.value if hasattr(raw_type, "value") else raw_type
            await workflow.execute_activity(
                open_human_checkpoint_activity,
                {
                    "task_id": ctx.raw.task_id,
                    "title": step.label or "Human approval",
                    "artifact_preview": preview,
                    "artifact_version": ctx.artifact_version,
                    "artifact_name": step.config.get("artifact_name") or (
                        art_type or "BusinessRequirementsDoc"
                    ),
                    "approver_role": step.config.get("approver_role") or "Product Owner",
                    "question": step.config.get("question") or "",
                    "checkpoint_key": step.config.get("checkpoint_key") or "",
                },
                start_to_close_timeout=timedelta(minutes=2),
            )
            await workflow.execute_activity(
                notify_escalation_activity,
                args=[
                    ctx.spec,
                    f"Approval required: {step.label}. Open Human Checkpoints in platform UI to decide.",
                    ctx.artifact_version,
                ],
                start_to_close_timeout=timedelta(minutes=2),
            )
            ctx.status = TaskStatus.ESCALATED
            if workflow_ref is not None:
                workflow_ref.clear_human_decision()
                timeout_h = float(step.config.get("timeout_hours", 72))
                workflow.logger.info(
                    "Waiting for human_decision signal (timeout=%sh) task=%s",
                    timeout_h, ctx.raw.task_id,
                )
                try:
                    await workflow.wait_condition(
                        lambda: workflow_ref.take_human_decision() is not None,
                        timeout=timedelta(hours=timeout_h),
                    )
                except Exception as wait_exc:
                    workflow.logger.error("Human approval wait failed: %s", wait_exc)
                    ctx.status = TaskStatus.ESCALATED
                    ctx.halted = True
                    ctx.error = f"Human approval timed out or failed: {wait_exc}"
                    _store_output(ctx, step, {"decision": "timeout", "output": "timeout"})
                    return ctx
                decision_payload = workflow_ref.take_human_decision() or {}
                decision = str(decision_payload.get("decision") or "").upper()
                comment = str(decision_payload.get("comment") or "")
                workflow_ref.clear_human_decision()
                if decision in {"APPROVE", "ACCEPT_RISK", "ACKNOWLEDGE"}:
                    ctx.status = TaskStatus.APPROVED
                    ctx.last_decision = "approve"
                    next_stage = str(step.config.get("next_stage") or "Publish Artifact")
                    await workflow.execute_activity(
                        record_execution_progress_activity,
                        {
                            "task_id": ctx.raw.task_id,
                            "status": "RUNNING",
                            "stage": next_stage,
                            "activity": f"Approved — continuing to {next_stage}",
                            "progress_pct": 85,
                            "stage_key": f"approval-{(step.config.get('checkpoint_key') or 'art')}",
                            "stage_status": "COMPLETED",
                            "detail": comment,
                        },
                        start_to_close_timeout=timedelta(minutes=1),
                    )
                elif decision in {"REQUEST_CHANGES"}:
                    ctx.status = TaskStatus.EXECUTING
                    ctx.last_decision = "request_changes"
                    ctx.rework_fixes = [comment or "Reviewer requested changes"]
                    ctx.rework_count += 1
                    ctx.artifact_version += 1
                    await workflow.execute_activity(
                        record_execution_progress_activity,
                        {
                            "task_id": ctx.raw.task_id,
                            "status": "RUNNING",
                            "stage": "Business Requirements",
                            "activity": "Changes requested — refining",
                            "progress_pct": 55,
                            "stage_key": "approval",
                            "stage_status": "COMPLETED",
                            "detail": comment,
                        },
                        start_to_close_timeout=timedelta(minutes=1),
                    )
                else:
                    # REJECT — follow a labeled reject edge when present; otherwise halt.
                    ctx.status = TaskStatus.ESCALATED
                    ctx.last_decision = "reject"
                    ctx.error = comment or "Rejected by human reviewer"
                    await workflow.execute_activity(
                        record_execution_progress_activity,
                        {
                            "task_id": ctx.raw.task_id,
                            "status": "CANCELLED",
                            "stage": "Human Approval",
                            "activity": "Rejected",
                            "progress_pct": 100,
                            "stage_key": "approval",
                            "stage_status": "FAILED",
                            "detail": comment,
                        },
                        start_to_close_timeout=timedelta(minutes=1),
                    )
                _store_output(
                    ctx,
                    step,
                    {"decision": ctx.last_decision, "output": ctx.last_decision, "comment": comment},
                )
            else:
                # No workflow ref — legacy halt
                ctx.halted = True

    elif st in (StepType.PUBLICATION, StepType.PUBLISH):
        step_script = WorkflowStepConfig(
            id=step.id, type=StepType.SCRIPT, label=step.label,
            script_id="publish", config=step.config, output_key=step.output_key,
            input_mappings=step.input_mappings, enabled=step.enabled,
        )
        ctx = await _run_script(step_script, ctx, settings, inputs)

    elif st == StepType.END:
        ctx.status = TaskStatus.CLOSED

    elif st == StepType.HUMAN_TASK:
        await workflow.execute_activity(
            notify_escalation_activity,
            args=[ctx.spec, f"Human task: {step.label}", ctx.artifact_version],
            start_to_close_timeout=timedelta(minutes=2),
        )
        ctx.status = TaskStatus.ESCALATED

    elif st == StepType.PARALLEL:
        workflow.logger.info("Parallel block %s — sequential fallback", step.id)

    elif st == StepType.SUB_PLAYBOOK:
        workflow.logger.info("Sub-playbook %s — not implemented, skipping", step.id)

    elif st == StepType.NORMALIZE:
        ctx.spec = await workflow.execute_activity(normalize_task, ctx.raw, start_to_close_timeout=_timeout(step, settings), retry_policy=_DEFAULT_RETRY)
    elif st == StepType.CLASSIFY:
        await _ensure_spec(ctx, settings)
        if ctx.routing is not None and not bool(step.config.get("force_reclassify")):
            if isinstance(ctx.routing, dict):
                ctx.routing = RoutingDecision.model_validate(ctx.routing)
            ctx.last_decision = ctx.routing.primary_skill
            _store_output(
                ctx,
                step,
                {
                    "routing": ctx.routing.model_dump(),
                    "output": ctx.routing.model_dump(),
                    "skipped": True,
                    "reason": "pre_scenario_route",
                },
            )
        else:
            raw_routing = await workflow.execute_activity(
                classify_task_activity,
                ctx.spec,
                start_to_close_timeout=_timeout(step, settings),
                retry_policy=_DEFAULT_RETRY,
            )
            ctx.routing = (
                raw_routing
                if isinstance(raw_routing, RoutingDecision)
                else RoutingDecision.model_validate(raw_routing)
            )
            ctx.last_decision = ctx.routing.primary_skill
            _store_output(ctx, step, {"routing": ctx.routing.model_dump(), "output": ctx.routing.model_dump()})
    elif st == StepType.EXECUTE_VERIFY_LOOP:
        await _ensure_spec(ctx, settings)
        max_rework = int(step.config.get("max_rework", settings.max_rework))
        for attempt in range(max_rework + 1):
            ctx.artifact = _coerce_artifact(
                await workflow.execute_activity(
                    execute_skill_activity,
                    args=[ctx.spec, ctx.routing, ctx.evidence, ctx.rework_fixes or None, ctx.artifact_version],
                    start_to_close_timeout=_timeout(step, settings),
                    retry_policy=_EXECUTE_RETRY,
                )
            )
            report = await workflow.execute_activity(verify_artifact_activity, args=[ctx.spec, ctx.artifact], start_to_close_timeout=timedelta(minutes=10), retry_policy=_LLM_RETRY)
            if report.status == VerificationStatus.PASS:
                break
            if attempt >= max_rework:
                ctx.halted = True
                return ctx
            ctx.rework_fixes = report.required_fixes or []
            ctx.artifact_version += 1

    return ctx


async def run_configurable_pipeline(
    raw: WorkflowInput,
    template: WorkflowTemplate,
    workflow_ref: Any = None,
    initial_routing: RoutingDecision | None = None,
    initial_spec: Any = None,
) -> WorkflowResult:
    """Walk playbook graph step-by-step with decision branching."""
    trace_id = raw.trace_id or raw.task_id
    ctx = PipelineContext(raw=raw, trace_id=trace_id)
    if initial_spec is not None:
        ctx.spec = initial_spec
    if initial_routing is not None:
        ctx.routing = initial_routing
        ctx.last_decision = initial_routing.primary_skill
    settings = template.settings
    steps_by_id = {s.id: s for s in template.steps}

    current_id: Optional[str] = _entry_step_id(template)
    guard = 0
    max_iter = len(template.steps) * (settings.max_rework + 2) + 4

    workflow.logger.info(
        "Running playbook %s for task %s (pre_route=%s)",
        template.id,
        raw.task_id,
        getattr(initial_routing, "primary_skill", None),
    )

    await workflow.execute_activity(
        record_execution_progress_activity,
        {
            "task_id": raw.task_id,
            "status": "RUNNING",
            "stage": "Intake",
            "activity": f"Running playbook {template.id}",
            "progress_pct": 10,
            "stage_key": "intake",
            "stage_status": "RUNNING",
        },
        start_to_close_timeout=timedelta(minutes=1),
    )

    while current_id and guard < max_iter:
        guard += 1
        step = steps_by_id.get(current_id)
        if step is None:
            break

        st_name = StepType(step.type)
        if st_name == StepType.SKILL and step.skill_id == "business-requirements":
            await workflow.execute_activity(
                record_execution_progress_activity,
                {
                    "task_id": raw.task_id,
                    "status": "RUNNING",
                    "stage": "Business Requirements",
                    "activity": step.label,
                    "progress_pct": 40,
                    "skill": "business-requirements",
                    "stage_key": "intake",
                    "stage_status": "COMPLETED",
                },
                start_to_close_timeout=timedelta(minutes=1),
            )
            await workflow.execute_activity(
                record_execution_progress_activity,
                {
                    "task_id": raw.task_id,
                    "stage_key": "brd",
                    "stage_status": "RUNNING",
                    "activity": "Generating BRD",
                    "progress_pct": 45,
                },
                start_to_close_timeout=timedelta(minutes=1),
            )
        elif st_name in (StepType.PUBLICATION, StepType.PUBLISH) or (
            st_name == StepType.SCRIPT and step.script_id == "publish"
        ):
            await workflow.execute_activity(
                record_execution_progress_activity,
                {
                    "task_id": raw.task_id,
                    "status": "RUNNING",
                    "stage": "Publish Artifact",
                    "activity": "Publishing to Slack",
                    "progress_pct": 90,
                    "stage_key": "publish",
                    "stage_status": "RUNNING",
                },
                start_to_close_timeout=timedelta(minutes=1),
            )

        ctx = await run_step(step, ctx, settings, template, workflow_ref=workflow_ref)
        if ctx.halted:
            await workflow.execute_activity(
                record_execution_progress_activity,
                {
                    "task_id": raw.task_id,
                    "status": "CANCELLED" if ctx.error else "FAILED",
                    "activity": "Halted",
                    "detail": ctx.error or "",
                    "progress_pct": 100,
                },
                start_to_close_timeout=timedelta(minutes=1),
            )
            return ctx.to_result()
        if StepType(step.type) == StepType.END:
            ctx.status = TaskStatus.CLOSED
            await workflow.execute_activity(
                record_execution_progress_activity,
                {
                    "task_id": raw.task_id,
                    "status": "COMPLETED",
                    "stage": "End",
                    "activity": "Completed",
                    "progress_pct": 100,
                    "stage_key": "publish",
                    "stage_status": "COMPLETED",
                },
                start_to_close_timeout=timedelta(minutes=1),
            )
            return ctx.to_result()

        st_cur = StepType(step.type)
        branch = None
        if st_cur in (StepType.DECISION, StepType.GATEWAY_OR) or _is_skill_router(step):
            branch = ctx.last_decision
        elif st_cur == StepType.APPROVAL:
            branch = ctx.last_decision
        current_id = _next_step_id(template, step.id, branch)
        if current_id is None and not ctx.halted and StepType(step.type) != StepType.END:
            if st_cur == StepType.APPROVAL and branch == "reject":
                ctx.halted = True
                ctx.error = ctx.error or "Rejected by human reviewer (no reject edge — execution stopped)"
                workflow.logger.info("%s task=%s", ctx.error, raw.task_id)
                return ctx.to_result()
            ctx.halted = True
            ctx.error = (
                f"No outgoing edge from '{step.id}' for branch={branch!r}. "
                "Check classify routing labels on the workflow template."
            )
            workflow.logger.error("%s task=%s", ctx.error, raw.task_id)
            await workflow.execute_activity(
                record_execution_progress_activity,
                {
                    "task_id": raw.task_id,
                    "status": "FAILED",
                    "activity": "Routing failed",
                    "detail": ctx.error,
                    "progress_pct": 100,
                },
                start_to_close_timeout=timedelta(minutes=1),
            )
            return ctx.to_result()

    if ctx.status != TaskStatus.CLOSED and not ctx.halted:
        if guard >= max_iter:
            workflow.logger.error(
                "Pipeline iteration guard hit (%d) for task %s — halting",
                max_iter, raw.task_id,
            )
            ctx.halted = True
            ctx.error = "Pipeline iteration limit exceeded"
        else:
            ctx.status = TaskStatus.CLOSED
    return ctx.to_result()
