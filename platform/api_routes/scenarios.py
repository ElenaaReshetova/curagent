"""Scenario control-plane HTTP API (SCENARIO_SRS)."""

from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from src.platform.scenarios import service as scenarios_svc
from src.platform.scenarios.errors import ScenarioError

router = APIRouter(tags=["scenarios"])


def _error(exc: ScenarioError) -> JSONResponse:
    return JSONResponse(status_code=exc.http_status, content=exc.as_body())


@router.get("/schemas/node-types")
async def node_types(kind: str | None = None):
    return scenarios_svc.node_types(kind)


@router.get("/scenarios")
async def scenarios_list(
    kind: str | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = 0,
    limit: int = 50,
):
    return scenarios_svc.list_scenarios(kind=kind, status=status, q=q, page=page, limit=limit)


@router.post("/scenarios", status_code=201)
async def scenarios_create(body: dict):
    try:
        return scenarios_svc.create_scenario(body or {})
    except ScenarioError as exc:
        return _error(exc)


@router.get("/scenarios/{scenario_id}")
async def scenarios_get(scenario_id: str, view: str | None = None):
    try:
        return scenarios_svc.get_scenario(scenario_id, include_dsl=view != "canvas")
    except ScenarioError as exc:
        return _error(exc)


@router.put("/scenarios/{scenario_id}")
async def scenarios_save(scenario_id: str, body: dict):
    try:
        return scenarios_svc.save_scenario(scenario_id, body or {})
    except ScenarioError as exc:
        return _error(exc)


@router.post("/scenarios/{scenario_id}")
async def scenarios_status(scenario_id: str, body: dict):
    try:
        return scenarios_svc.set_status(scenario_id, body or {})
    except ScenarioError as exc:
        return _error(exc)


@router.delete("/scenarios/{scenario_id}", status_code=204)
async def scenarios_delete(scenario_id: str):
    try:
        scenarios_svc.delete_scenario(scenario_id)
    except ScenarioError as exc:
        return _error(exc)
    return Response(status_code=204)


@router.post("/runs", status_code=201)
async def runs_create(body: dict):
    try:
        return await scenarios_svc.start_run(body or {})
    except ScenarioError as exc:
        return _error(exc)


@router.get("/runs/{run_id}")
async def runs_get(run_id: str):
    try:
        return scenarios_svc.get_run(run_id)
    except ScenarioError as exc:
        return _error(exc)


@router.get("/runs/{run_id}/state")
async def runs_state(run_id: str):
    try:
        return await scenarios_svc.get_run_state(run_id)
    except ScenarioError as exc:
        return _error(exc)


@router.get("/runs/{run_id}/events")
async def runs_events(run_id: str):
    try:
        return scenarios_svc.list_run_events(run_id)
    except ScenarioError as exc:
        return _error(exc)


@router.get("/runs/{run_id}/viewer")
async def runs_viewer(run_id: str):
    try:
        run = scenarios_svc.get_run(run_id)
        state = await scenarios_svc.get_run_state(run_id)
        rec = scenarios_svc.resolve_record(str(run["scenario_id"]))
        return {
            "run": run,
            "dsl": run.get("dsl_snapshot"),
            "plan": run.get("plan"),
            "state": state,
            "graph": run.get("dsl_snapshot") and scenarios_svc.card(rec).get("canvas"),
            "graph_id": run["scenario_id"],
            "version_id": run.get("version_id"),
        }
    except ScenarioError as exc:
        return _error(exc)


@router.post("/runs/{run_id}/signal")
async def runs_signal(run_id: str, body: dict | None = None):
    try:
        return await scenarios_svc.signal_run(run_id, body)
    except ScenarioError as exc:
        return _error(exc)


async def _signal_with_default(run_id: str, body: dict | None, decision: str):
    payload = dict(body or {})
    payload.setdefault("decision", decision)
    try:
        return await scenarios_svc.signal_run(run_id, payload)
    except ScenarioError as exc:
        return _error(exc)


@router.post("/runs/{run_id}/signal/approve")
async def runs_approve(run_id: str, body: dict | None = None):
    return await _signal_with_default(run_id, body, "approve")


@router.post("/runs/{run_id}/signal/reject")
async def runs_reject(run_id: str, body: dict | None = None):
    return await _signal_with_default(run_id, body, "reject")


@router.post("/runs/{run_id}/signal/changes")
async def runs_changes(run_id: str, body: dict | None = None):
    return await _signal_with_default(run_id, body, "changes")


@router.post("/runs/{run_id}/update/resume")
async def runs_resume(run_id: str, body: dict | None = None):
    return await _signal_with_default(run_id, body, "resume")


@router.post("/runs/{run_id}/cancel")
async def runs_cancel(run_id: str):
    try:
        return await scenarios_svc.cancel_run(run_id)
    except ScenarioError as exc:
        return _error(exc)
