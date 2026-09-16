"""Bridge between Temporal runtime and platform control-plane stores.

Used by kafka_starter / orchestrator activities / human-checkpoint decisions so
Slack→Temporal runs appear in Executions UI, wait for human approval, and pick
up the active LM Studio model from Runtime Profiles.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_RUNTIME_PROFILE_KEY = os.environ.get("RUNTIME_PROFILE_KEY", "local-lm-studio")


def resolve_lm_studio_settings(profile_key: str | None = None) -> dict[str, str]:
    """Resolve LM Studio URL + model from active runtime profile, falling back to env."""
    url = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1")
    model = os.environ.get("LM_STUDIO_MODEL", "local-model")
    key = profile_key or DEFAULT_RUNTIME_PROFILE_KEY
    try:
        from src.platform.runtime_profiles import service as rp_svc

        rec = rp_svc.get_record(key)
        if rec:
            ver = rp_svc._current_version(rec)  # noqa: SLF001
            if ver and ver.model:
                if ver.provider in ("LM_STUDIO", "LOCAL_OLLAMA", "LOCAL_VLLM", "CUSTOM_HTTP", "OPENAI_API"):
                    model = ver.model
                gen = ver.generation_config or {}
                # Only override URL when explicitly configured (keep container env otherwise)
                if gen.get("base_url"):
                    url = str(gen["base_url"])
        from src.platform.store import get_platform_dir
        import json

        resolved_path = get_platform_dir() / "runtime_resolved.json"
        if resolved_path.exists():
            data = json.loads(resolved_path.read_text(encoding="utf-8"))
            if data.get("profile_key") in (None, key) and data.get("model"):
                model = str(data["model"])
            # Prefer env URL inside Docker; sidecar often has localhost from UI host
            if data.get("base_url") and "host.docker.internal" not in url:
                if "localhost" not in str(data.get("base_url")):
                    url = str(data["base_url"])
    except Exception as exc:
        logger.warning("Runtime profile resolve failed (%s); using env LM Studio settings", exc)
    return {"url": url, "model": model, "profile_key": key}


def write_resolved_runtime(profile_key: str, model: str, provider: str = "LM_STUDIO", base_url: str | None = None) -> None:
    """Persist effective runtime so workers pick up UI activates without restart of env."""
    from src.platform.store import get_platform_dir
    import json

    path = get_platform_dir() / "runtime_resolved.json"
    payload = {
        "profile_key": profile_key,
        "provider": provider,
        "model": model,
        "base_url": base_url or os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1"),
        "updated_at": datetime.utcnow().isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _execution_id_for_task(task_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]", "", task_id)[:8].upper() or "TASK"
    return f"EXE-SLACK-{safe}"


GRAPH_WORKFLOW_TEMPLATE = "__graph_workflow__"
_GRAPH_TEMPLATE_ALIASES = frozenset({GRAPH_WORKFLOW_TEMPLATE, "__port_workflow__"})


def _legacy_playbook_stage_runs():
    from src.platform.executions.models import StageRun

    return [
        StageRun(key="intake", name="Slack Intake", status="RUNNING"),
        StageRun(key="classify", name="Classify", status="NOT_STARTED"),
        StageRun(key="brd", name="Business Requirements", status="NOT_STARTED"),
        StageRun(key="srd", name="System Requirements", status="NOT_STARTED"),
        StageRun(key="approval", name="Human Approval", status="NOT_STARTED"),
        StageRun(key="publish", name="Publish Artifact", status="NOT_STARTED"),
    ]


def stage_runs_from_plan(plan: dict[str, Any] | None):
    """Build inspector stages from a published Temporal plan (not the old playbook spine)."""
    from src.platform.executions.models import StageRun

    if not isinstance(plan, dict):
        return []
    steps = plan.get("steps") if isinstance(plan.get("steps"), dict) else {}
    order = list(plan.get("step_order") or steps.keys())
    out = []
    trigger = plan.get("trigger") if isinstance(plan.get("trigger"), dict) else {}
    tid = str(trigger.get("identifier") or "").strip()
    if tid and tid not in order:
        out.append(StageRun(key=tid, name=str(trigger.get("title") or "Trigger"), status="COMPLETED"))
    for sid in order:
        st = steps.get(sid) if isinstance(steps.get(sid), dict) else {}
        name = str((st or {}).get("name") or sid)
        out.append(StageRun(key=str(sid), name=name, status="NOT_STARTED"))
    return out


def _published_graph_context(*, flow_key: str | None, source: str | None = None) -> dict[str, Any]:
    try:
        from src.platform.graphs.service import find_ingress_port_plan

        compiled = find_ingress_port_plan(flow_key=flow_key, source=source)
        if compiled and compiled.get("plan"):
            return compiled
    except Exception as exc:
        logger.debug("published graph context skipped: %s", exc)
    return {}


def record_execution_started(
    *,
    task_id: str,
    source: str,
    source_id: str,
    description: str,
    workflow_id: str,
    workflow_template_id: str | None = None,
    flow_key: str | None = None,
) -> str:
    """Create (or refresh) a platform execution for a live Temporal run."""
    from src.platform.executions import service as executions_svc
    from src.platform.executions.models import ExecutionRecord, TimelineEvent

    now = datetime.utcnow()
    eid = _execution_id_for_task(task_id)
    title = (description or "Slack task").strip().replace("\n", " ")
    if len(title) > 120:
        title = title[:117] + "…"
    template = workflow_template_id or ""
    runtime = resolve_lm_studio_settings()
    graph_ctx = _published_graph_context(flow_key=flow_key, source=source)
    graph_plan = graph_ctx.get("plan") if graph_ctx else None
    is_graph = bool(graph_plan) or template in _GRAPH_TEMPLATE_ALIASES or (
        flow_key in {"ai-pdlc-flow", "e2e:ai-pdlc-flow"}
    )
    if is_graph:
        template = GRAPH_WORKFLOW_TEMPLATE
        flow_key = str(graph_ctx.get("flow_key") or flow_key or "ai-pdlc-flow")
        flow_name = str(graph_ctx.get("flow_name") or "AI PDLC")
        playbook_key, playbook_name = "", ""
        stage_runs = stage_runs_from_plan(graph_plan) or []
        exec_type = "FLOW"
        current_stage = (stage_runs[0].name if stage_runs else flow_name)
    elif template == "generate-system-requirements":
        flow_key, flow_name = "slack-srd-delivery", "Slack → System Requirements"
        playbook_key, playbook_name = "system-requirements", "System Requirements"
        stage_runs = _legacy_playbook_stage_runs()
        exec_type, current_stage = "PLAYBOOK", "Intake"
    elif template in ("generate-brd-then-srd-slack",):
        flow_key, flow_name = "slack-srd-delivery", "Slack → BRD → SRD"
        playbook_key, playbook_name = "business-requirements", "Business Requirements"
        stage_runs = _legacy_playbook_stage_runs()
        exec_type, current_stage = "PLAYBOOK", "Intake"
    elif template in ("generate-business-requirements-slack", "generate-brd-srd-slack"):
        flow_key, flow_name = "slack-brd-delivery", "Slack → Business Requirements"
        playbook_key, playbook_name = "business-requirements", "Business Requirements"
        stage_runs = _legacy_playbook_stage_runs()
        exec_type, current_stage = "PLAYBOOK", "Intake"
    elif flow_key:
        flow_key, flow_name = str(flow_key), str(flow_key)
        playbook_key, playbook_name = "", ""
        stage_runs = _legacy_playbook_stage_runs()
        exec_type, current_stage = "PLAYBOOK", "Intake"
    else:
        flow_key, flow_name = "slack-brd-srd-delivery", "Slack → Classify → BRD | SRD"
        playbook_key, playbook_name = "business-requirements", "Business Requirements"
        stage_runs = _legacy_playbook_stage_runs()
        exec_type, current_stage = "PLAYBOOK", "Intake"

    snap = {
        "task_id": task_id,
        "temporal_workflow_id": workflow_id,
        "workflow_template_id": template,
        "source_id": source_id,
    }
    if graph_ctx.get("graph_id"):
        snap["graph_id"] = str(graph_ctx["graph_id"])
        snap["graph_run_id"] = str(task_id)
    if graph_ctx.get("version_id"):
        snap["graph_version_id"] = str(graph_ctx["version_id"])

    existing = executions_svc.get_record(eid)
    if existing:
        patch_kw: dict[str, Any] = {
            "status": "RUNNING",
            "current_stage": current_stage,
            "current_activity": "Workflow started",
            "progress_pct": 5,
            "flow_key": flow_key,
            "flow_name": flow_name,
            "timeline_event": TimelineEvent(
                at=now.strftime("%H:%M:%S"),
                title="Workflow re-started",
                detail=f"Temporal {workflow_id}",
            ),
            "snapshot_updates": snap,
        }
        if stage_runs:
            patch_kw["replace_stage_runs"] = stage_runs
        executions_svc.patch_execution(eid, **patch_kw)
        if snap.get("graph_id"):
            try:
                from src.platform.graphs.service import ensure_live_run

                ensure_live_run(
                    run_id=task_id,
                    graph_id=str(snap["graph_id"]),
                    version_id=str(snap["graph_version_id"]) if snap.get("graph_version_id") else None,
                    temporal_workflow_id=workflow_id,
                )
            except Exception as exc:
                logger.debug("ensure_live_run on restart skipped: %s", exc)
        return eid

    rec = ExecutionRecord(
        id=eid,
        title=title or f"Slack task {task_id[:8]}",
        execution_type=exec_type,  # type: ignore[arg-type]
        source_type=source.upper() if source else "SLACK",
        source_ref=source_id or task_id,
        flow_key=flow_key,
        flow_name=flow_name,
        playbook_key=playbook_key,
        playbook_name=playbook_name,
        current_stage=current_stage,
        progress_pct=5,
        status="RUNNING",
        risk_level="MEDIUM",
        duration="0m",
        current_activity="Workflow started",
        stage_runs=stage_runs,
        timeline=[
            TimelineEvent(
                at=now.strftime("%H:%M:%S"),
                title="Execution started from Slack",
                detail=f"task_id={task_id}",
            )
        ],
        runtime_effective={
            "profile": runtime.get("profile_key"),
            "provider": "LM_STUDIO",
            "model": runtime.get("model"),
            "base_url": runtime.get("url"),
        },
        snapshot=snap,
        graph_id=snap.get("graph_id"),
        graph_run_id=snap.get("graph_run_id"),
        graph_version_id=snap.get("graph_version_id"),
        started_at=now,
        updated_at=now,
    )
    executions_svc.save_record(rec)
    logger.info("Recorded platform execution %s for workflow %s", eid, workflow_id)
    if snap.get("graph_id"):
        try:
            from src.platform.graphs.service import ensure_live_run

            ensure_live_run(
                run_id=task_id,
                graph_id=str(snap["graph_id"]),
                version_id=str(snap["graph_version_id"]) if snap.get("graph_version_id") else None,
                temporal_workflow_id=workflow_id,
            )
        except Exception as exc:
            logger.debug("ensure_live_run on start skipped: %s", exc)
    return eid


def update_execution_progress(
    task_id: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    activity: str | None = None,
    progress_pct: int | None = None,
    skill: str | None = None,
    detail: str = "",
    stage_key: str | None = None,
    stage_status: str | None = None,
    stage_name: str | None = None,
    flow_key: str | None = None,
    flow_name: str | None = None,
    graph_id: str | None = None,
    graph_version_id: str | None = None,
) -> None:
    from src.platform.executions import service as executions_svc
    from src.platform.executions.models import TimelineEvent

    eid = _execution_id_for_task(task_id)
    rec = executions_svc.get_record(eid)
    if not rec:
        return
    event = None
    if activity or detail:
        event = TimelineEvent(
            at=datetime.utcnow().strftime("%H:%M:%S"),
            title=activity or "Progress",
            detail=detail,
        )
    gid = graph_id or rec.graph_id or (rec.snapshot or {}).get("graph_id")
    gvid = graph_version_id or rec.graph_version_id or (rec.snapshot or {}).get("graph_version_id")
    patch_kwargs: dict[str, Any] = {
        "status": status,
        "current_stage": stage,
        "current_activity": activity,
        "progress_pct": progress_pct,
        "current_skill": skill,
        "timeline_event": event,
        "stage_key": stage_key,
        "stage_status": stage_status,
        "stage_name": stage_name or (stage if stage_key else None),
        "flow_key": flow_key,
        "flow_name": flow_name,
    }
    snap: dict[str, Any] = {}
    if gid:
        snap["graph_id"] = str(gid)
        snap["graph_run_id"] = str(task_id)
    if gvid:
        snap["graph_version_id"] = str(gvid)
    if snap:
        patch_kwargs["snapshot_updates"] = snap
        from src.platform.executions.service import LEGACY_PLAYBOOK_STAGE_KEYS

        mixed = any(s.key in LEGACY_PLAYBOOK_STAGE_KEYS for s in (rec.stage_runs or []))
        if mixed:
            ctx = _published_graph_context(flow_key=flow_key or rec.flow_key)
            plan = ctx.get("plan")
            rebuilt = stage_runs_from_plan(plan if isinstance(plan, dict) else None)
            if rebuilt:
                patch_kwargs["replace_stage_runs"] = rebuilt
        try:
            from src.platform.graphs.service import ensure_live_run

            ensure_live_run(
                run_id=task_id,
                graph_id=str(gid),
                version_id=str(gvid) if gvid else None,
                temporal_workflow_id=str((rec.snapshot or {}).get("temporal_workflow_id") or ""),
            )
        except Exception as exc:
            logger.debug("ensure_live_run skipped: %s", exc)
    # Keep Executions UI aligned with classify routing (not hard-coded BRD).
    if not flow_key and skill == "system-requirements":
        patch_kwargs["playbook_key"] = "system-requirements"
        patch_kwargs["playbook_name"] = "System Requirements"
        if not stage:
            patch_kwargs["current_stage"] = "System Requirements"
    elif not flow_key and skill == "business-requirements":
        patch_kwargs["playbook_key"] = "business-requirements"
        patch_kwargs["playbook_name"] = "Business Requirements"
        if not stage:
            patch_kwargs["current_stage"] = "Business Requirements"
    executions_svc.patch_execution(eid, **patch_kwargs)


def graph_refs_from_workflow(workflow_id: str, task_id: str = "") -> dict[str, str]:
    """Extract graph_run_id / related refs from Temporal workflow id."""
    out: dict[str, str] = {}
    wf = (workflow_id or "").strip()
    if wf.startswith("graph-run-"):
        out["graph_run_id"] = wf[len("graph-run-"):]
        out["temporal_workflow_id"] = wf
    elif task_id and len(task_id) >= 8 and "-" in task_id:
        # Graph activities pass run UUID as task_id
        try:
            from uuid import UUID

            UUID(str(task_id))
            out["graph_run_id"] = str(task_id)
        except Exception:
            pass
    return out


def create_approval_checkpoint(
    *,
    task_id: str,
    workflow_id: str,
    title: str,
    artifact_preview: str = "",
    artifact_version: int = 1,
    artifact_name: str = "BusinessRequirementsDoc",
    assignee_role: str = "Product Owner",
    question: str = "",
    checkpoint_key: str = "",
) -> str:
    from src.platform.executions import service as executions_svc
    from src.platform.executions.models import ArtifactRef, TimelineEvent
    from src.platform.human_checkpoints import service as hc_svc
    from src.platform.human_checkpoints.models import (
        ActivityEvent,
        DecisionOption,
        HumanCheckpointRecord,
    )

    eid = _execution_id_for_task(task_id)
    preview = (artifact_preview or "").strip()
    art_name = (artifact_name or "BusinessRequirementsDoc").strip() or "BusinessRequirementsDoc"
    role = (assignee_role or "Product Owner").strip() or "Product Owner"
    raw_ck = (checkpoint_key or "").strip()
    if raw_ck.lower() not in {"", "brd", "srd", "art"}:
        ck = raw_ck.upper()
        approval_stage_key = raw_ck
        approval_stage_name = raw_ck.replace("_", " ").strip().title() or "Review"
    else:
        ck = raw_ck.upper() or (
            "SRD" if "System" in art_name else "BRD"
        )
        approval_stage_key = f"approval-{ck.lower()}"
        approval_stage_name = "Human Approval"
    default_question = (
        "Можно ли публиковать системные требования в Slack thread?"
        if ck == "SRD"
        else "Можно ли принять BRD и продолжить сценарий?"
    )
    q = (question or "").strip() or default_question

    update_execution_progress(
        task_id,
        status="WAITING_FOR_HUMAN",
        stage=approval_stage_name,
        activity=f"Waiting for {art_name} approval",
        progress_pct=75,
        stage_key=approval_stage_key,
        stage_status="RUNNING",
        stage_name=approval_stage_name,
        detail="Human checkpoint opened",
    )

    # Persist artifact on the execution so Запуски / Inspector show it
    try:
        art_ver = f"v{artifact_version}"
        records = executions_svc.list_records()
        for r in records:
            if r.id != eid:
                continue
            arts = [
                a for a in (r.artifacts or [])
                if not (a.name == art_name and a.version == art_ver)
            ]
            arts.append(ArtifactRef(name=art_name, version=art_ver, status="Pending approval"))
            r.artifacts = arts
            r.artifacts_count = len(arts)
            snap = dict(r.snapshot or {})
            snap["artifact_preview"] = preview[:8000]
            snap["artifact_name"] = art_name
            snap["artifact_version"] = art_ver
            r.snapshot = snap
            r.timeline.append(TimelineEvent(
                at=datetime.utcnow().strftime("%H:%M:%S"),
                title="Artifact ready for approval",
                detail=f"{art_name} {art_ver}",
            ))
            r.updated_at = datetime.utcnow()
            break
        executions_svc._save_records(records)  # noqa: SLF001
    except Exception as exc:
        logger.warning("Could not attach artifact to execution %s: %s", eid, exc)

    now = datetime.utcnow()
    cid = f"CHK-{eid.replace('EXE-', '')}-{ck}"
    existing = hc_svc.get_record(cid)
    if existing:
        records = hc_svc.list_records()
        for r in records:
            if r.id != cid:
                continue
            old_preview = r.artifact_preview or ""
            applied_feedback = (r.decision_comment or "").strip()
            r.status = "OPEN"
            r.queue_view = "unassigned"
            r.assignee = "Unassigned"
            r.selected_decision = None
            r.decision_comment = None
            r.decided_at = None
            r.artifact_name = art_name
            r.assignee_role = role
            r.question = q
            r.artifact_preview = preview[:8000] if preview else old_preview
            r.artifact_version = f"v{artifact_version}"
            r.updated_at = now
            if old_preview and preview and old_preview != preview:
                import difflib

                r.artifact_diff = list(
                    difflib.unified_diff(
                        old_preview.splitlines(),
                        preview.splitlines(),
                        fromfile=f"v{max(1, artifact_version - 1)}",
                        tofile=f"v{artifact_version}",
                        lineterm="",
                    )
                )[:200]
            key_changes = [
                f"Обновлён артефакт до v{artifact_version}",
                f"Требуется повторное решение ({role})",
            ]
            if applied_feedback:
                key_changes.insert(0, f"Учтены замечания: {applied_feedback[:240]}")
            r.key_changes = key_changes
            r.review_summary = {
                **(r.review_summary or {}),
                "artifact": f"{art_name} v{artifact_version}",
                "temporal_workflow_id": workflow_id,
                "task_id": task_id,
                "execution_id": eid,
                "applied_feedback": applied_feedback or None,
                **graph_refs_from_workflow(workflow_id, task_id),
            }
            r.activity.append(ActivityEvent(
                at=now.strftime("%H:%M"),
                title="Checkpoint reopened for review" if existing.status != "OPEN" else "Artifact updated for review",
                detail=f"v{artifact_version}" + (f" · feedback: {applied_feedback[:120]}" if applied_feedback else ""),
            ))
            r.audit.append({
                "at": now.isoformat(),
                "action": "checkpoint.reopened" if existing.status not in {"OPEN", "ASSIGNED", "IN_REVIEW"} else "checkpoint.artifact_updated",
                "temporal_workflow_id": workflow_id,
                "task_id": task_id,
                "artifact_version": artifact_version,
                "applied_feedback": applied_feedback or None,
            })
            break
        hc_svc._save_records(records)  # noqa: SLF001
        logger.info("Reopened/updated human checkpoint %s for execution %s", cid, eid)
        return cid

    rec = HumanCheckpointRecord(
        id=cid,
        title=title or f"Approve {art_name}",
        execution_id=eid,
        execution_title=title,
        source=f"Slack · {task_id[:8]}",
        checkpoint_type="PUBLICATION_APPROVAL",
        status="OPEN",
        priority="HIGH",
        risk_level="MEDIUM",
        blocking=True,
        question=q,
        requested_action="Approve to continue, request changes to refine, or reject to stop.",
        artifact_name=art_name,
        artifact_version=f"v{artifact_version}",
        assignee="Unassigned",
        assignee_role=role,
        assignment_type="ROLE",
        due_label="Today, 23:59",
        sla_label="24h",
        queue_view="unassigned",
        decision_options=[
            DecisionOption(
                key="APPROVE",
                label="Approve",
                impact="Workflow continues to the next stage.",
            ),
            DecisionOption(
                key="REQUEST_CHANGES",
                label="Request changes",
                impact="Workflow will refine the artifact and return for another review.",
                requires_comment=True,
            ),
            DecisionOption(
                key="REJECT",
                label="Reject",
                impact="Workflow stops without publishing.",
                requires_comment=True,
            ),
        ],
        artifact_preview=preview[:8000],
        key_changes=[
            f"Сгенерирован артефакт {art_name}",
            f"Версия артефакта v{artifact_version}",
            f"Требуется решение ({role})",
        ],
        activity=[ActivityEvent(at=now.strftime("%H:%M"), title="Checkpoint created", detail=f"workflow={workflow_id}")],
        audit=[{
            "at": now.isoformat(),
            "action": "checkpoint.created",
            "temporal_workflow_id": workflow_id,
            "task_id": task_id,
        }],
        review_summary={
            "temporal_workflow_id": workflow_id,
            "task_id": task_id,
            "execution_id": eid,
            "artifact": f"{art_name} v{artifact_version}",
            "evidence": 0,
            "controls_passed": 0,
            **graph_refs_from_workflow(workflow_id, task_id),
        },
        created_at=now,
        updated_at=now,
    )
    hc_svc.save_record(rec)
    try:
        from uuid import UUID

        from src.platform.graphs import service as graphs_svc

        run = graphs_svc.get_run(UUID(str(task_id)))
        if workflow_id and run.temporal_workflow_id != workflow_id:
            run.temporal_workflow_id = workflow_id
            graphs_svc.update_run(run)
    except Exception:
        logger.debug("Could not pin checkpoint interpreter workflow id", exc_info=True)
    # Keep execution snapshot linked for Run Mode UI
    try:
        refs = graph_refs_from_workflow(workflow_id, task_id)
        if refs:
            executions_svc.patch_execution(eid, snapshot_updates=refs)
    except Exception as exc:
        logger.warning("Could not patch execution graph refs: %s", exc)
    logger.info("Created human checkpoint %s for execution %s", cid, eid)
    return cid


async def signal_temporal_decision(workflow_id: str, decision: str, comment: str = "") -> None:
    """Send human_decision to the waiting child (and parent, if distinct)."""
    from temporalio.client import Client

    from src.platform.graphs.expressions import normalize_hitl_decision

    host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    client = await Client.connect(host)
    mapped = normalize_hitl_decision(decision)
    payload = {"decision": mapped, "comment": comment or "", "raw_decision": decision}
    if workflow_id.startswith("graph-run-") or workflow_id.endswith(":graph"):
        targets = [workflow_id]
    else:
        targets = [f"{workflow_id}:graph"]
    last_exc: Exception | None = None
    signaled = False
    for wid in targets:
        try:
            handle = client.get_workflow_handle(wid)
            await handle.signal("human_decision", payload)
            logger.info("Signaled workflow %s decision=%s", wid, mapped)
            signaled = True
        except Exception as exc:
            last_exc = exc
            logger.warning("Temporal signal failed for %s: %s", wid, exc)
    if not signaled and last_exc:
        raise last_exc


def workflow_id_from_checkpoint(checkpoint_id: str) -> Optional[str]:
    from src.platform.human_checkpoints import service as hc_svc
    from src.platform.executions import service as executions_svc

    rec = hc_svc.get_record(checkpoint_id)
    if not rec:
        return None
    wf = (rec.review_summary or {}).get("temporal_workflow_id")
    if wf:
        return str(wf)
    ex = executions_svc.get_record(rec.execution_id)
    if ex and isinstance(ex.snapshot, dict):
        return ex.snapshot.get("temporal_workflow_id")
    return None
