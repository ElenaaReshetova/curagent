"""Skills versioned API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.platform.api_common import ValidateResponse
from src.platform.skills import service as skills_svc

router = APIRouter(tags=["skills"])

@router.get("/skills")
async def skills_list(
    q: str = "",
    status: str = "",
    skillType: str = "",
    interfaceKey: str = "",
):
    items = skills_svc.catalog_items(
        query=q, skill_type=skillType, status=status, interface_key=interfaceKey,
    )
    return {
        "skills": [i.model_dump(mode="json") for i in items],
        "metrics": skills_svc.metrics().model_dump(mode="json"),
    }


@router.get("/skills/metrics")
async def skills_metrics():
    return skills_svc.metrics().model_dump(mode="json")


@router.get("/skills/{skill_id}")
async def skills_get(skill_id: str):
    try:
        return skills_svc.detail(skill_id)
    except KeyError:
        raise HTTPException(404, "Skill not found")


@router.post("/skills/{skill_id}/inherit")
async def skills_inherit(skill_id: str, body: dict):
    try:
        return skills_svc.inherit_skill(skill_id, body)
    except KeyError:
        raise HTTPException(404, "Skill not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/skills")
async def skills_create(body: dict):
    try:
        return skills_svc.create_skill(body)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))


@router.put("/skills/{skill_id}")
async def skills_update(skill_id: str, body: dict):
    try:
        return skills_svc.update_skill(skill_id, body)
    except KeyError:
        raise HTTPException(404, "Skill not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/skills/{skill_id}")
async def skills_delete(skill_id: str):
    try:
        return skills_svc.delete_skill(skill_id)
    except KeyError:
        raise HTTPException(404, "Skill not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/skills/{skill_id}/validate", response_model=ValidateResponse)
async def skills_validate(skill_id: str):
    rec = skills_svc.get_record(skill_id)
    if not rec:
        raise HTTPException(404, "Skill not found")
    detail = skills_svc.detail(str(rec.id))
    current = detail.get("current_version") or {}
    if not current.get("id"):
        raise HTTPException(400, "Skill has no version to validate")
    report = skills_svc.validate_skill_version(str(rec.id), current["id"])
    errors = [e.get("message", e.get("code", "error")) for e in report.get("errors", [])]
    return ValidateResponse(valid=bool(report.get("valid")), errors=errors)


@router.get("/skills/{skill_id}/versions")
async def skills_versions(skill_id: str):
    rec = skills_svc.get_record(skill_id)
    if not rec:
        raise HTTPException(404, "Skill not found")
    return {"versions": [v.model_dump(mode="json") for v in skills_svc.list_versions(str(rec.id))]}


@router.post("/skills/{skill_id}/versions")
async def skills_create_draft(skill_id: str):
    try:
        return skills_svc.create_draft(skill_id)
    except KeyError:
        raise HTTPException(404, "Skill not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/skills/{skill_id}/versions/{version_id}")
async def skills_version_get(skill_id: str, version_id: str):
    rec = skills_svc.get_record(skill_id)
    ver = skills_svc.get_version(version_id)
    if not rec or not ver or str(ver.skill_id) != str(rec.id):
        raise HTTPException(404, "Version not found")
    return ver.model_dump(mode="json")


@router.put("/skills/{skill_id}/versions/{version_id}/files/SKILL.md")
async def skills_save_skill_md(skill_id: str, version_id: str, body: dict):
    try:
        ver = skills_svc.save_draft_content(
            skill_id,
            version_id,
            body.get("content") or body.get("skill_markdown") or "",
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
        "checksum": ver.package_checksum,
        "validation": ver.validation_report,
        "skill_markdown": ver.skill_markdown,
    }


@router.get("/skills/{skill_id}/versions/{version_id}/files")
async def skills_list_files(skill_id: str, version_id: str):
    try:
        return {"files": skills_svc.list_package_files(skill_id, version_id)}
    except KeyError:
        raise HTTPException(404, "Version not found")


@router.put("/skills/{skill_id}/versions/{version_id}/files/{file_path:path}")
async def skills_upsert_file(skill_id: str, version_id: str, file_path: str, body: dict):
    try:
        ver = skills_svc.upsert_package_entry(
            skill_id,
            version_id,
            path=file_path,
            content_text=body.get("content") or body.get("content_text") or "",
            kind=body.get("kind") or "file",
            if_match=str(body["revision"]) if body.get("revision") is not None else None,
        )
    except KeyError:
        raise HTTPException(404, "Version not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {
        "revision": ver.revision,
        "checksum": ver.package_checksum,
        "validation": ver.validation_report,
        "files": [f.model_dump(mode="json") for f in ver.files],
    }


@router.post("/skills/{skill_id}/versions/{version_id}/files")
async def skills_create_file(skill_id: str, version_id: str, body: dict):
    path = body.get("path") or ""
    try:
        ver = skills_svc.upsert_package_entry(
            skill_id,
            version_id,
            path=path,
            content_text=body.get("content") or body.get("content_text") or "",
            kind=body.get("kind") or ("folder" if str(path).endswith("/") else "file"),
            if_match=str(body["revision"]) if body.get("revision") is not None else None,
        )
    except KeyError:
        raise HTTPException(404, "Version not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {
        "revision": ver.revision,
        "checksum": ver.package_checksum,
        "validation": ver.validation_report,
        "files": [f.model_dump(mode="json") for f in ver.files],
    }


@router.post("/skills/{skill_id}/versions/{version_id}/files/move")
async def skills_move_file(skill_id: str, version_id: str, body: dict):
    try:
        ver = skills_svc.move_package_entry(
            skill_id,
            version_id,
            from_path=body.get("from_path") or body.get("from") or "",
            to_path=body.get("to_path") or body.get("to") or "",
            if_match=str(body["revision"]) if body.get("revision") is not None else None,
        )
    except KeyError as e:
        raise HTTPException(404, str(e) if "not found" in str(e).lower() else "Package entry not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {
        "revision": ver.revision,
        "checksum": ver.package_checksum,
        "validation": ver.validation_report,
        "files": [f.model_dump(mode="json") for f in ver.files],
    }


@router.delete("/skills/{skill_id}/versions/{version_id}/files/{file_path:path}")
async def skills_delete_file(skill_id: str, version_id: str, file_path: str, revision: str | None = None):
    try:
        ver = skills_svc.delete_package_entry(
            skill_id,
            version_id,
            file_path,
            if_match=revision,
        )
    except KeyError as e:
        raise HTTPException(404, str(e) if str(e) != "'Package entry not found'" else "Package entry not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {
        "revision": ver.revision,
        "checksum": ver.package_checksum,
        "files": [f.model_dump(mode="json") for f in ver.files],
    }


@router.post("/skills/{skill_id}/versions/{version_id}/validate")
async def skills_version_validate(skill_id: str, version_id: str):
    try:
        return skills_svc.validate_skill_version(skill_id, version_id)
    except KeyError:
        raise HTTPException(404, "Version not found")


@router.post("/skills/{skill_id}/versions/{version_id}/publish")
async def skills_version_publish(skill_id: str, version_id: str):
    try:
        return skills_svc.publish_version(skill_id, version_id)
    except KeyError:
        raise HTTPException(404, "Version not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


