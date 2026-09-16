"""Temporal activities for multi-agent task lifecycle."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from temporalio import activity

from src.orchestrator.classifier import classify_task, detect_language
from src.orchestrator.delivery import publish_via_callback, verify_publication
from src.orchestrator.models import (
    ArtifactDraft,
    ComplianceReport,
    EvidenceBundle,
    EvidenceItem,
    ExecutionPlan,
    ExecutionStep,
    NormalizedTaskSpec,
    PublicationReceipt,
    RoutingDecision,
    VerificationReport,
    VerificationStatus,
    WorkflowInput,
)
from src.orchestrator.validators import (
    checksum,
    merge_structural_into_report,
    run_compliance_checks,
    validate_structure,
)
from src.orchestrator.verifier import verify_with_llm

logger = logging.getLogger(__name__)

_project_root = Path(__file__).resolve().parents[2]
_agent = None
_agent_model_key = None


def _get_agent():
    """Build agent using active Runtime Profile model (falls back to env)."""
    from src.agent.core.runner import build_agent

    global _agent, _agent_model_key
    resolved = {
        "url": os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1"),
        "model": os.environ.get("LM_STUDIO_MODEL", "local-model"),
    }
    try:
        from src.platform.runtime_bridge import resolve_lm_studio_settings

        resolved = resolve_lm_studio_settings()
    except Exception as exc:
        activity.logger.warning("Could not resolve runtime profile: %s", exc)

    cache_key = f"{resolved.get('url')}::{resolved.get('model')}"
    if _agent is None or _agent_model_key != cache_key:
        skills_dir = os.environ.get("SKILLS_DIR")
        _agent = build_agent(
            skills_dir=Path(skills_dir) if skills_dir else None,
            project_root=_project_root,
            gigachat_credentials=os.environ.get("GIGACHAT_CREDENTIALS"),
            gigachat_model=os.environ.get("GIGACHAT_MODEL", "GigaChat"),
            lm_studio_url=resolved.get("url"),
            lm_studio_model=resolved.get("model") or "local-model",
        )
        _agent_model_key = cache_key
    return _agent


@activity.defn(name="record_execution_progress")
async def record_execution_progress_activity(payload: dict) -> dict:
    """Update platform Executions UI for a live Temporal run."""
    try:
        from src.platform.runtime_bridge import update_execution_progress

        update_execution_progress(
            payload["task_id"],
            status=payload.get("status"),
            stage=payload.get("stage"),
            activity=payload.get("activity"),
            progress_pct=payload.get("progress_pct"),
            skill=payload.get("skill"),
            detail=payload.get("detail") or "",
            stage_key=payload.get("stage_key"),
            stage_status=payload.get("stage_status"),
            stage_name=payload.get("stage_name"),
            flow_key=payload.get("flow_key"),
            flow_name=payload.get("flow_name"),
            graph_id=payload.get("graph_id"),
            graph_version_id=payload.get("graph_version_id"),
        )
        return {"ok": True}
    except Exception as exc:
        activity.logger.warning("record_execution_progress failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@activity.defn(name="open_human_checkpoint")
async def open_human_checkpoint_activity(payload: dict) -> dict:
    """Create a platform Human Checkpoint and mark execution waiting."""
    try:
        from src.platform.runtime_bridge import create_approval_checkpoint

        workflow_id = activity.info().workflow_id
        cid = create_approval_checkpoint(
            task_id=payload["task_id"],
            workflow_id=workflow_id,
            title=payload.get("title") or "Approve Business Requirements",
            artifact_preview=payload.get("artifact_preview") or "",
            artifact_version=int(payload.get("artifact_version") or 1),
            artifact_name=payload.get("artifact_name") or "BusinessRequirementsDoc",
            assignee_role=payload.get("approver_role") or payload.get("assignee_role") or "Product Owner",
            question=payload.get("question") or "",
            checkpoint_key=payload.get("checkpoint_key") or "",
        )
        return {"ok": True, "checkpoint_id": cid, "workflow_id": workflow_id}
    except Exception as exc:
        activity.logger.exception("open_human_checkpoint failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@activity.defn(name="resolve_flow_template")
async def resolve_flow_template_activity(payload: dict) -> dict:
    """Resolve workflow template from armed platform E2E flow graph."""
    from src.orchestrator.flow_template_resolver import resolve_execution_template

    template_id, reason, meta = resolve_execution_template(
        primary_skill=str(payload.get("primary_skill") or "general"),
        requested_template_id=payload.get("workflow_template_id"),
        flow_key=payload.get("flow_key"),
        source=payload.get("source"),
        project=payload.get("project"),
        issue_type=payload.get("issue_type"),
        graph_only=bool(payload.get("graph_only")),
    )
    return {"template_id": template_id, "reason": reason, **meta}


@activity.defn(name="load_workflow_template")
async def load_workflow_template_activity(template_id: str | None = None) -> dict:
    """Load workflow template JSON for configurable pipeline."""
    from src.orchestrator.workflow_config.store import get_default_template, get_template

    if template_id:
        template = get_template(template_id)
        if template is None:
            activity.logger.warning("Template %s not found, using default", template_id)
            template = get_default_template()
    else:
        template = get_default_template()
    activity.logger.info("Loaded workflow template: %s", template.id)
    return template.model_dump()


@activity.defn(name="execute_tool")
async def execute_tool_activity(
    tool_id: str,
    spec: NormalizedTaskSpec,
    routing: Optional[RoutingDecision],
    plan: Optional[ExecutionPlan],
    evidence: Optional[EvidenceBundle],
    artifact: Optional[ArtifactDraft],
    inputs: dict,
) -> dict:
    """Execute tool via Tool Gateway (SEC-002 — no direct adapter bypass)."""
    from src.tool_gateway.gateway.gateway import build_intent_from_legacy, get_gateway
    from src.tool_gateway.models.envelopes import ApprovalArtifact, ApprovalTier
    from src.tool_gateway.registry.store import get_manifest

    activity.logger.info("Executing tool %s via Tool Gateway", tool_id)

    intent = build_intent_from_legacy(
        tool_id=tool_id,
        trace_id=spec.trace_id,
        task_id=spec.task_id,
        inputs=inputs,
        caller_role="playbook-executor",
        idempotency_key=f"{spec.task_id}:{tool_id}:{artifact.version if artifact else 0}",
    )

    manifest = get_manifest(tool_id)
    if manifest and manifest.approval_tier in (ApprovalTier.SOFT, ApprovalTier.HARD):
        intent = intent.model_copy(update={
            "approval_ref": ApprovalArtifact(
                approval_id=f"playbook-{spec.task_id}",
                tier_granted=manifest.approval_tier,
                tenant_id=intent.tenant_id,
                capability_id=tool_id,
                caller_id=intent.caller.agent_id,
                issued_at=datetime.now(timezone.utc).isoformat(),
                expires_at="2099-12-31T23:59:59Z",
            ),
        })

    ctx = {
        "spec": spec,
        "routing": routing,
        "plan": plan,
        "evidence": evidence,
        "artifact": artifact,
    }
    response = await get_gateway().invoke(intent, ctx)
    if not response.success or response.result is None:
        denial = response.denial
        code = denial.denial_code.value if denial else "UNKNOWN"
        msg = denial.message if denial else "Tool Gateway denied invocation"
        raise ValueError(f"Tool Gateway denial [{code}]: {msg}")

    return response.result.outputs


@activity.defn(name="execute_skill_step")
async def execute_skill_step_activity(
    spec: NormalizedTaskSpec,
    skill_id: str,
    evidence_text: str,
    rework_fixes: list[str] | None = None,
    artifact_version: int = 1,
    routing: Optional[RoutingDecision] = None,
    previous_artifact: str | None = None,
    rule_keys: list[str] | None = None,
    playbook_key: str | None = None,
) -> dict:
    """Execute a specific skill by id (playbook skill step)."""
    from src.orchestrator.classifier import _SKILL_ARTIFACT, classify_task
    from src.platform.graphs.bindings import bound_rule_keys_for_skill
    from src.platform.rules import service as rules_svc

    if routing is None:
        routing = classify_task(spec.description, spec.title)
    # Override skill + artifact type from playbook step (not classifier guess)
    artifact_type = _SKILL_ARTIFACT.get(skill_id, routing.artifact_type)
    routing = routing.model_copy(update={"primary_skill": skill_id, "artifact_type": artifact_type})

    explicit_keys = [str(k).strip() for k in (rule_keys or []) if str(k).strip()]
    resolved_keys = explicit_keys or bound_rule_keys_for_skill(
        skill_id,
        playbook_key,
    )
    rule_bundle = rules_svc.resolve_bound_bundle(resolved_keys) if resolved_keys else {}
    rules_markdown = str(rule_bundle.get("bundle_markdown") or "").strip()
    if resolved_keys:
        activity.logger.info(
            "Applying bound rules for skill %s: %s",
            skill_id,
            rule_bundle.get("effective_rule_keys") or resolved_keys,
        )

    agent = _get_agent()
    enriched = spec.description
    if evidence_text:
        enriched = f"[CONTEXT]\n{evidence_text[:8000]}\n\n[TASK]\n{spec.description}"

    from src.agent.core.runner import execute_skill

    content = await execute_skill(
        agent=agent,
        description=enriched,
        skill_name=skill_id,
        project_root=_project_root,
        rework_fixes=rework_fixes,
        previous_artifact=previous_artifact,
        rules_markdown=rules_markdown or None,
    )
    artifact_id = f"{spec.task_id}-{skill_id}"
    artifact = ArtifactDraft(
        artifact_id=artifact_id,
        task_id=spec.task_id,
        type=routing.artifact_type,
        skill=skill_id,
        version=artifact_version,
        content=content,
        content_checksum=checksum(content),
        provenance={
            "skill_id": skill_id,
            "executor": "skill-step",
            "playbook_key": playbook_key or skill_id,
            "rule_keys": resolved_keys,
            "rule_bundle": {
                "ruleVersionIds": rule_bundle.get("effective_rule_ids") or [],
                "effectiveRuleKeys": rule_bundle.get("effective_rule_keys") or [],
                "checksum": checksum(rules_markdown) if rules_markdown else "",
            },
        },
    )
    return {"artifact": artifact.model_dump(), "output": artifact.model_dump()}


@activity.defn(name="normalize_task")
async def normalize_task(raw: WorkflowInput) -> NormalizedTaskSpec:
    """Intake Normalizer: raw Kafka message → canonical Task Spec."""
    activity.logger.info("Normalizing task %s", raw.task_id)
    title = raw.description.split("\n")[0][:200] if raw.description else raw.task_id
    return NormalizedTaskSpec(
        task_id=raw.task_id,
        trace_id=raw.trace_id or raw.task_id,
        title=title,
        description=raw.description,
        source=raw.source,
        source_id=raw.source_id,
        callback_url=raw.callback_url,
        language=detect_language(raw.description),
        constraints=[],
        source_refs=[raw.source_id],
    )


@activity.defn(name="classify_task")
async def classify_task_activity(spec: NormalizedTaskSpec) -> RoutingDecision:
    """Task Classifier & Router."""
    decision = classify_task(spec.description, spec.title)
    activity.logger.info(
        "Classified task %s → primary_skill=%s confidence=%s title=%r",
        spec.task_id,
        decision.primary_skill,
        decision.confidence,
        (spec.title or "")[:120],
    )
    return decision


@activity.defn(name="plan_task")
async def plan_task(spec: NormalizedTaskSpec, routing: RoutingDecision) -> ExecutionPlan:
    """Planner / Decomposer — trivial plan for MVP, expandable for complex tasks."""
    step = ExecutionStep(
        step_id="step-1",
        skill=routing.primary_skill,
        description=spec.description,
        done_criteria=f"Complete {routing.artifact_type.value} per skill {routing.primary_skill}",
    )
    steps = [step]
    if routing.requires_planning and routing.complexity == "high":
        steps.append(ExecutionStep(
            step_id="step-2",
            skill="general",
            description="Review and consolidate output from step-1",
            done_criteria="Consolidated artifact ready for verification",
        ))
    return ExecutionPlan(
        task_id=spec.task_id,
        steps=steps,
        evidence_requirements=["source_description"],
    )


@activity.defn(name="collect_evidence")
async def collect_evidence(spec: NormalizedTaskSpec, plan: ExecutionPlan) -> EvidenceBundle:
    """Evidence Collector — MVP: capture source description as evidence."""
    item = EvidenceItem(
        evidence_id=str(uuid.uuid4()),
        type="source_description",
        source_uri=spec.source_id,
        excerpt=spec.description[:4000],
        checksum=checksum(spec.description),
    )
    return EvidenceBundle(task_id=spec.task_id, items=[item])


@activity.defn(name="execute_skill")
async def execute_skill_activity(
    spec: NormalizedTaskSpec,
    routing: RoutingDecision,
    evidence: EvidenceBundle,
    rework_fixes: list[str] | None = None,
    artifact_version: int = 1,
) -> ArtifactDraft:
    """Skill Executor — produces artifact draft without delivery."""
    from src.platform.graphs.bindings import bound_rule_keys_for_skill
    from src.platform.rules import service as rules_svc

    activity.logger.info(
        "Executing skill %s for task %s (v%d)",
        routing.primary_skill, spec.task_id, artifact_version,
    )
    resolved_keys = bound_rule_keys_for_skill(routing.primary_skill)
    rule_bundle = rules_svc.resolve_bound_bundle(resolved_keys) if resolved_keys else {}
    rules_markdown = str(rule_bundle.get("bundle_markdown") or "").strip()

    agent = _get_agent()
    enriched = spec.description
    if evidence.items:
        refs = "\n".join(f"- [{e.type}] {e.excerpt[:500]}" for e in evidence.items[:3])
        enriched = f"[EVIDENCE]\n{refs}\n\n[TASK]\n{spec.description}"

    from src.agent.core.runner import execute_skill

    content = await execute_skill(
        agent=agent,
        description=enriched,
        skill_name=routing.primary_skill,
        project_root=_project_root,
        rework_fixes=rework_fixes,
        rules_markdown=rules_markdown or None,
    )
    artifact_id = f"{spec.task_id}-artifact"
    return ArtifactDraft(
        artifact_id=artifact_id,
        task_id=spec.task_id,
        type=routing.artifact_type,
        skill=routing.primary_skill,
        version=artifact_version,
        content=content,
        content_checksum=checksum(content),
        evidence_refs=[e.evidence_id for e in evidence.items],
        provenance={
            "model": os.environ.get("GIGACHAT_MODEL") or os.environ.get("LM_STUDIO_MODEL", "local"),
            "executor": "skill-executor",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "rule_keys": resolved_keys,
            "rule_bundle": {
                "ruleVersionIds": rule_bundle.get("effective_rule_ids") or [],
                "effectiveRuleKeys": rule_bundle.get("effective_rule_keys") or [],
                "checksum": checksum(rules_markdown) if rules_markdown else "",
            },
        },
    )


@activity.defn(name="verify_artifact")
async def verify_artifact_activity(
    spec: NormalizedTaskSpec,
    artifact: ArtifactDraft,
) -> VerificationReport:
    """Independent Verifier — structural + semantic checks."""
    activity.logger.info("Verifying artifact %s v%d", artifact.artifact_id, artifact.version)
    structural = validate_structure(artifact)

    agent = _get_agent()
    sem_status, scores, sem_findings, required_fixes = await verify_with_llm(
        agent.llm, spec, artifact,
    )

    return merge_structural_into_report(
        artifact=artifact,
        structural_findings=structural,
        semantic_status=sem_status,
        semantic_findings=sem_findings,
        scores=scores,
        required_fixes=required_fixes,
    )


@activity.defn(name="check_compliance")
async def check_compliance_activity(artifact: ArtifactDraft) -> ComplianceReport:
    """Compliance & Policy Validator — deterministic rules."""
    activity.logger.info("Compliance check for artifact %s", artifact.artifact_id)
    return run_compliance_checks(artifact)


@activity.defn(name="publish_artifact")
async def publish_artifact_activity(
    spec: NormalizedTaskSpec,
    artifact: ArtifactDraft,
) -> PublicationReceipt:
    """Publisher — deliver to target via callback adapter."""
    activity.logger.info("Publishing artifact %s to %s", artifact.artifact_id, spec.source)
    receipt = await publish_via_callback(spec, artifact)
    if not await verify_publication(receipt):
        raise RuntimeError("Post-publish verification failed: invalid receipt")
    return receipt


@activity.defn(name="notify_escalation")
async def notify_escalation_activity(
    spec: NormalizedTaskSpec,
    reason: str,
    artifact_version: int = 0,
) -> str:
    """Escalation Handler — log + optional Slack/Jira notification via callback."""
    activity.logger.error(
        "ESCALATION task=%s reason=%s artifact_version=%d",
        spec.task_id, reason, artifact_version,
    )
    if spec.callback_url:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(spec.callback_url, json={
                    "task_id": spec.task_id,
                    "source_id": spec.source_id,
                    "message": f"[ESCALATION] {reason}",
                    "escalation": True,
                })
        except Exception as e:
            activity.logger.warning("Escalation callback failed: %s", e)
    return f"escalated:{spec.task_id}:{reason}"
