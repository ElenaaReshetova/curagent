"""Control Plane + Runtime Plane API (/api/v1)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from src.platform import store
from src.platform.rules import service as rules_svc
from src.platform.knowledge import service as knowledge_svc
from src.platform.runtime_profiles import service as runtime_profiles_svc
from src.platform.executions import service as executions_svc
from src.platform.human_checkpoints import service as checkpoints_svc
from src.platform.controls import service as controls_svc
from src.platform.integrations import service as integrations_svc
from src.platform.help import service as help_svc
from src.platform import mcp_inventory
from src.platform.domain.models import (
    CapabilityDef,
    KnowledgeSpace,
    RuleSet,
    RuntimeProfile,
    SkillInterface,
)

logger = logging.getLogger(__name__)
from src.platform.policy_eval import validate_policy_pack

router = APIRouter(prefix="/api/v1", tags=["platform"])


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class ActivateResponse(BaseModel):
    id: str
    status: str


def _activate(entity: Any, saver) -> Any:
    entity.status = "active"
    entity.updated_at = datetime.utcnow()
    return saver(entity)


def _register_crud(
    path: str,
    collection_key: str,
    label: str,
    model: type[BaseModel],
    list_fn,
    get_fn,
    save_fn,
    delete_fn,
) -> None:
    async def list_items():
        return {collection_key: [item.model_dump(mode="json") for item in list_fn()]}

    async def get_item(entity_id: str):
        item = get_fn(entity_id)
        if not item:
            raise HTTPException(404, f"{label} not found")
        return item.model_dump(mode="json")

    async def create_item(body: dict):
        data = dict(body)
        data.pop("id", None)
        return save_fn(model.model_validate(data)).model_dump(mode="json")

    async def update_item(entity_id: str, body: dict):
        existing = get_fn(entity_id)
        if not existing:
            raise HTTPException(404, f"{label} not found")
        data = {**existing.model_dump(mode="json"), **body, "id": str(existing.id)}
        return save_fn(model.model_validate(data)).model_dump(mode="json")

    async def delete_item(entity_id: str):
        if not delete_fn(entity_id):
            raise HTTPException(404, f"{label} not found")
        return {"ok": True}

    router.add_api_route(path, list_items, methods=["GET"], name=f"list_{collection_key}")
    router.add_api_route(path, create_item, methods=["POST"], name=f"create_{collection_key}")
    router.add_api_route(f"{path}/{{entity_id}}", get_item, methods=["GET"], name=f"get_{collection_key}")
    router.add_api_route(f"{path}/{{entity_id}}", update_item, methods=["PUT"], name=f"update_{collection_key}")
    router.add_api_route(f"{path}/{{entity_id}}", delete_item, methods=["DELETE"], name=f"delete_{collection_key}")


@router.get("/agents")
async def agents_list():
    return {"agents": [item.model_dump(mode="json") for item in store.list_agents()]}


@router.get("/agents/{agent_id}")
async def agents_get(agent_id: str):
    item = store.get_agent(agent_id)
    if not item:
        raise HTTPException(404, "Agent not found")
    return item.model_dump(mode="json")


_register_crud(
    "/capabilities", "capabilities", "Capability", CapabilityDef,
    store.list_capabilities, store.get_capability, store.save_capability, store.delete_capability,
)


@router.get("/mcp/servers")
async def mcp_servers_list():
    return {"servers": mcp_inventory.list_mcp_servers()}


@router.get("/mcp/servers/{server_id}")
async def mcp_servers_get(server_id: str):
    server = next((item for item in mcp_inventory.list_mcp_servers() if item["id"] == server_id), None)
    if not server:
        raise HTTPException(404, "MCP server not found")
    return {**server, "capabilities": mcp_inventory.capabilities_for_mcp_server(server_id)}


@router.get("/capability-manifests")
async def capability_manifests_list():
    return {"manifests": mcp_inventory.list_capability_manifests()}


@router.get("/capability-manifests/{capability_id}")
async def capability_manifest_get(capability_id: str):
    manifest = mcp_inventory.get_capability_manifest(capability_id)
    if not manifest:
        raise HTTPException(404, "Capability manifest not found")
    return manifest



from src.platform.api_routes import overview as overview_routes
from src.platform.api_routes import skill_interfaces as skill_interfaces_routes
from src.platform.api_routes import skills as skills_routes
from src.platform.api_routes import scenarios as scenarios_routes
from src.platform.api_routes import graphs as graphs_routes

router.include_router(overview_routes.router)
router.include_router(skill_interfaces_routes.router)
router.include_router(skills_routes.router)
router.include_router(scenarios_routes.router)
router.include_router(graphs_routes.router)


@router.post("/runtime-profiles/{profile_id}/validate", response_model=ValidateResponse)
async def runtime_profiles_validate(profile_id: str):
    try:
        report = runtime_profiles_svc.validate_profile(profile_id)
    except KeyError:
        profile = store.get_runtime_profile(profile_id)
        if not profile:
            raise HTTPException(404, "Runtime profile not found")
        errors: list[str] = []
        if not profile.key:
            errors.append("key required")
        if not profile.model:
            errors.append("model required")
        if profile.provider == "qwen" and not profile.sandbox_config:
            errors.append("qwen provider requires sandbox_config")
        return ValidateResponse(valid=not errors, errors=errors)
    return ValidateResponse(
        valid=report.get("valid", False),
        errors=[e.get("message", str(e)) if isinstance(e, dict) else str(e) for e in report.get("errors", [])],
    )


@router.post("/runtime-profiles/{profile_id}/test")
async def runtime_profiles_test(profile_id: str):
    try:
        return runtime_profiles_svc.test_connection(profile_id)
    except KeyError:
        profile = store.get_runtime_profile(profile_id)
        if not profile:
            raise HTTPException(404, "Runtime profile not found")
        return {
            "ok": True,
            "profile": profile.key,
            "provider": profile.provider,
            "model": profile.model,
            "message": "Connectivity stub OK (legacy)",
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Knowledge Spaces ───────────────────────────────────────────

@router.get("/knowledge-spaces")
async def knowledge_spaces_list(
    search: str = "",
    type: str = "",
    status: str = "",
):
    items = knowledge_svc.catalog_items(search=search, space_type=type, status=status)
    return {
        "knowledge_spaces": [i.model_dump(mode="json") for i in items],
        "metrics": knowledge_svc.metrics().model_dump(mode="json"),
    }


@router.get("/knowledge-spaces/metrics")
async def knowledge_spaces_metrics():
    return knowledge_svc.metrics().model_dump(mode="json")


@router.get("/knowledge-spaces/{space_id}")
async def knowledge_spaces_get(space_id: str):
    try:
        return knowledge_svc.detail(space_id)
    except KeyError:
        space = store.get_knowledge_space(space_id)
        if not space:
            raise HTTPException(404, "Knowledge Space not found")
        return space.model_dump(mode="json")


@router.post("/knowledge-spaces")
async def knowledge_spaces_create(body: dict):
    # Legacy flat KnowledgeSpace create
    if body.get("key") and body.get("source_bindings") is not None and "space_type" not in body and "type" not in body:
        data = dict(body)
        data.pop("id", None)
        return store.save_knowledge_space(KnowledgeSpace.model_validate(data)).model_dump(mode="json")
    try:
        return knowledge_svc.create_space(body)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/knowledge-spaces/{space_id}")
async def knowledge_spaces_update(space_id: str, body: dict):
    try:
        return knowledge_svc.update_space(space_id, body)
    except KeyError:
        pass
    except ValueError as e:
        raise HTTPException(400, str(e))
    existing = store.get_knowledge_space(space_id)
    if existing:
        data = {**existing.model_dump(mode="json"), **body, "id": str(existing.id)}
        return store.save_knowledge_space(KnowledgeSpace.model_validate(data)).model_dump(mode="json")
    raise HTTPException(404, "Knowledge Space not found")


@router.post("/knowledge-spaces/{space_id}/activate")
async def knowledge_spaces_activate(space_id: str):
    try:
        return knowledge_svc.activate_space(space_id)
    except KeyError:
        raise HTTPException(404, "Knowledge Space not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/knowledge-spaces/{space_id}/disable")
async def knowledge_spaces_disable(space_id: str):
    try:
        return knowledge_svc.disable_space(space_id)
    except KeyError:
        raise HTTPException(404, "Knowledge Space not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/knowledge-spaces/{space_id}")
async def knowledge_spaces_delete(space_id: str):
    try:
        return knowledge_svc.delete_space(space_id)
    except KeyError:
        pass
    if store.delete_knowledge_space(space_id):
        return {"ok": True}
    raise HTTPException(404, "Knowledge Space not found")


@router.get("/knowledge-spaces/{space_id}/sources")
async def knowledge_sources_list(space_id: str):
    try:
        detail = knowledge_svc.detail(space_id)
    except KeyError:
        raise HTTPException(404, "Knowledge Space not found")
    return {"sources": detail["sources"]}


@router.post("/knowledge-spaces/{space_id}/sources")
async def knowledge_sources_add(space_id: str, body: dict):
    try:
        return knowledge_svc.add_source(space_id, body)
    except KeyError:
        raise HTTPException(404, "Knowledge Space not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/knowledge-spaces/{space_id}/sources/{source_id}")
async def knowledge_sources_update(space_id: str, source_id: str, body: dict):
    try:
        return knowledge_svc.update_source(space_id, source_id, body)
    except KeyError as e:
        raise HTTPException(404, e.args[0] if e.args else "Not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/knowledge-spaces/{space_id}/sources/{source_id}")
async def knowledge_sources_delete(space_id: str, source_id: str):
    try:
        return knowledge_svc.delete_source(space_id, source_id)
    except KeyError as e:
        raise HTTPException(404, e.args[0] if e.args else "Not found")


@router.post("/knowledge-spaces/{space_id}/search")
@router.post("/knowledge-spaces/{space_id}/search/explain")
async def knowledge_search(space_id: str, body: dict | None = None):
    try:
        return knowledge_svc.search_playground(space_id, body or {})
    except KeyError:
        raise HTTPException(404, "Knowledge Space not found")


@router.get("/knowledge-spaces/{space_id}/health")
@router.post("/knowledge-spaces/{space_id}/health/check")
async def knowledge_health(space_id: str):
    try:
        return knowledge_svc.health_check(space_id)
    except KeyError:
        raise HTTPException(404, "Knowledge Space not found")


# ── Runtime Profiles (versioned module) ──────────────────────────

@router.get("/runtime-profiles")
async def runtime_profiles_list(
    search: str = "",
    type: str = "",
    provider: str = "",
    status: str = "",
):
    items = runtime_profiles_svc.catalog_items(
        search=search, profile_type=type, provider=provider, status=status,
    )
    return {
        "runtime_profiles": [i.model_dump(mode="json") for i in items],
        "metrics": runtime_profiles_svc.metrics().model_dump(mode="json"),
    }


@router.get("/runtime-profiles/metrics")
async def runtime_profiles_metrics():
    return runtime_profiles_svc.metrics().model_dump(mode="json")


@router.post("/runtime-profiles/resolve")
@router.post("/runtime-profiles/resolve/preview")
async def runtime_profiles_resolve(body: dict | None = None):
    return runtime_profiles_svc.resolve_preview(body or {})


@router.get("/runtime-profiles/{profile_id}")
async def runtime_profiles_get(profile_id: str):
    try:
        return runtime_profiles_svc.detail(profile_id)
    except KeyError:
        profile = store.get_runtime_profile(profile_id)
        if not profile:
            raise HTTPException(404, "Runtime profile not found")
        return profile.model_dump(mode="json")


@router.post("/runtime-profiles")
async def runtime_profiles_create(body: dict):
    if body.get("key") and body.get("provider") in ("lm_studio", "gigachat", "qwen", "openai_compatible"):
        data = dict(body)
        data.pop("id", None)
        return store.save_runtime_profile(RuntimeProfile.model_validate(data)).model_dump(mode="json")
    try:
        return runtime_profiles_svc.create_profile(body)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/runtime-profiles/{profile_id}")
@router.patch("/runtime-profiles/{profile_id}")
async def runtime_profiles_update(profile_id: str, body: dict):
    # Prefer versioned store (draft) — legacy flat catalog is a mirror only.
    try:
        if runtime_profiles_svc.get_record(profile_id):
            result = runtime_profiles_svc.update_draft(profile_id, body or {})
            # Keep legacy mirror in sync so Overview / old clients see the same model
            try:
                existing = store.get_runtime_profile(profile_id)
                if existing and body:
                    data = {**existing.model_dump(mode="json"), **{
                        k: body[k] for k in ("name", "description", "model", "provider", "generation_config")
                        if k in body
                    }, "id": str(existing.id)}
                    if "model" in body:
                        data["model"] = body["model"]
                    store.save_runtime_profile(RuntimeProfile.model_validate(data))
            except Exception:
                pass
            return result
    except KeyError:
        pass
    existing = store.get_runtime_profile(profile_id)
    if existing:
        data = {**existing.model_dump(mode="json"), **body, "id": str(existing.id)}
        return store.save_runtime_profile(RuntimeProfile.model_validate(data)).model_dump(mode="json")
    try:
        return runtime_profiles_svc.update_draft(profile_id, body or {})
    except KeyError:
        raise HTTPException(404, "Runtime profile not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/runtime-profiles/{profile_id}/draft")
async def runtime_profiles_create_draft(profile_id: str):
    try:
        return runtime_profiles_svc.create_draft(profile_id)
    except KeyError:
        raise HTTPException(404, "Runtime profile not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/runtime-profiles/{profile_id}/versions/{version_id}/activate")
@router.post("/runtime-profiles/{profile_id}/activate")
async def runtime_profiles_activate(profile_id: str, version_id: str | None = None):
    try:
        return runtime_profiles_svc.activate_version(profile_id, version_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/runtime-profiles/{profile_id}")
async def runtime_profiles_delete(profile_id: str):
    try:
        return runtime_profiles_svc.delete_profile(profile_id)
    except KeyError:
        pass
    except ValueError as e:
        raise HTTPException(400, str(e))
    if store.delete_runtime_profile(profile_id):
        return {"ok": True}
    raise HTTPException(404, "Runtime profile not found")


@router.get("/runtime-profiles/{profile_id}/versions")
async def runtime_profiles_versions(profile_id: str):
    rec = runtime_profiles_svc.get_record(profile_id)
    if not rec:
        raise HTTPException(404, "Runtime profile not found")
    return {"versions": [v.model_dump(mode="json") for v in runtime_profiles_svc.list_versions(str(rec.id))]}


# ── Rules (versioned module) ───────────────────────────────────

@router.get("/rules")
async def rules_list(
    search: str = "",
    category: str = "",
    scope: str = "",
    status: str = "",
):
    items = rules_svc.catalog_items(search=search, category=category, scope=scope, status=status)
    return {
        "rules": [i.model_dump(mode="json") for i in items],
        "metrics": rules_svc.metrics().model_dump(mode="json"),
    }


@router.get("/rules/metrics")
async def rules_metrics():
    return rules_svc.metrics().model_dump(mode="json")


@router.post("/rules/resolve")
@router.post("/rules/resolve/preview")
async def rules_resolve(body: dict | None = None):
    return rules_svc.resolve_preview(body or {})


@router.get("/rules/{rule_id}")
async def rules_get(rule_id: str):
    try:
        return rules_svc.detail(rule_id)
    except KeyError:
        rule = store.get_rule(rule_id)
        if not rule:
            raise HTTPException(404, "Rule not found")
        return rule.model_dump(mode="json")


@router.get("/rules/{rule_id}/usage")
async def rules_usage(rule_id: str):
    try:
        return rules_svc.usage(rule_id)
    except KeyError:
        raise HTTPException(404, "Rule not found")


@router.post("/rules")
async def rules_create(body: dict):
    # Legacy RuleSet create
    if body.get("key") and body.get("content_md") is not None and "category" not in body:
        data = dict(body)
        data.pop("id", None)
        return store.save_rule(RuleSet.model_validate(data)).model_dump(mode="json")
    try:
        return rules_svc.create_rule(body)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/rules/{rule_id}")
async def rules_update(rule_id: str, body: dict):
    try:
        return rules_svc.update_rule(rule_id, body)
    except KeyError:
        pass
    except ValueError as e:
        raise HTTPException(400, str(e))
    existing = store.get_rule(rule_id)
    if existing:
        data = {**existing.model_dump(mode="json"), **body, "id": str(existing.id)}
        return store.save_rule(RuleSet.model_validate(data)).model_dump(mode="json")
    raise HTTPException(404, "Rule not found")


@router.delete("/rules/{rule_id}")
async def rules_delete(rule_id: str):
    try:
        return rules_svc.delete_rule(rule_id)
    except KeyError:
        pass
    except ValueError as e:
        raise HTTPException(400, str(e))
    if store.delete_rule(rule_id):
        return {"ok": True}
    raise HTTPException(404, "Rule not found")


@router.get("/rules/{rule_id}/versions")
async def rules_versions(rule_id: str):
    rec = rules_svc.get_record(rule_id)
    if not rec:
        raise HTTPException(404, "Rule not found")
    return {"versions": [v.model_dump(mode="json") for v in rules_svc.list_versions(str(rec.id))]}


@router.post("/rules/{rule_id}/versions/{version_id}/validate")
async def rules_version_validate(rule_id: str, version_id: str):
    try:
        return rules_svc.validate_rule_version(rule_id, version_id)
    except KeyError:
        raise HTTPException(404, "Version not found")


@router.post("/rules/{rule_id}/versions/{version_id}/publish")
async def rules_version_publish(rule_id: str, version_id: str):
    try:
        return rules_svc.publish_version(rule_id, version_id)
    except KeyError:
        raise HTTPException(404, "Version not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/rules/{rule_id}/versions/{version_id}/content")
async def rules_save_content(rule_id: str, version_id: str, body: dict):
    try:
        ver = rules_svc.save_content(
            rule_id,
            version_id,
            body.get("content") or body.get("content_markdown") or "",
            if_match=str(body["revision"]) if body.get("revision") is not None else None,
        )
    except KeyError:
        raise HTTPException(404, "Version not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {
        "revision": ver.revision,
        "checksum": ver.checksum,
        "validation": ver.validation_report,
        "content_markdown": ver.content_markdown,
    }


# ── Controls (versioned module) ────────────────────────────────

@router.get("/controls")
async def controls_list(
    search: str = "",
    type: str = "",
    severity: str = "",
    status: str = "",
):
    items = controls_svc.catalog_items(
        search=search, control_type=type, severity=severity, status=status,
    )
    return {
        "controls": [i.model_dump(mode="json") for i in items],
        "metrics": controls_svc.metrics().model_dump(mode="json"),
    }


@router.get("/controls/metrics")
async def controls_metrics():
    return controls_svc.metrics().model_dump(mode="json")


@router.post("/controls/resolve")
@router.post("/controls/resolve/preview")
async def controls_resolve(body: dict | None = None):
    return controls_svc.resolve_preview(body or {})


@router.get("/controls/{control_id}")
async def controls_get(control_id: str):
    try:
        return controls_svc.detail(control_id)
    except KeyError:
        control = store.get_control(control_id)
        if not control:
            raise HTTPException(404, "Control not found")
        return control.model_dump(mode="json")


@router.post("/controls")
async def controls_create(body: dict):
    try:
        return controls_svc.create_control(body)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/controls/{control_id}")
async def controls_update(control_id: str, body: dict | None = None):
    try:
        return controls_svc.update_draft(control_id, body or {})
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/controls/{control_id}")
async def controls_delete(control_id: str):
    try:
        return controls_svc.delete_control(control_id)
    except KeyError:
        pass
    except ValueError as e:
        raise HTTPException(400, str(e))
    if store.delete_control(control_id):
        return {"ok": True}
    raise HTTPException(404, "Control not found")


@router.post("/controls/{control_id}/draft")
async def controls_create_draft(control_id: str):
    try:
        return controls_svc.create_draft(control_id)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/controls/{control_id}/validate", response_model=ValidateResponse)
async def controls_validate(control_id: str):
    if controls_svc.get_record(control_id):
        result = controls_svc.validate_control(control_id)
        return ValidateResponse(valid=result["valid"], errors=result["errors"])
    control = store.get_control(control_id)
    if not control:
        raise HTTPException(404, "Control not found")
    errors = validate_policy_pack(control.rules)
    if not control.locked_steps and control.enforcement == "hard":
        errors.append("hard control requires at least one locked step")
    return ValidateResponse(valid=not errors, errors=errors)


@router.post("/controls/{control_id}/activate", response_model=ActivateResponse)
async def controls_activate(control_id: str):
    if controls_svc.get_record(control_id):
        try:
            rec = controls_svc.activate_control(control_id)
            return ActivateResponse(id=str(rec.id), status=rec.status)
        except ValueError as e:
            raise HTTPException(400, detail=str(e))
    control = store.get_control(control_id)
    if not control:
        raise HTTPException(404, "Control not found")
    result = await controls_validate(control_id)
    if not result.valid:
        raise HTTPException(400, detail="; ".join(result.errors))
    control = _activate(control, store.save_control)
    return ActivateResponse(id=str(control.id), status=control.status)


@router.post("/controls/{control_id}/test")
async def controls_test(control_id: str, body: dict | None = None):
    try:
        return controls_svc.test_control(control_id, body)
    except KeyError:
        raise HTTPException(404, "Control not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Integrations (MCP / A2A / ACP protocol connections) ─────────

@router.get("/integrations")
async def integrations_list(
    search: str = "",
    protocol: str = "",
    status: str = "",
):
    result = integrations_svc.catalog(search=search, protocol=protocol, status=status)
    return result.model_dump(mode="json")


@router.get("/integrations/config")
async def integrations_config():
    """Standard config.json document: mcpServers + A2A servers + ACP agent_servers."""
    from src.workflow_ui.mcp_config import servers_json_path

    return {
        "path": {
            "mcp": str(servers_json_path()),
            "a2a": str(integrations_svc.a2a_config_path()),
            "acp": str(integrations_svc.acp_config_path()),
        },
        "document": integrations_svc.build_full_config_document(),
        "mcp": integrations_svc.build_mcp_servers_document(),
        "a2a": integrations_svc.load_a2a_document(),
        "acp": integrations_svc.load_acp_document(),
    }


@router.put("/integrations/config")
async def integrations_config_save(body: dict):
    try:
        document = body.get("document") if isinstance(body.get("document"), dict) else body
        return {
            "document": integrations_svc.apply_full_config_document(document),
            "mcp": integrations_svc.build_mcp_servers_document(),
            "a2a": integrations_svc.load_a2a_document(),
            "acp": integrations_svc.load_acp_document(),
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/integrations/metrics")
async def integrations_metrics():
    return integrations_svc.metrics().model_dump(mode="json")


@router.get("/integrations/{integration_id:path}")
async def integrations_get(integration_id: str):
    try:
        return integrations_svc.detail(integration_id).model_dump(mode="json")
    except KeyError:
        raise HTTPException(404, "Integration not found")


@router.post("/integrations")
async def integrations_create(body: dict):
    try:
        return integrations_svc.upsert_connection(body).model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/integrations/{integration_id:path}")
async def integrations_update(integration_id: str, body: dict):
    try:
        protocol, key = integrations_svc._parse_id(integration_id)
        payload = {**body, "protocol": body.get("protocol") or protocol, "key": body.get("key") or key}
        return integrations_svc.upsert_connection(payload).model_dump(mode="json")
    except KeyError:
        raise HTTPException(404, "Integration not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/integrations/{integration_id:path}")
async def integrations_delete(integration_id: str):
    try:
        integrations_svc.delete_connection(integration_id)
        return {"deleted": integration_id}
    except KeyError:
        raise HTTPException(404, "Integration not found")


# ── Contextual help registry ─────────────────────────────────

@router.get("/help")
async def help_list(locale: str = "ru-RU", prefix: str = ""):
    catalog = help_svc.list_concepts(locale=locale, prefix=prefix)
    return catalog.model_dump(mode="json", by_alias=True)


@router.get("/help/{concept_key:path}")
async def help_get(concept_key: str, locale: str = "ru-RU"):
    concept = help_svc.get_concept(concept_key, locale=locale)
    if not concept:
        raise HTTPException(404, f"Help concept not found: {concept_key}")
    return concept.model_dump(mode="json", by_alias=True)


# ── Audit ─────────────────────────────────────────────────────
@router.get("/audit")
async def audit_list(limit: int = 100):
    return {"audit": [a.model_dump(mode="json") for a in store.list_audit()[:limit]]}


# ── Executions (versioned module) ──────────────────────────────

@router.get("/executions")
async def executions_list(
    response: Response,
    search: str = "",
    status: str = "",
    type: str = "",
    risk: str = "",
):
    response.headers["Cache-Control"] = "no-store"
    items = executions_svc.catalog_items(
        search=search, status=status, execution_type=type, risk=risk,
    )
    return {
        "executions": [i.model_dump(mode="json") for i in items],
        "metrics": executions_svc.metrics().model_dump(mode="json"),
    }


@router.get("/executions/metrics")
async def executions_metrics():
    return executions_svc.metrics().model_dump(mode="json")


@router.get("/executions/{execution_id}")
async def executions_get(execution_id: str, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return executions_svc.detail(execution_id)
    except KeyError:
        ex = store.get_execution(execution_id)
        if not ex:
            raise HTTPException(404, "Execution not found")
        return ex.model_dump(mode="json", exclude={"run_contract"})


@router.post("/executions")
async def executions_create(body: dict):
    try:
        return executions_svc.create_execution(body)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/executions/{execution_id}/pause")
async def executions_pause(execution_id: str):
    try:
        return executions_svc.status_response(execution_id, "PAUSED", "Paused by operator")
    except KeyError:
        raise HTTPException(404, "Execution not found")


@router.post("/executions/{execution_id}/resume")
async def executions_resume(execution_id: str):
    try:
        return executions_svc.status_response(execution_id, "RUNNING", "Resumed by operator")
    except KeyError:
        raise HTTPException(404, "Execution not found")


@router.post("/executions/{execution_id}/cancel")
async def executions_cancel(execution_id: str):
    try:
        return executions_svc.status_response(execution_id, "CANCELLED", "Cancelled by operator")
    except KeyError:
        raise HTTPException(404, "Execution not found")


@router.post("/executions/{execution_id}/retry")
async def executions_retry(execution_id: str):
    try:
        detail = executions_svc.detail(execution_id)
        ex = detail["execution"]
        if ex.get("status") != "FAILED":
            raise HTTPException(400, "Retry only available for failed executions")
        return executions_svc.set_status(execution_id, "RUNNING", "Retry requested")
    except KeyError:
        raise HTTPException(404, "Execution not found")


# ── Runtime (legacy detail endpoints) ────────────────────────


@router.post("/executions/{execution_id}/replan")
async def executions_replan(execution_id: str):
    ex = store.get_execution(execution_id)
    if not ex:
        raise HTTPException(404, "Execution not found")
    ex.next_proposed_action = "analyze_external_work_item"
    ex.reason = "Manual replan requested"
    ex.status = "running"
    ex.audit_trail.append({
        "at": datetime.utcnow().isoformat(),
        "action": "replan",
        "by": "admin",
    })
    return store.save_execution(ex).model_dump(mode="json")


@router.get("/executions/{execution_id}/contract")
async def executions_contract(execution_id: str):
    rec = executions_svc.get_record(execution_id)
    if rec:
        return {
            "execution_id": rec.id,
            "version": 1,
            "contract": rec.snapshot or rec.runtime_effective,
        }
    ex = store.get_execution(execution_id)
    if not ex:
        raise HTTPException(404, "Execution not found")
    return {
        "execution_id": ex.id,
        "version": ex.contract_version,
        "contract": ex.run_contract or ex.contract_summary,
    }


@router.get("/executions/{execution_id}/case-context")
async def executions_case_context(execution_id: str):
    rec = executions_svc.get_record(execution_id)
    if rec:
        return {"execution_id": rec.id, "case_context": rec.snapshot}
    ex = store.get_execution(execution_id)
    if not ex:
        raise HTTPException(404, "Execution not found")
    return {"execution_id": ex.id, "case_context": ex.case_context}


@router.get("/executions/{execution_id}/artifact")
async def executions_artifact(execution_id: str):
    rec = executions_svc.get_record(execution_id)
    if rec:
        facets = [
            {"key": a.name, "status": a.status.lower(), "summary": f"{a.version} · {a.status}"}
            for a in rec.artifacts
        ]
        return {"facets": facets, "open_questions": [], "conflicts": []}
    ex = store.get_execution(execution_id)
    if not ex:
        raise HTTPException(404, "Execution not found")
    return {
        "facets": [f.model_dump(mode="json") for f in ex.artifact_facets],
        "open_questions": ex.open_questions,
        "conflicts": ex.conflicts,
    }


@router.get("/executions/{execution_id}/artifacts")
async def executions_artifacts(execution_id: str):
    return await executions_artifact(execution_id)


@router.get("/executions/{execution_id}/plan")
async def executions_plan(execution_id: str):
    rec = executions_svc.get_record(execution_id)
    if rec:
        plan = [
            {"step": i + 1, "operator_key": s.key, "title": s.name, "status": s.status.lower()}
            for i, s in enumerate(rec.stage_runs)
        ]
        return {"execution_id": rec.id, "plan": plan}
    ex = store.get_execution(execution_id)
    if not ex:
        raise HTTPException(404, "Execution not found")
    return {"execution_id": ex.id, "plan": ex.plan}


@router.get("/executions/{execution_id}/evidence")
async def executions_evidence(execution_id: str):
    rec = executions_svc.get_record(execution_id)
    if rec:
        return {
            "evidence": [
                {
                    "id": f"ev-{i}",
                    "source_type": e.source.split(" · ")[0].lower() if " · " in e.source else "other",
                    "source_ref": e.title,
                    "summary": e.title,
                    "trust_class": "A",
                    "score": e.score,
                }
                for i, e in enumerate(rec.evidence)
            ]
        }
    ex = store.get_execution(execution_id)
    if not ex:
        raise HTTPException(404, "Execution not found")
    return {"evidence": [e.model_dump(mode="json") for e in ex.evidence]}


@router.get("/executions/{execution_id}/operator-runs")
async def executions_operator_runs(execution_id: str):
    rec = executions_svc.get_record(execution_id)
    if rec:
        return {
            "operator_runs": [
                {"id": s.key, "operator_key": s.key, "status": s.status.lower(), "summary": s.name}
                for s in rec.stage_runs
            ]
        }
    ex = store.get_execution(execution_id)
    if not ex:
        raise HTTPException(404, "Execution not found")
    return {"operator_runs": [r.model_dump(mode="json") for r in ex.operator_runs]}


@router.get("/executions/{execution_id}/skill-runs")
async def executions_skill_runs(execution_id: str):
    rec = executions_svc.get_record(execution_id)
    if rec:
        runs = []
        if rec.current_skill:
            runs.append({
                "id": f"sk-{rec.id}",
                "skill_key": rec.current_skill,
                "status": "running" if rec.status == "RUNNING" else rec.status.lower(),
                "summary": rec.current_activity,
            })
        return {"skill_runs": runs}
    ex = store.get_execution(execution_id)
    if not ex:
        raise HTTPException(404, "Execution not found")
    return {"skill_runs": ex.skill_runs}


@router.get("/executions/{execution_id}/events")
async def executions_events(execution_id: str):
    rec = executions_svc.get_record(execution_id)
    if rec:
        return {
            "events": [
                {
                    "event_type": t.title,
                    "occurred_at": t.at,
                    "payload": {"detail": t.detail, "actor": t.actor},
                }
                for t in rec.timeline
            ]
        }
    events = [e for e in store.list_events() if e.correlation_id == execution_id]
    return {"events": [e.model_dump(mode="json") for e in events]}


@router.get("/human-checkpoints")
async def human_checkpoints_list(
    search: str = "",
    type: str = "",
    priority: str = "",
    status: str = "",
    view: str = "all",
):
    items = checkpoints_svc.catalog_items(
        search=search,
        checkpoint_type=type,
        priority=priority,
        status=status,
        view=view,
    )
    return {
        "checkpoints": [i.model_dump(mode="json") for i in items],
        "metrics": checkpoints_svc.metrics().model_dump(mode="json"),
    }


@router.get("/human-checkpoints/{checkpoint_id}")
async def human_checkpoints_get(checkpoint_id: str):
    try:
        return checkpoints_svc.detail(checkpoint_id)
    except KeyError:
        raise HTTPException(404, "Checkpoint not found")


@router.post("/human-checkpoints/claim-next")
async def human_checkpoints_claim_next(body: Optional[dict] = None):
    try:
        return checkpoints_svc.claim_next(reviewer=(body or {}).get("reviewer", "Alexey Khromov"))
    except KeyError:
        raise HTTPException(404, "No unassigned checkpoints")


@router.post("/human-checkpoints/{checkpoint_id}/claim")
async def human_checkpoints_claim(checkpoint_id: str, body: Optional[dict] = None):
    try:
        return checkpoints_svc.claim(checkpoint_id, reviewer=(body or {}).get("reviewer", "Alexey Khromov"))
    except KeyError:
        raise HTTPException(404, "Checkpoint not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/human-checkpoints/{checkpoint_id}/start-review")
async def human_checkpoints_start_review(checkpoint_id: str):
    try:
        return checkpoints_svc.start_review(checkpoint_id)
    except KeyError:
        raise HTTPException(404, "Checkpoint not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/human-checkpoints/{checkpoint_id}/decisions")
async def human_checkpoints_decide(checkpoint_id: str, body: Optional[dict] = None):
    payload = body or {}
    try:
        result = checkpoints_svc.submit_decision(
            checkpoint_id,
            decision=payload.get("decision", ""),
            comment=payload.get("comment", ""),
            structured_input=payload.get("structuredInput"),
        )
    except KeyError:
        raise HTTPException(404, "Checkpoint not found")
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Resume Temporal workflow waiting on this approval
    try:
        from src.platform.runtime_bridge import signal_temporal_decision, workflow_id_from_checkpoint

        workflow_id = workflow_id_from_checkpoint(checkpoint_id)
        if workflow_id:
            await signal_temporal_decision(
                workflow_id,
                str(payload.get("decision", "")).upper(),
                payload.get("comment", "") or "",
            )
    except Exception as exc:
        logger.warning("Temporal signal failed for checkpoint %s: %s", checkpoint_id, exc)

    return result


@router.get("/human-checkpoints/{checkpoint_id}/artifact")
async def human_checkpoints_artifact(checkpoint_id: str):
    rec = checkpoints_svc.get_record(checkpoint_id)
    if not rec:
        raise HTTPException(404, "Checkpoint not found")
    preview = (rec.artifact_preview or "").strip()
    # Fallback: execution snapshot may still hold the body when checkpoint preview was empty.
    if not preview and rec.execution_id:
        try:
            from src.platform.executions import service as executions_svc

            ex = executions_svc.get_record(rec.execution_id)
            snap = (ex.snapshot if ex else None) or {}
            preview = str(snap.get("artifact_preview") or "").strip()
        except Exception:
            preview = ""
    return {
        "artifact": {
            "name": rec.artifact_name,
            "version": rec.artifact_version,
            "preview": preview,
        }
    }


@router.get("/human-checkpoints/{checkpoint_id}/diff")
async def human_checkpoints_diff(checkpoint_id: str):
    rec = checkpoints_svc.get_record(checkpoint_id)
    if not rec:
        raise HTTPException(404, "Checkpoint not found")
    return {"changes": rec.artifact_diff}


@router.get("/human-checkpoints/{checkpoint_id}/evidence")
async def human_checkpoints_evidence(checkpoint_id: str):
    rec = checkpoints_svc.get_record(checkpoint_id)
    if not rec:
        raise HTTPException(404, "Checkpoint not found")
    return {"evidence": [e.model_dump(mode="json") for e in rec.evidence]}


@router.get("/human-checkpoints/{checkpoint_id}/controls")
async def human_checkpoints_controls(checkpoint_id: str):
    rec = checkpoints_svc.get_record(checkpoint_id)
    if not rec:
        raise HTTPException(404, "Checkpoint not found")
    return {"controls": [c.model_dump(mode="json") for c in rec.controls]}


@router.get("/human-checkpoints/{checkpoint_id}/activity")
async def human_checkpoints_activity(checkpoint_id: str):
    rec = checkpoints_svc.get_record(checkpoint_id)
    if not rec:
        raise HTTPException(404, "Checkpoint not found")
    return {"activity": [a.model_dump(mode="json") for a in rec.activity]}


@router.get("/human-checkpoints/{checkpoint_id}/audit")
async def human_checkpoints_audit(checkpoint_id: str):
    rec = checkpoints_svc.get_record(checkpoint_id)
    if not rec:
        raise HTTPException(404, "Checkpoint not found")
    return {"audit": rec.audit}


@router.get("/approvals")
async def approvals_list():
    response = await human_checkpoints_list()
    items = []
    for item in response["checkpoints"]:
        items.append({
            "id": item["id"],
            "type": item["checkpoint_type"].lower(),
            "status": "pending" if item["status"] in {"OPEN", "ASSIGNED", "IN_REVIEW", "ESCALATED"} else item["status"].lower(),
            "requested_role": item["assignee"],
            "subject": item["title"],
            "execution_id": item["execution_id"],
        })
    return {"approvals": items}


@router.get("/checkpoints")
async def checkpoints_list():
    return await human_checkpoints_list()


@router.post("/approvals/{approval_id}/approve")
async def approvals_approve(approval_id: str, body: Optional[dict] = None):
    if checkpoints_svc.get_record(approval_id):
        return checkpoints_svc.submit_decision(approval_id, "APPROVE", (body or {}).get("comment", ""))
    return _resolve_approval(approval_id, "approved", (body or {}).get("comment"))


@router.post("/approvals/{approval_id}/reject")
async def approvals_reject(approval_id: str, body: Optional[dict] = None):
    if checkpoints_svc.get_record(approval_id):
        return checkpoints_svc.submit_decision(approval_id, "REJECT", (body or {}).get("comment", ""))
    return _resolve_approval(approval_id, "rejected", (body or {}).get("comment"))


