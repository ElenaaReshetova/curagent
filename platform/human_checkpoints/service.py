"""Human Checkpoints persistence and review actions."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.platform.executions import service as executions_svc
from src.platform.human_checkpoints.models import (
    ActivityEvent,
    ControlResult,
    DecisionOption,
    EvidenceItem,
    HumanCheckpointCatalogItem,
    HumanCheckpointMetrics,
    HumanCheckpointRecord,
)
from src.platform.human_checkpoints.validation import TERMINAL, can_transition, validate_record
from src.platform.store import append_audit, get_platform_dir

logger = logging.getLogger(__name__)
_SEEDING = False


def _path(name: str) -> Path:
    return get_platform_dir() / name


def _read_json(name: str, default: Any) -> Any:
    path = _path(name)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed reading %s: %s", path, e)
        return default


def _write_json(name: str, payload: Any) -> None:
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def list_records() -> list[HumanCheckpointRecord]:
    ensure_human_checkpoints_seeded()
    raw = _read_json("human_checkpoints.json", {"human_checkpoints": []})
    return [HumanCheckpointRecord.model_validate(item) for item in raw.get("human_checkpoints", [])]


def _save_records(records: list[HumanCheckpointRecord]) -> None:
    _write_json("human_checkpoints.json", {"human_checkpoints": [r.model_dump(mode="json") for r in records]})


def get_record(checkpoint_id: str) -> HumanCheckpointRecord | None:
    return next((r for r in list_records() if r.id == checkpoint_id), None)


def save_record(rec: HumanCheckpointRecord) -> HumanCheckpointRecord:
    records = [r for r in list_records() if r.id != rec.id]
    records.append(rec)
    _save_records(records)
    return rec


def ensure_human_checkpoints_seeded() -> None:
    global _SEEDING
    marker = _path(".seeded_human_checkpoints_v1")
    if marker.exists() and _path("human_checkpoints.json").exists():
        return
    if _SEEDING:
        return
    _SEEDING = True
    try:
        _seed_unlocked()
    finally:
        _SEEDING = False


def _seed_unlocked() -> None:
    marker = _path(".seeded_human_checkpoints_v1")
    if marker.exists() and _path("human_checkpoints.json").exists():
        return

    now = datetime.utcnow()
    options = [
        DecisionOption(key="APPROVE", label="Approve", impact="Execution will resume and continue to Development."),
        DecisionOption(key="REQUEST_CHANGES", label="Request changes", impact="Execution will return to the revision step.", requires_comment=True),
        DecisionOption(key="REJECT", label="Reject", impact="Execution will follow the rejection transition and may stop.", requires_comment=True),
    ]
    seeds = [
        HumanCheckpointRecord(
            id="CHK-2026-001842",
            title="Approve System Requirements",
            execution_id="EXE-2026-004182",
            execution_title="Payment cancellation",
            source="Jira PAY-123",
            checkpoint_type="APPROVAL",
            status="IN_REVIEW",
            priority="HIGH",
            risk_level="HIGH",
            question="Can this artifact proceed to development?",
            requested_action="Approve or request revisions for the System Requirements draft.",
            artifact_name="System Requirements Draft",
            artifact_version="v1",
            assignee="Alexey Khromov",
            assignee_role="Solution Architect",
            assignee_team="Payments Architecture",
            assignment_type="ROLE",
            due_label="Today, 17:00",
            sla_label="4h 18m",
            queue_view="my",
            waiting_minutes=258,
            warnings_count=2,
            evidence_count=14,
            controls_passed=8,
            controls_warning=1,
            decision_options=options,
            artifact_preview=(
                "## System Requirements: Payment Cancellation\n\n"
                "### 1. Scope\n"
                "The system shall support cancellation of eligible payment transactions before settlement.\n\n"
                "### 2. Functional requirements\n"
                "Cancellation eligibility shall be determined by payment state, settlement window and channel restrictions.\n\n"
                "### 3. Failure handling\n"
                "Failed cancellation shall preserve the original transaction and emit a structured failure event.\n"
            ),
            artifact_diff=[
                "+ Added rollback behavior for partial cancellation.",
                "+ Added idempotency requirement.",
                "- Removed manual settlement exception.",
                "+ Added timeout and retry requirements.",
            ],
            key_changes=[
                "Added cancellation state model.",
                "Added rollback requirements.",
                "Updated API error scenarios.",
            ],
            evidence=[
                EvidenceItem(title="Payment Cancellation Architecture", source="Confluence · PAY-ARCH-102", score=0.93, excerpt="Architecture scope and service boundaries."),
                EvidenceItem(title="CancellationService.java", source="Git · payment-api", score=0.89, excerpt="Current implementation and idempotency guardrails."),
                EvidenceItem(title="PAY-872 Previous feature", source="Jira · PAY-872", score=0.84, excerpt="Reference rollout and regression notes."),
            ],
            controls=[
                ControlResult(name="Architecture approval required", result="PASSED", severity="HIGH", explanation="Required reviewer assigned."),
                ControlResult(name="Evidence minimum", result="PASSED", severity="MEDIUM", explanation="More than minimum evidence linked."),
                ControlResult(name="Operational rollback documented", result="WARNING", severity="MEDIUM", explanation="Rollback flow exists but lacks alerting detail."),
            ],
            activity=[
                ActivityEvent(at="10:46", title="Checkpoint opened", actor="System"),
                ActivityEvent(at="10:47", title="Assigned to Solution Architects", actor="Assignment Resolver"),
                ActivityEvent(at="11:02", title="Claimed by Alexey Khromov", actor="Reviewer"),
            ],
            review_summary={"artifact": "System Requirements Draft v1", "evidence": 14, "warnings": 2, "controls_passed": 8},
            audit=[{"at": now.isoformat(), "action": "checkpoint.created", "actor": "system"}],
            created_at=now,
            updated_at=now,
        ),
        HumanCheckpointRecord(
            id="CHK-2026-001841",
            title="Architecture sign-off",
            execution_id="EXE-2026-004181",
            execution_title="Card tokenization update",
            source="Jira CARD-772",
            checkpoint_type="SIGN_OFF",
            status="ASSIGNED",
            priority="HIGH",
            risk_level="HIGH",
            question="Does the proposed architecture meet platform standards?",
            requested_action="Review architecture decision package and sign off.",
            artifact_name="Architecture Decision",
            artifact_version="v2",
            assignee="Elena Volkova",
            assignee_role="Solution Architect",
            assignee_team="Payments Architecture",
            due_label="Today, 14:30",
            sla_label="1h 42m",
            queue_view="my",
            waiting_minutes=102,
            warnings_count=1,
            evidence_count=9,
            controls_passed=6,
            decision_options=options,
            key_changes=["Added fallback provider path.", "Introduced MCP audit trace."],
            evidence=[EvidenceItem(title="ADR-004 Capability Gateway", source="Docs", score=0.88, excerpt="Gateway constraints and capability allowlists.")],
            controls=[ControlResult(name="Architecture control pack", result="PASSED", severity="HIGH")],
            activity=[ActivityEvent(at="09:12", title="Checkpoint assigned", actor="Assignment Resolver")],
            review_summary={"artifact": "Architecture Decision v2", "evidence": 9, "warnings": 1, "controls_passed": 6},
            audit=[{"at": now.isoformat(), "action": "checkpoint.assigned", "actor": "resolver"}],
            created_at=now,
            updated_at=now,
        ),
        HumanCheckpointRecord(
            id="CHK-2026-001838",
            title="Accept residual risk",
            execution_id="EXE-2026-004177",
            execution_title="Login incident",
            source="Jira IAM-221",
            checkpoint_type="RISK_ACCEPTANCE",
            status="ESCALATED",
            priority="HIGH",
            risk_level="HIGH",
            question="Can the documented residual risk be accepted?",
            requested_action="Manager review required due to overdue risk checkpoint.",
            artifact_name="Risk Assessment",
            artifact_version="v1",
            assignee="Security Review Team",
            assignee_team="Security Review Team",
            due_label="Overdue",
            sla_label="Overdue 2h",
            queue_view="overdue",
            waiting_minutes=600,
            warnings_count=3,
            evidence_count=6,
            controls_passed=4,
            controls_warning=2,
            escalated=True,
            decision_options=[
                DecisionOption(key="ACCEPT_RISK", label="Accept risk", impact="Execution resumes with accepted residual risk."),
                DecisionOption(key="DECLINE_RISK", label="Decline risk", impact="Execution stops on the current path.", requires_comment=True),
            ],
            key_changes=["Residual risk remains on token replay window."],
            evidence=[EvidenceItem(title="Threat model delta", source="Security review", score=0.91, excerpt="Residual replay risk after mitigation.")],
            controls=[ControlResult(name="Security exception policy", result="WARNING", severity="HIGH", blocking=True)],
            activity=[ActivityEvent(at="08:14", title="Checkpoint escalated", actor="SLA Service")],
            review_summary={"artifact": "Risk Assessment v1", "evidence": 6, "warnings": 3, "controls_passed": 4},
            audit=[{"at": now.isoformat(), "action": "checkpoint.escalated", "actor": "sla-service"}],
            created_at=now,
            updated_at=now,
        ),
        HumanCheckpointRecord(
            id="CHK-2026-001834",
            title="Review Business Requirements",
            execution_id="EXE-2026-004170",
            execution_title="Merchant onboarding",
            source="Jira PAY-118",
            checkpoint_type="REVIEW",
            status="OPEN",
            priority="MEDIUM",
            risk_level="MEDIUM",
            question="Are the business requirements complete and testable?",
            requested_action="Reviewer should validate requirement completeness.",
            artifact_name="Business Requirements",
            artifact_version="v2",
            assignee="Payments Product Team",
            assignee_team="Payments Product Team",
            due_label="Today, 19:00",
            sla_label="7h 05m",
            queue_view="team",
            waiting_minutes=425,
            warnings_count=1,
            evidence_count=7,
            controls_passed=5,
            decision_options=options,
            key_changes=["Clarified merchant KYC flow."],
            activity=[ActivityEvent(at="08:22", title="Checkpoint opened", actor="System")],
            review_summary={"artifact": "Business Requirements v2", "evidence": 7, "warnings": 1, "controls_passed": 5},
            created_at=now,
            updated_at=now,
        ),
        HumanCheckpointRecord(
            id="CHK-2026-001829",
            title="Approve publication",
            execution_id="EXE-2026-004156",
            execution_title="Operations runbook update",
            source="Manual",
            checkpoint_type="PUBLICATION_APPROVAL",
            status="OPEN",
            priority="MEDIUM",
            risk_level="MEDIUM",
            question="Can this artifact be published to the operational repository?",
            requested_action="Publication gate before artifact release.",
            artifact_name="Operational Runbook",
            artifact_version="v4",
            assignee="Unassigned",
            assignee_team="Operations",
            due_label="Tomorrow, 09:00",
            sla_label="12h 20m",
            queue_view="unassigned",
            waiting_minutes=740,
            warnings_count=0,
            evidence_count=5,
            controls_passed=6,
            decision_options=options,
            key_changes=["Updated incident rollback and on-call contacts."],
            activity=[ActivityEvent(at="07:50", title="Added to team queue", actor="Assignment Resolver")],
            review_summary={"artifact": "Operational Runbook v4", "evidence": 5, "warnings": 0, "controls_passed": 6},
            created_at=now,
            updated_at=now,
        ),
        HumanCheckpointRecord(
            id="CHK-2026-001824",
            title="Provide missing retention period",
            execution_id="EXE-2026-004150",
            execution_title="Data retention rule",
            source="Jira DATA-77",
            checkpoint_type="MANUAL_INPUT",
            status="ASSIGNED",
            priority="LOW",
            risk_level="LOW",
            question="What retention period should be applied?",
            requested_action="Provide missing policy input to continue execution.",
            artifact_name="Data Requirements Draft",
            artifact_version="v1",
            assignee="Data Governance",
            assignee_team="Data Governance",
            due_label="In 1 day",
            sla_label="1d 3h",
            queue_view="team",
            waiting_minutes=1620,
            warnings_count=0,
            evidence_count=3,
            controls_passed=3,
            decision_options=[
                DecisionOption(key="PROVIDE_INPUT", label="Provide input", impact="Execution resumes with supplied structured input."),
            ],
            key_changes=["Retention policy section missing from draft."],
            activity=[ActivityEvent(at="Yesterday", title="Assigned to Data Governance", actor="Assignment Resolver")],
            review_summary={"artifact": "Data Requirements Draft", "evidence": 3, "warnings": 0, "controls_passed": 3},
            created_at=now,
            updated_at=now,
        ),
    ]
    _save_records(seeds)
    marker.write_text(now.isoformat() + "\n", encoding="utf-8")


def catalog_items(
    search: str = "",
    checkpoint_type: str = "",
    priority: str = "",
    status: str = "",
    view: str = "all",
) -> list[HumanCheckpointCatalogItem]:
    items: list[HumanCheckpointCatalogItem] = []
    for r in list_records():
        blob = f"{r.id} {r.title} {r.execution_id} {r.artifact_name} {r.source}".lower()
        if search and search.lower() not in blob:
            continue
        if checkpoint_type and r.checkpoint_type != checkpoint_type.upper():
            continue
        if priority and r.priority != priority.upper():
            continue
        if status and r.status != status.upper():
            continue
        if view and view != "all":
            if view == "team" and r.queue_view not in {"team", "my", "unassigned"}:
                continue
            elif view == "unassigned" and r.assignee != "Unassigned":
                continue
            elif view == "overdue" and "Overdue" not in r.sla_label and r.status != "ESCALATED":
                continue
            elif view == "completed" and r.status not in {"APPROVED", "REJECTED", "CHANGES_REQUESTED", "INPUT_PROVIDED"}:
                continue
            elif view == "my":
                # Actionable inbox: assigned to me OR unassigned open items
                if r.queue_view == "my":
                    pass
                elif r.assignee == "Unassigned" and r.status in {"OPEN", "ESCALATED", "ASSIGNED"}:
                    pass
                else:
                    continue
        items.append(HumanCheckpointCatalogItem(
            id=r.id,
            title=r.title,
            execution_id=r.execution_id,
            source=r.source,
            checkpoint_type=r.checkpoint_type,
            priority=r.priority,
            risk_level=r.risk_level,
            status=r.status,
            assignee=r.assignee,
            due_label=r.due_label,
            sla_label=r.sla_label,
            artifact_name=r.artifact_name + (" " + r.artifact_version if r.artifact_version else ""),
            waiting_minutes=r.waiting_minutes,
            escalated=r.escalated,
        ))
    items.sort(key=lambda x: x.id, reverse=True)
    return items


def metrics() -> HumanCheckpointMetrics:
    records = list_records()
    return HumanCheckpointMetrics(
        my_open=sum(
            1
            for r in records
            if r.status not in {"APPROVED", "REJECTED", "CHANGES_REQUESTED", "INPUT_PROVIDED"}
            and (r.queue_view == "my" or r.assignee == "Unassigned")
        ),
        due_today=sum(1 for r in records if r.due_label.startswith("Today")),
        team_queue=sum(1 for r in records if r.queue_view in {"team", "my", "unassigned"}),
        unassigned=sum(1 for r in records if r.assignee == "Unassigned" and r.status in {"OPEN", "ASSIGNED", "IN_REVIEW", "ESCALATED"}),
        overdue=sum(1 for r in records if "Overdue" in r.sla_label or r.status == "ESCALATED"),
        escalated=sum(1 for r in records if r.escalated or r.status == "ESCALATED"),
        completed=sum(1 for r in records if r.status in {"APPROVED", "REJECTED", "CHANGES_REQUESTED", "INPUT_PROVIDED"}),
        avg_decision_time="3h 42m",
    )


def detail(checkpoint_id: str) -> dict[str, Any]:
    rec = get_record(checkpoint_id)
    if not rec:
        raise KeyError("Checkpoint not found")
    payload = rec.model_dump(mode="json")
    preview = str(payload.get("artifact_preview") or "").strip()
    if not preview and rec.execution_id:
        try:
            from src.platform.executions import service as executions_svc

            ex = executions_svc.get_record(rec.execution_id)
            snap = (ex.snapshot if ex else None) or {}
            snap_preview = str(snap.get("artifact_preview") or "").strip()
            if snap_preview:
                payload["artifact_preview"] = snap_preview
        except Exception:
            pass
    return {
        "checkpoint": payload,
        "validation": validate_record(rec),
    }


def _update_status(checkpoint_id: str, status: str, actor: str, detail_text: str = "") -> HumanCheckpointRecord:
    records = list_records()
    updated: HumanCheckpointRecord | None = None
    for rec in records:
        if rec.id != checkpoint_id:
            continue
        if not can_transition(rec.status, status):
            raise ValueError(f"Invalid transition: {rec.status} -> {status}")
        rec.status = status  # type: ignore[assignment]
        rec.updated_at = datetime.utcnow()
        if status == "ESCALATED":
            rec.escalated = True
        rec.activity.append(ActivityEvent(at=datetime.utcnow().strftime("%H:%M"), title=f"Status → {status}", actor=actor, detail=detail_text))
        rec.audit.append({"at": datetime.utcnow().isoformat(), "action": f"checkpoint.{status.lower()}", "actor": actor, "detail": detail_text})
        updated = rec
        break
    if not updated:
        raise KeyError("Checkpoint not found")
    _save_records(records)
    append_audit("update", "human_checkpoint", updated.id, f"{updated.id} -> {status}", actor=actor)
    return updated


def claim(checkpoint_id: str, reviewer: str = "Alexey Khromov") -> dict[str, Any]:
    records = list_records()
    claimed: HumanCheckpointRecord | None = None
    for rec in records:
        if rec.id != checkpoint_id:
            continue
        target = "ASSIGNED" if rec.status in {"OPEN", "ESCALATED"} else rec.status
        if not can_transition(rec.status, target):
            raise ValueError(f"Invalid transition: {rec.status} -> {target}")
        rec.status = target  # type: ignore[assignment]
        rec.assignee = reviewer
        rec.queue_view = "my"
        rec.updated_at = datetime.utcnow()
        rec.activity.append(ActivityEvent(at=datetime.utcnow().strftime("%H:%M"), title=f"Claimed by {reviewer}", actor="Reviewer"))
        rec.audit.append({"at": datetime.utcnow().isoformat(), "action": "checkpoint.claimed", "actor": reviewer})
        claimed = rec
        break
    if not claimed:
        raise KeyError("Checkpoint not found")
    _save_records(records)
    return detail(claimed.id)


def claim_next(reviewer: str = "Alexey Khromov") -> dict[str, Any]:
    candidate = next((r for r in catalog_items(view="unassigned") if r.status in {"OPEN", "ESCALATED"}), None)
    if not candidate:
        raise KeyError("No unassigned checkpoints")
    return claim(candidate.id, reviewer=reviewer)


def start_review(checkpoint_id: str) -> dict[str, Any]:
    rec = _update_status(checkpoint_id, "IN_REVIEW", "Reviewer", "Review started")
    return detail(rec.id)


def submit_decision(checkpoint_id: str, decision: str, comment: str = "", structured_input: dict[str, Any] | None = None) -> dict[str, Any]:
    records = list_records()
    updated: HumanCheckpointRecord | None = None
    decision = decision.upper()
    decision_map = {
        "APPROVE": "APPROVED",
        "REJECT": "REJECTED",
        "REQUEST_CHANGES": "CHANGES_REQUESTED",
        "PROVIDE_INPUT": "INPUT_PROVIDED",
        "ACCEPT_RISK": "APPROVED",
        "DECLINE_RISK": "REJECTED",
        "ACKNOWLEDGE": "APPROVED",
        "SELECT_OPTION": "APPROVED",
    }
    target = decision_map.get(decision)
    if not target:
        raise ValueError("Unsupported decision")

    for rec in records:
        if rec.id != checkpoint_id:
            continue
        if rec.status in TERMINAL:
            raise ValueError(f"Checkpoint already closed ({rec.status})")
        option = next((o for o in rec.decision_options if o.key == decision), None)
        if not option:
            raise ValueError("Decision not allowed for this checkpoint")
        if option.requires_comment and not comment.strip():
            raise ValueError("Comment is required for this decision")
        if rec.status == "OPEN":
            if can_transition(rec.status, "IN_REVIEW"):
                rec.status = "IN_REVIEW"  # type: ignore[assignment]
        if not can_transition(rec.status, target):
            raise ValueError(f"Invalid transition: {rec.status} -> {target}")
        rec.status = target  # type: ignore[assignment]
        rec.selected_decision = decision
        rec.decision_comment = comment.strip() or None
        rec.decided_at = datetime.utcnow()
        rec.updated_at = rec.decided_at
        rec.queue_view = "completed"
        rec.activity.append(ActivityEvent(at=rec.decided_at.strftime("%H:%M"), title=f"Decision recorded: {decision}", actor=rec.assignee or "Reviewer", detail=comment.strip()))
        rec.audit.append({
            "at": rec.decided_at.isoformat(),
            "action": "checkpoint.decision.submitted",
            "actor": rec.assignee or "Reviewer",
            "decision": decision,
            "comment": comment.strip(),
            "structured_input": structured_input or {},
        })
        updated = rec
        break
    if not updated:
        raise KeyError("Checkpoint not found")

    _save_records(records)
    append_audit("decision", "human_checkpoint", updated.id, f"{updated.id} -> {decision}", actor=updated.assignee or "reviewer")

    if decision in {"APPROVE", "ACCEPT_RISK", "ACKNOWLEDGE", "SELECT_OPTION", "PROVIDE_INPUT"}:
        try:
            executions_svc.set_status(updated.execution_id, "RUNNING", f"Checkpoint {updated.id} {decision.lower()}")
        except Exception:
            logger.warning("Execution %s not updated after checkpoint decision", updated.execution_id)
    else:
        try:
            executions_svc.set_status(updated.execution_id, "PAUSED", f"Checkpoint {updated.id} {decision.lower()}")
        except Exception:
            logger.warning("Execution %s not updated after checkpoint decision", updated.execution_id)

    return detail(updated.id)
