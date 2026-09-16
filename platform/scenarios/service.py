"""Scenario control plane — product API over workflow tables.

Author contract (SCENARIO_SRS):
  GET/POST /scenarios
  GET/PUT/POST/DELETE /scenarios/{id}
  POST/GET /runs, signal, cancel

Physical store: workflows + versions + stages + connections + executions.
Canvas PUT is an atomic workflow DSL document; rows are a projection.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from src.platform.graphs import service as graphs_svc
from src.platform.graphs.models import GraphRecord, GraphRun, GraphVersion
from src.platform.graphs.workflow_dsl import workflow_dsl_to_canvas
from src.platform.scenarios.errors import ScenarioError

_PRODUCT = {"draft", "published", "launched"}


def product_status(rec: GraphRecord) -> str:
    if rec.launched:
        return "launched"
    if rec.status == "active":
        return "published"
    return "draft"


def _looks_uuid(value: str) -> bool:
    try:
        UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def resolve_record(scenario_id: str) -> GraphRecord:
    graphs_svc.ensure_graphs_seeded()
    if _looks_uuid(scenario_id):
        try:
            return graphs_svc.get_graph(UUID(scenario_id))
        except KeyError:
            raise ScenarioError("NOT_FOUND", f"Scenario {scenario_id} not found", http_status=404)
    try:
        return graphs_svc.get_graph_by_key(scenario_id)
    except KeyError:
        raise ScenarioError("NOT_FOUND", f"Scenario {scenario_id} not found", http_status=404)


def _version(vid: UUID | None) -> GraphVersion | None:
    if not vid:
        return None
    try:
        return graphs_svc.get_version(vid)
    except KeyError:
        return None


def working_version(rec: GraphRecord) -> GraphVersion | None:
    status = product_status(rec)
    if status == "draft":
        return _version(rec.current_draft_version_id) or _version(rec.current_published_version_id)
    return _version(rec.current_published_version_id) or _version(rec.current_draft_version_id)


def _canvas(dsl: dict[str, Any] | None, kind: str) -> dict[str, Any]:
    if not dsl:
        return {}
    from src.platform.graphs.workflow_dsl import parse_workflow_dsl

    canvas = workflow_dsl_to_canvas(parse_workflow_dsl(dsl))
    canvas["kind"] = kind
    return canvas


def card(rec: GraphRecord, *, include_dsl: bool = True) -> dict[str, Any]:
    rec = graphs_svc.get_graph(rec.id)
    status = product_status(rec)
    ver = working_version(rec)
    pub = _version(rec.current_published_version_id)
    dsl = dict(ver.dsl or {}) if ver else {}
    plan = None
    if status in {"published", "launched"} and pub:
        plan = pub.temporal_plan
    elif ver:
        plan = ver.temporal_plan
    validation = dict(ver.validation_report or {}) if ver else {"ok": True, "issues": []}
    body: dict[str, Any] = {
        "id": str(rec.id),
        "key": rec.key,
        "name": rec.name,
        "description": rec.description,
        "kind": rec.kind,
        "status": status,
        "revision": rec.revision,
        "plan": plan,
        "canvas": _canvas(dsl, rec.kind),
        "validation": validation,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
    }
    if include_dsl:
        body["dsl"] = dsl
    return body


def list_item(rec: GraphRecord) -> dict[str, Any]:
    ver = working_version(rec)
    nodes = (ver.dsl or {}).get("nodes") if ver and isinstance(ver.dsl, dict) else []
    return {
        "id": str(rec.id),
        "key": rec.key,
        "name": rec.name,
        "kind": rec.kind,
        "status": product_status(rec),
        "node_count": len(nodes) if isinstance(nodes, list) else 0,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
    }


def list_scenarios(
    *,
    kind: str | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    items = graphs_svc.list_graphs(kind if kind in ("e2e", "stage") else None)
    if status:
        items = [r for r in items if product_status(r) == status]
    if q:
        needle = q.lower()
        items = [r for r in items if needle in (r.name or "").lower() or needle in (r.key or "").lower()]
    items.sort(key=lambda r: r.updated_at or datetime.min, reverse=True)
    total = len(items)
    start = max(0, page) * max(1, limit)
    slice_ = items[start : start + max(1, limit)]
    return {"items": [list_item(r) for r in slice_], "total": total}


def create_scenario(body: dict[str, Any]) -> dict[str, Any]:
    key = str(body.get("key") or "").strip()
    name = str(body.get("name") or key or "").strip()
    kind = str(body.get("kind") or "e2e")
    if kind not in ("e2e", "stage"):
        raise ScenarioError("BAD_REQUEST", "kind must be e2e or stage")
    if not key:
        raise ScenarioError("BAD_REQUEST", "key required")
    full = key if ":" in key else f"{kind}:{key}"
    for rec in graphs_svc.list_graphs():
        if rec.key == full or rec.key == key:
            raise ScenarioError("CONFLICT", f"key {full} already exists", http_status=409)
    rec = graphs_svc.create_graph(
        key=key,
        name=name or key,
        kind=kind,  # type: ignore[arg-type]
        description=str(body.get("description") or ""),
        graph=body.get("dsl"),
    )
    return card(rec)


def get_scenario(scenario_id: str, *, include_dsl: bool = True) -> dict[str, Any]:
    return card(resolve_record(scenario_id), include_dsl=include_dsl)


def save_scenario(scenario_id: str, body: dict[str, Any]) -> dict[str, Any]:
    rec = resolve_record(scenario_id)
    if "plan" in body:
        raise ScenarioError("BAD_REQUEST", "plan is computed on publish; do not send it")
    if "status" in body:
        raise ScenarioError("BAD_REQUEST", "status is changed via POST, not PUT")
    if product_status(rec) != "draft":
        raise ScenarioError("NOT_DRAFT", "dsl can only be changed in draft", http_status=409)
    if body.get("revision") is not None and int(body["revision"]) != rec.revision:
        raise ScenarioError(
            "REVISION_CONFLICT",
            f"revision conflict: expected {rec.revision}",
            http_status=409,
        )
    dsl = body.get("dsl")
    if dsl is None:
        raise ScenarioError("BAD_REQUEST", "dsl required")
    graphs_svc.save_draft(rec.id, dsl, None)
    rec = graphs_svc.get_graph(rec.id)
    changed = False
    if body.get("name"):
        rec.name = str(body["name"])
        changed = True
    if "description" in body:
        rec.description = str(body.get("description") or "")
        changed = True
    if changed:
        expected_revision = rec.revision
        rec.revision += 1
        rec.updated_at = datetime.utcnow()
        _persist_record(rec, expected_revision=expected_revision)
    return card(graphs_svc.get_graph(rec.id))


def _replace_record(rec: GraphRecord) -> list[GraphRecord]:
    items = graphs_svc.list_graphs()
    out = []
    for r in items:
        out.append(rec if r.id == rec.id else r)
    return out


def _persist_record(rec: GraphRecord, *, expected_revision: int | None = None) -> None:
    try:
        graphs_svc.save_record(rec, expected_revision=expected_revision)
    except ValueError as exc:
        if "revision conflict" in str(exc):
            raise ScenarioError("REVISION_CONFLICT", str(exc), http_status=409) from exc
        raise


def _bump_record(rec: GraphRecord, *, launched: bool | None = None, status: str | None = None) -> dict[str, Any]:
    expected_revision = rec.revision
    if launched is not None:
        rec.launched = launched
    if status is not None:
        rec.status = status  # type: ignore[assignment]
    rec.revision += 1
    rec.updated_at = datetime.utcnow()
    _persist_record(rec, expected_revision=expected_revision)
    return card(rec)


def _publish_draft(rec: GraphRecord) -> GraphRecord:
    try:
        graphs_svc.publish_version(rec.id)
    except ValueError as exc:
        issues: list[Any] = []
        try:
            ver = working_version(graphs_svc.get_graph(rec.id))
            if ver and ver.dsl:
                report = graphs_svc.validate_only(ver.dsl)
                issues = [i.model_dump(mode="json") for i in report.issues]
        except Exception:
            pass
        raise ScenarioError(
            "VALIDATION_FAILED",
            str(exc),
            http_status=400,
            issues=issues,
        ) from exc
    rec = graphs_svc.get_graph(rec.id)
    expected_revision = rec.revision
    rec.status = "active"
    rec.launched = False
    rec.revision += 1
    rec.updated_at = datetime.utcnow()
    _persist_record(rec, expected_revision=expected_revision)
    return rec


_STATUS_PATCHES: dict[tuple[str, str], dict[str, Any]] = {
    ("published", "launched"): {"launched": True, "status": "active"},
    ("launched", "published"): {"launched": False, "status": "active"},
    ("published", "draft"): {"launched": False, "status": "draft"},
    ("launched", "draft"): {"launched": False, "status": "draft"},
}


def set_status(scenario_id: str, body: dict[str, Any]) -> dict[str, Any]:
    rec = resolve_record(scenario_id)
    to = str(body.get("status") or "").strip()
    if to not in _PRODUCT:
        raise ScenarioError("BAD_REQUEST", "status must be draft, published or launched")
    if body.get("revision") is not None and int(body["revision"]) != rec.revision:
        raise ScenarioError(
            "REVISION_CONFLICT",
            f"revision conflict: expected {rec.revision}",
            http_status=409,
        )
    current = product_status(rec)
    if to == current:
        return card(rec)

    if current == "draft" and to == "published":
        return card(_publish_draft(rec))

    if current == "draft" and to == "launched":
        raise ScenarioError("BAD_TRANSITION", "publish before launch")

    if to == "draft" and current in {"published", "launched"}:
        try:
            graphs_svc.create_draft_from_published(rec.id)
        except ValueError as exc:
            raise ScenarioError("BAD_TRANSITION", str(exc)) from exc
        return card(graphs_svc.get_graph(rec.id))

    patch = _STATUS_PATCHES.get((current, to))
    if patch is None:
        raise ScenarioError("BAD_TRANSITION", f"cannot go from {current} to {to}")
    if to == "launched" and rec.kind != "e2e":
        raise ScenarioError("BAD_REQUEST", "only e2e scenarios can be launched")
    return _bump_record(rec, **patch)


def delete_scenario(scenario_id: str) -> None:
    rec = resolve_record(scenario_id)
    executions = [
        r
        for r in graphs_svc._load_runs()  # noqa: SLF001
        if r.graph_id == rec.id
    ]
    if executions:
        raise ScenarioError("CONFLICT", "cannot delete a scenario with execution history", http_status=409)
    graphs_svc.delete_graph(rec.id)


async def start_run(body: dict[str, Any]) -> dict[str, Any]:
    raw_id = body.get("scenario_id") or body.get("graph_id") or body.get("scenario_key")
    if not raw_id:
        raise ScenarioError("BAD_REQUEST", "scenario_id (or graph_id / scenario_key) required")
    rec = resolve_record(str(raw_id))
    mode = str(body.get("mode") or "").strip().lower()
    payload = dict(body.get("input") or {})
    start_temporal = bool(body.get("start_temporal", True))
    if not mode:
        if str(payload.get("_source") or "").upper() == "TEST" or start_temporal is False:
            mode = "test"
        else:
            mode = "live"
    if mode == "live" and product_status(rec) != "launched":
        raise ScenarioError("NOT_LAUNCHED", "live run requires a launched e2e scenario")
    if mode == "test":
        payload["_source"] = "TEST"
        start_temporal = False
    try:
        if mode == "live":
            run = await graphs_svc.create_run_and_start(
                graph_id=rec.id,
                input_payload=payload,
                version_id=UUID(str(body["version_id"])) if body.get("version_id") else None,
            )
        else:
            run = graphs_svc.create_run(
                graph_id=rec.id,
                input_payload=payload,
                version_id=UUID(str(body["version_id"])) if body.get("version_id") else None,
                start_temporal=False,
            )
    except (ValueError, KeyError) as exc:
        raise ScenarioError("BAD_REQUEST", str(exc)) from exc
    if mode == "live" and run.status == "failed":
        raise ScenarioError(
            "RUNTIME_UNAVAILABLE",
            run.error or "Temporal is unavailable",
            http_status=503,
        )
    return run_card(run, rec)


def run_card(run: GraphRun, rec: GraphRecord | None = None) -> dict[str, Any]:
    rec = rec or graphs_svc.get_graph(run.graph_id)
    ver = _version(run.version_id)
    plan = (run.state or {}).get("plan") if isinstance(run.state, dict) else None
    return {
        "id": str(run.id),
        "scenario_id": str(run.graph_id),
        "scenario_key": rec.key if rec else None,
        "version_id": str(run.version_id),
        "status": run.status,
        "mode": "test" if str((run.state or {}).get("source") or "").upper() == "TEST" else "live",
        "input": run.input,
        "output": run.output,
        "state": run.state,
        "plan": plan or (ver.temporal_plan if ver else None),
        "dsl_snapshot": ver.dsl if ver else None,
        "temporal_workflow_id": run.temporal_workflow_id,
        "error": run.error,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def get_run(run_id: str) -> dict[str, Any]:
    try:
        run = graphs_svc.get_run(UUID(run_id))
    except (KeyError, ValueError):
        raise ScenarioError("NOT_FOUND", "Run not found", http_status=404)
    return run_card(run)


async def get_run_state(run_id: str) -> dict[str, Any]:
    try:
        return await graphs_svc.query_run_state_async(UUID(run_id))
    except (KeyError, ValueError):
        raise ScenarioError("NOT_FOUND", "Run not found", http_status=404)


def list_run_events(run_id: str) -> dict[str, Any]:
    try:
        run = graphs_svc.get_run(UUID(run_id))
    except (KeyError, ValueError):
        raise ScenarioError("NOT_FOUND", "Run not found", http_status=404)
    return {"events": list(run.events or [])}


async def signal_run(run_id: str, body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    try:
        run = graphs_svc.get_run(UUID(run_id))
    except (KeyError, ValueError):
        raise ScenarioError("NOT_FOUND", "Run not found", http_status=404)
    if run.status != "waiting" and str(body.get("decision") or body.get("signal") or "") in {
        "approve",
        "reject",
        "decline",
    }:
        raise ScenarioError("RUN_NOT_WAITING", "run is not waiting for a decision")
    decision = str(body.get("decision") or body.get("signal") or "approve")
    if decision == "reject":
        decision = "decline"
    try:
        run = await graphs_svc.signal_run_async(UUID(run_id), decision, body)
    except ValueError as exc:
        raise ScenarioError("BAD_REQUEST", str(exc)) from exc
    return run_card(run)


async def cancel_run(run_id: str) -> dict[str, Any]:
    try:
        run = graphs_svc.get_run(UUID(run_id))
    except (KeyError, ValueError):
        raise ScenarioError("NOT_FOUND", "Run not found", http_status=404)
    try:
        run = await graphs_svc.cancel_run_async(run.id)
    except Exception as exc:
        raise ScenarioError("RUNTIME_UNAVAILABLE", str(exc), http_status=503) from exc
    return run_card(run)


def node_types(kind: str | None = None) -> dict[str, Any]:
    k = kind if kind in ("e2e", "stage") else None
    return {"node_types": graphs_svc.node_types(k)}  # type: ignore[arg-type]
