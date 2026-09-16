"""Compatibility adapters for leftover /graphs* clients.

Product control plane is `/scenarios` + `/runs` (see api_routes/scenarios.py).
Keep these routes for flow-mirroring and preview (normalize/parse/validate).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from src.platform.graphs import service as graphs_svc
from src.platform.graphs.workflow_dsl import parse_workflow_dsl

router = APIRouter(tags=["graphs"])


@router.get("/schemas/workflow-graph")
async def schemas_workflow_graph():
    from src.platform.graphs.schema_export import build_schema_bundle

    return build_schema_bundle()


@router.get("/node-presets")
async def node_presets_list(kind: str | None = None):
    from src.platform.graphs import presets as presets_svc

    k = kind if kind in ("e2e", "stage") else None
    return {"presets": [p.model_dump(mode="json") for p in presets_svc.list_presets(kind=k)]}


@router.post("/node-presets")
async def node_presets_save(body: dict | None = None):
    from src.platform.graphs import presets as presets_svc

    body = body or {}
    try:
        rec = presets_svc.save_preset(
            name=str(body.get("name") or body.get("label") or ""),
            node_type=str(body.get("node_type") or body.get("type") or ""),
            label=str(body.get("label") or ""),
            config=body.get("config") if isinstance(body.get("config"), dict) else {},
            kind=str(body["kind"]) if body.get("kind") in ("e2e", "stage") else None,
            preset_id=UUID(str(body["id"])) if body.get("id") else None,
        )
        return rec.model_dump(mode="json")
    except KeyError:
        raise HTTPException(404, "Preset not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/node-presets/{preset_id}")
async def node_presets_delete(preset_id: str):
    from src.platform.graphs import presets as presets_svc

    try:
        presets_svc.delete_preset(UUID(preset_id))
        return {"ok": True}
    except (KeyError, ValueError):
        raise HTTPException(404, "Preset not found")


@router.get("/graphs")
async def graphs_list(kind: str | None = None):
    k = kind if kind in ("e2e", "stage") else None
    items = graphs_svc.list_graphs(k)  # type: ignore[arg-type]
    return {"graphs": [i.model_dump(mode="json") for i in items]}


@router.post("/graphs")
async def graphs_create(body: dict):
    try:
        kind = body.get("kind") or "stage"
        if kind not in ("e2e", "stage"):
            raise ValueError("kind must be e2e or stage")
        graph = body.get("dsl")
        if graph is None:
            raise ValueError("dsl required")
        rec = graphs_svc.create_graph(
            key=str(body.get("key") or ""),
            name=str(body.get("name") or body.get("key") or "Untitled"),
            kind=kind,
            description=str(body.get("description") or ""),
            graph=graph,
        )
        return rec.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/graphs/resolve")
async def graphs_resolve(kind: str, key: str, name: str | None = None):
    if kind not in ("e2e", "stage"):
        raise HTTPException(400, "kind must be e2e or stage")
    if not key:
        raise HTTPException(400, "key required")
    rec = graphs_svc.ensure_linked_graph(kind=kind, key=key, name=name or key)  # type: ignore[arg-type]
    return {"id": str(rec.id), "key": rec.key, "kind": rec.kind, "name": rec.name}


@router.get("/graphs/{graph_id}")
async def graphs_get(graph_id: str):
    try:
        rec = graphs_svc.get_graph(UUID(graph_id))
    except (KeyError, ValueError):
        try:
            rec = graphs_svc.get_graph_by_key(graph_id)
        except KeyError:
            raise HTTPException(404, "Graph not found")
    draft = None
    canvas = None
    if rec.current_draft_version_id:
        ver = graphs_svc.get_version(rec.current_draft_version_id)
        draft = ver.model_dump(mode="json")
        try:
            canvas = graphs_svc.get_draft_canvas(rec.id)
        except Exception:
            canvas = None
        if canvas is not None:
            draft["canvas"] = canvas
    return {**rec.model_dump(mode="json"), "draft": draft, "canvas": canvas, "published": draft}


@router.post("/graphs/{graph_id}/draft")
async def graphs_save_draft(graph_id: str, body: dict):
    try:
        ver = graphs_svc.save_draft(
            UUID(graph_id),
            body.get("dsl") or body,
            body.get("revision"),
        )
        return ver.model_dump(mode="json")
    except KeyError:
        raise HTTPException(404, "Graph not found")
    except ValueError as e:
        raise HTTPException(409 if "revision" in str(e) else 400, str(e))


@router.post("/graphs/normalize")
async def graphs_normalize(body: dict | None = None):
    """Normalize workflow DSL — strip ui/service params."""
    from src.platform.graphs.normalize import normalize_workflow_dsl

    body = body or {}
    try:
        doc = normalize_workflow_dsl(body.get("dsl") or body)
    except Exception as e:
        raise HTTPException(400, f"Invalid workflow DSL: {e}") from e
    return {"ok": True, "dsl": doc.model_dump(mode="json")}


@router.post("/graphs/parse")
async def graphs_parse(body: dict | None = None):
    """Normalize + parse workflow DSL → Temporal plan (preview)."""
    from src.platform.graphs.parse import parse_workflow_to_temporal

    body = body or {}
    try:
        doc = graphs_svc.prepare_workflow_doc(body.get("dsl") or body)
        plan = parse_workflow_to_temporal(doc)
    except Exception as e:
        raise HTTPException(400, str(e)) from e
    report = graphs_svc.validate_workflow(doc)
    return {
        "ok": report.ok,
        "validation": report.model_dump(mode="json"),
        "dsl": doc.model_dump(mode="json"),
        "plan": plan.to_dict(),
    }


@router.post("/graphs/{graph_id}/validate")
async def graphs_validate(graph_id: str, body: dict | None = None):
    try:
        rec = graphs_svc.get_graph(UUID(graph_id))
    except (KeyError, ValueError):
        raise HTTPException(404, "Graph not found")
    if body and (body.get("dsl") or body.get("nodes")):
        raw = body.get("dsl") or body
    elif rec.current_draft_version_id:
        raw = graphs_svc.get_version(rec.current_draft_version_id).dsl
    else:
        raise HTTPException(400, "No graph to validate")
    report = graphs_svc.validate_only(raw)
    return report.model_dump(mode="json")


@router.post("/graphs/{graph_id}/publish")
async def graphs_publish(graph_id: str, body: dict | None = None):
    try:
        vid = UUID(body["version_id"]) if body and body.get("version_id") else None
        ver = graphs_svc.publish_version(UUID(graph_id), vid)
        return ver.model_dump(mode="json")
    except KeyError:
        raise HTTPException(404, "Graph not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/graphs/{graph_id}/versions")
async def graphs_versions(graph_id: str):
    try:
        items = graphs_svc.list_versions(UUID(graph_id))
    except KeyError:
        raise HTTPException(404, "Graph not found")
    return {"versions": [i.model_dump(mode="json") for i in items]}
