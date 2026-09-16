"""AI PDLC Platform UI — Governed Playbooks with Pluggable Skills."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.platform.api import router as platform_router
from src.orchestrator.workflow_config.models import (
    STEP_TYPE_META,
    SkillDef,
    StepType,
    WorkflowEdge,
    WorkflowSettings,
    WorkflowStepConfig,
    WorkflowTemplate,
)
from src.orchestrator.workflow_config.registry import list_skills, save_skills
from src.orchestrator.workflow_config.store import (
    clone_template,
    delete_template,
    get_default_template,
    get_template,
    get_workflows_dir,
    list_templates,
    save_template,
    set_default_template,
    topological_order,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Governed AI Delivery Platform",
    description="Playbooks · Skills · Controls · Runtime Profiles",
)
app.include_router(platform_router)


@app.on_event("startup")
async def _platform_db_startup() -> None:
    """Ensure PG schema once at boot when PLATFORM_DATABASE_URL is configured."""
    from src.platform.db.settings import database_url

    if not database_url():
        return
    try:
        from src.platform.db.schema import ensure_schema

        ensure_schema()
    except Exception:
        logger.exception("Platform schema ensure failed on startup")

STATIC_DIR = Path(__file__).resolve().parent / "static"
SKILLS_DIR = Path(os.environ.get("SKILLS_DIR", Path(__file__).resolve().parents[2] / "skills"))
TEMPORAL_UI_URL = os.environ.get("TEMPORAL_UI_URL", "http://localhost:8088")
TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")


class TemplateSummary(BaseModel):
    id: str
    name: str
    description: str
    version: int
    is_default: bool
    status: str
    step_count: int


class CreateTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    clone_from: Optional[str] = None


class ValidateResponse(BaseModel):
    valid: bool
    execution_order: list[str]
    errors: list[str] = Field(default_factory=list)


# ── Skills ──────────────────────────────────────────────────────

@app.get("/api/skills")
async def api_skills():
    return {"skills": [s.model_dump() for s in list_skills()]}


@app.put("/api/skills")
async def api_save_skills(body: dict):
    items = [SkillDef.model_validate(s) for s in body.get("skills", [])]
    save_skills(items)
    return {"skills": [s.model_dump() for s in list_skills()]}


@app.get("/api/skills/{skill_id}")
async def api_get_skill(skill_id: str):
    from src.orchestrator.workflow_config.skill_manifests import get_skill_manifest
    sk = next((s for s in list_skills() if s.id == skill_id), None)
    if sk is None:
        raise HTTPException(404, f"Skill {skill_id} not found")
    man = get_skill_manifest(skill_id)
    return {
        "skill": sk.model_dump(),
        "manifest": man.model_dump() if man else None,
    }


@app.put("/api/skills/{skill_id}")
async def api_save_skill(skill_id: str, body: dict):
    from src.orchestrator.workflow_config.registry import save_skill
    body = dict(body)
    body["id"] = skill_id
    # drop legacy single capability_id from UI
    body.pop("capability_id", None)
    sk = SkillDef.model_validate(body)
    saved = save_skill(sk)
    return {"skill": saved.model_dump()}


@app.get("/api/skills/{skill_id}/content")
async def api_skill_content(skill_id: str):
    path = SKILLS_DIR / skill_id / "SKILL.md"
    if not path.exists():
        raise HTTPException(404, f"Skill {skill_id} not found")
    return {"id": skill_id, "content": path.read_text(encoding="utf-8")}


# ── Capabilities (Tool Gateway manifests) ───────────────────────

@app.get("/api/capabilities")
async def api_capabilities():
    from src.tool_gateway.registry.store import (
        ensure_loaded,
        get_manifests_dir,
        get_snapshot_id,
        is_registry_available,
        list_manifests,
    )
    ensure_loaded()
    return {
        "capabilities": [m.model_dump() for m in list_manifests()],
        "snapshot_id": get_snapshot_id(),
        "registry_available": is_registry_available(),
        "manifests_dir": str(get_manifests_dir()),
    }


@app.get("/api/capabilities/{capability_id}")
async def api_get_capability(capability_id: str):
    from src.tool_gateway.registry.store import ensure_loaded, get_manifest
    ensure_loaded()
    m = get_manifest(capability_id)
    if m is None:
        raise HTTPException(404, f"Capability {capability_id} not found")
    return m.model_dump()


@app.post("/api/capabilities")
async def api_create_capability(body: dict[str, Any]):
    from src.tool_gateway.models.manifest import CapabilityManifest
    from src.tool_gateway.registry.store import get_manifest, manifest_path, save_manifest
    try:
        manifest = CapabilityManifest.model_validate(body)
    except Exception as e:
        raise HTTPException(400, str(e))
    if manifest_path(manifest.capability_id).exists() or get_manifest(manifest.capability_id):
        raise HTTPException(409, f"Capability {manifest.capability_id} already exists")
    return save_manifest(manifest).model_dump()


@app.put("/api/capabilities/{capability_id}")
async def api_save_capability(capability_id: str, body: dict[str, Any]):
    from src.tool_gateway.models.manifest import CapabilityManifest
    from src.tool_gateway.registry.store import get_manifest, manifest_path, save_manifest
    if get_manifest(capability_id) is None and not manifest_path(capability_id).exists():
        raise HTTPException(404, f"Capability {capability_id} not found")
    body["capability_id"] = capability_id
    try:
        manifest = CapabilityManifest.model_validate(body)
    except Exception as e:
        raise HTTPException(400, str(e))
    return save_manifest(manifest).model_dump()


@app.delete("/api/capabilities/{capability_id}")
async def api_delete_capability(capability_id: str):
    from src.tool_gateway.registry.store import delete_manifest
    if not delete_manifest(capability_id):
        raise HTTPException(404, f"Capability {capability_id} not found")
    return {"deleted": capability_id}


@app.post("/api/capabilities/reload")
async def api_reload_capabilities():
    from src.tool_gateway.registry.store import list_manifests, reload_registry
    snapshot_id = reload_registry()
    return {"snapshot_id": snapshot_id, "count": len(list_manifests())}


# ── MCP ─────────────────────────────────────────────────────────

@app.get("/api/mcp/servers")
async def api_mcp_servers():
    from src.workflow_ui.mcp_config import build_mcp_status
    return build_mcp_status()


@app.get("/api/mcp/config")
async def api_mcp_config():
    """Raw servers.json for JSON editor."""
    from src.workflow_ui.mcp_config import get_raw_config_for_editor, servers_json_path
    return {
        "path": str(servers_json_path()),
        "document": get_raw_config_for_editor(),
    }


@app.put("/api/mcp/servers")
async def api_save_mcp_servers(body: dict):
    from src.workflow_ui.mcp_config import apply_mcp_save, build_mcp_status
    try:
        apply_mcp_save(body)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return build_mcp_status()


@app.put("/api/mcp/config")
async def api_save_mcp_config(body: dict):
    """Save full document from JSON editor ({version, servers})."""
    from src.workflow_ui.mcp_config import apply_mcp_save, build_mcp_status
    try:
        apply_mcp_save({"document": body.get("document", body)})
    except ValueError as e:
        raise HTTPException(400, str(e))
    return build_mcp_status()


@app.delete("/api/mcp/servers/{server_id}")
async def api_delete_mcp_server(server_id: str):
    from src.workflow_ui.mcp_config import apply_mcp_save, build_mcp_status
    apply_mcp_save({"delete": server_id})
    return build_mcp_status()


@app.post("/api/mcp/servers")
async def api_upsert_mcp_server(body: dict):
    from src.workflow_ui.mcp_config import apply_mcp_save, build_mcp_status
    try:
        apply_mcp_save({"upsert": body})
    except ValueError as e:
        raise HTTPException(400, str(e))
    return build_mcp_status()


# ── Playbooks ───────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "workflows_dir": str(get_workflows_dir())}


@app.get("/api/step-types")
async def step_types():
    from src.orchestrator.workflow_config.models import SCRIPT_CATALOG
    palette = [
        StepType.SKILL, StepType.SCRIPT,
        StepType.GATEWAY_OR, StepType.GATEWAY_AND,
        StepType.APPROVAL, StepType.WAIT_CONTEXT, StepType.END,
    ]
    return {
        "types": [
            {"type": st.value, **STEP_TYPE_META[st]}
            for st in palette
            if st in STEP_TYPE_META and not STEP_TYPE_META[st].get("hidden")
        ],
        "scripts": SCRIPT_CATALOG,
    }


@app.get("/api/templates", response_model=list[TemplateSummary])
async def api_list_templates():
    return [
        TemplateSummary(
            id=t.id, name=t.name, description=t.description, version=t.version,
            is_default=t.is_default, status=getattr(t, "status", "draft"), step_count=len(t.steps),
        )
        for t in list_templates()
    ]


@app.get("/api/templates/default")
async def api_get_default():
    try:
        return get_default_template().model_dump()
    except FileNotFoundError:
        raise HTTPException(404, "No templates configured")


@app.get("/api/templates/{template_id}")
async def api_get_template(template_id: str):
    try:
        t = get_template(template_id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if t is None:
        raise HTTPException(404, f"Template {template_id} not found")
    return t.model_dump()


@app.get("/api/templates/{template_id}/yaml")
async def api_get_template_yaml(template_id: str):
    try:
        t = get_template(template_id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if t is None:
        raise HTTPException(404, f"Template {template_id} not found")
    return {"yaml": yaml.dump(t.model_dump(), allow_unicode=True, default_flow_style=False)}


@app.post("/api/templates")
async def api_create_template(req: CreateTemplateRequest):
    if req.clone_from:
        try:
            t = clone_template(req.clone_from, req.name)
            t.description = req.description or t.description
            return save_template(t).model_dump()
        except KeyError:
            raise HTTPException(404, f"Source template {req.clone_from} not found")

    from src.orchestrator.workflow_config.skeleton import build_process_skeleton

    new_id = f"playbook-{uuid.uuid4().hex[:8]}"
    # Placeholder skill inside playbook body — user replaces/extends
    body_skill = WorkflowStepConfig(
        id="step-scenario",
        type=StepType.SKILL,
        label="General",
        skill_id="general",
        output_key="artifact",
        description="Пользовательский сценарий (редактируйте внутри Start/End Playbook)",
        config={"timeout_minutes": 15},
        position={"x": 520, "y": 650},
    )
    template = build_process_skeleton(
        template_id=new_id,
        name=req.name,
        description=req.description or "",
        body_steps=[body_skill],
        body_edges=[],
        first_body_id=body_skill.id,
        last_body_id=body_skill.id,
        settings=WorkflowSettings(),
        status="draft",
    )
    return save_template(template).model_dump()


@app.put("/api/templates/{template_id}")
async def api_update_template(template_id: str, body: dict[str, Any]):
    existing = get_template(template_id)
    if existing is None:
        raise HTTPException(404, f"Template {template_id} not found")
    body["id"] = template_id
    if existing.is_default:
        body["is_default"] = True
    for step in body.get("steps", []):
        if step.get("type") == "script" and not step.get("script_id"):
            step["script_id"] = step.get("system_handler") or step.get("tool_id")
    try:
        template = WorkflowTemplate.model_validate(body)
    except Exception as e:
        raise HTTPException(400, str(e))
    template.version = existing.version + 1
    return save_template(template).model_dump()


@app.delete("/api/templates/{template_id}")
async def api_delete_template(template_id: str):
    existing = get_template(template_id)
    if existing is None:
        raise HTTPException(404, f"Template {template_id} not found")
    if existing.is_default:
        raise HTTPException(
            400,
            "Нельзя удалить default playbook. Сначала назначьте другой playbook default.",
        )
    if not delete_template(template_id):
        raise HTTPException(404, f"Template {template_id} not found")
    return {"deleted": template_id}


@app.post("/api/templates/{template_id}/set-default")
async def api_set_default(template_id: str):
    try:
        return set_default_template(template_id).model_dump()
    except KeyError:
        raise HTTPException(404, f"Template {template_id} not found")


@app.post("/api/templates/{template_id}/clone")
async def api_clone(template_id: str, name: Optional[str] = None):
    try:
        return clone_template(template_id, name).model_dump()
    except KeyError:
        raise HTTPException(404, f"Template {template_id} not found")


@app.post("/api/templates/{template_id}/validate", response_model=ValidateResponse)
async def api_validate(template_id: str):
    from src.orchestrator.workflow_config.validation import collect_graph_errors

    t = get_template(template_id)
    if t is None:
        raise HTTPException(404, f"Template {template_id} not found")
    errors: list[str] = []
    try:
        WorkflowTemplate.model_validate(t.model_dump())
    except Exception as e:
        errors.append(str(e))
    errors.extend(collect_graph_errors(t))
    # de-dupe while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for e in errors:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    order = [s.id for s in topological_order(t)]
    return ValidateResponse(
        valid=len(uniq) == 0,
        execution_order=order,
        errors=uniq,
    )


@app.post("/api/templates/{template_id}/publish")
async def api_publish_template(template_id: str):
    from src.orchestrator.workflow_config.validation import collect_graph_errors

    t = get_template(template_id)
    if t is None:
        raise HTTPException(404, f"Template {template_id} not found")
    errors = collect_graph_errors(t)
    if errors:
        raise HTTPException(400, detail="; ".join(errors))
    t.status = "published"
    return save_template(t).model_dump()


@app.get("/api/config")
async def api_config():
    return {
        "temporal_ui_url": TEMPORAL_UI_URL,
        "temporal_host": TEMPORAL_HOST,
        "platform_name": os.environ.get("PLATFORM_NAME", "AI PDLC Platform"),
        "planes": ["build", "run", "govern"],
        "product_model": "governed_ai_delivery_v2",
    }


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>Workflow UI static files not found</h1>", status_code=500)


def main():
    import uvicorn
    port = int(os.environ.get("WORKFLOW_UI_PORT", "8092"))
    reload = os.environ.get("WORKFLOW_UI_RELOAD", "").strip().lower() in ("1", "true", "yes")
    if reload:
        uvicorn.run(
            "src.workflow_ui.main:app",
            host="0.0.0.0",
            port=port,
            reload=True,
            reload_dirs=["/app/src"],
        )
    else:
        uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
