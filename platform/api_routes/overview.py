"""Overview and dashboard API routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.platform import store
from src.platform.scenarios import service as scenarios_svc
from src.platform.skills import service as skills_svc

router = APIRouter(tags=["overview"])


@router.get("/overview")
async def overview():
    payload = store.build_overview_from_store().model_dump(mode="json")
    payload["flows"] = scenarios_svc.list_scenarios(limit=1000)["items"]
    return payload


@router.get("/dashboard/summary")
async def dashboard_summary():
    o = store.build_overview_from_store()
    sk_metrics = skills_svc.metrics()
    executions = store.list_executions()
    completed = sum(1 for e in executions if e.status == "completed")
    failed = sum(1 for e in executions if e.status == "failed")
    active = sum(
        1
        for e in executions
        if e.status in {"running", "waiting_approval", "compiling", "received", "paused"}
    )
    rules = store.list_rules()
    capabilities = store.list_capabilities()
    audit = store.list_audit()
    integrations_online = sum(1 for i in o.integrations if i.status == "online")
    scenarios = scenarios_svc.list_scenarios(limit=1000)["items"]
    return {
        "scenarios_published": sum(1 for item in scenarios if item["status"] in {"published", "launched"}),
        "scenarios_total": len(scenarios),
        "skills_published": sk_metrics.published_versions,
        "skills_total": sk_metrics.skills,
        "rules_total": len(rules),
        "runtime_profiles": len(o.runtime_profiles),
        "knowledge_spaces": len(o.knowledge_spaces),
        "executions_total": len(executions),
        "executions_active": active,
        "executions_completed": completed,
        "executions_failed": failed,
        "success_rate": round(completed / len(executions), 3) if executions else 0,
        "pending_approvals": o.waiting_approvals_count,
        "control_packs": len(o.controls),
        "integrations_total": len(o.integrations),
        "integrations_online": integrations_online,
        "capabilities_total": len(capabilities),
        "capabilities_active": sum(1 for c in capabilities if c.status == "active"),
        "audit_events": len(audit),
    }


@router.get("/dashboard/pending-actions")
async def dashboard_pending_actions():
    approvals = []
    for ex in store.list_executions():
        for ap in ex.approvals:
            if ap.status == "pending":
                approvals.append({
                    "approval_id": ap.id,
                    "execution_id": ex.id,
                    "type": ap.type,
                    "subject": ap.subject,
                    "external_work_item_id": ex.external_work_item_id,
                })
    return {"pending_approvals": approvals}
