"""Skill interface catalog API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.platform.contracts.registry import list_contracts
from src.platform.skill_interfaces import service as iface_svc

router = APIRouter(tags=["skill-interfaces"])


@router.get("/skill-interfaces")
async def skill_interfaces_list():
    items = iface_svc.list_interfaces()
    return {
        "skill_interfaces": [item.model_dump(mode="json") for item in items],
        "counts": {
            "total": len(items),
            "platform": sum(1 for i in items if i.source == "platform"),
            "custom": sum(1 for i in items if i.source == "custom"),
        },
    }


@router.get("/artifact-contracts")
async def artifact_contracts_list():
    items = list_contracts()
    return {
        "contracts": [item.model_dump(mode="json") for item in items],
        "counts": {
            "total": len(items),
            "artifact": sum(1 for i in items if i.kind == "artifact"),
            "patch": sum(1 for i in items if i.kind == "patch"),
            "work_item": sum(1 for i in items if i.kind == "work_item"),
        },
    }


@router.get("/artifact-contracts/{contract_key}")
async def artifact_contracts_get(contract_key: str):
    from src.platform.contracts.registry import get_contract

    item = get_contract(contract_key)
    if not item:
        raise HTTPException(404, "Contract not found")
    return item.model_dump(mode="json")


@router.get("/skill-interfaces/{entity_id}")
async def skill_interfaces_get(entity_id: str):
    item = iface_svc.get_interface(entity_id)
    if not item:
        raise HTTPException(404, "Skill interface not found")
    return item.model_dump(mode="json")


@router.post("/skill-interfaces")
async def skill_interfaces_create(body: dict):
    try:
        return iface_svc.create_interface(body).model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/skill-interfaces/{entity_id}")
async def skill_interfaces_update(entity_id: str, body: dict):
    try:
        return iface_svc.update_interface(entity_id, body).model_dump(mode="json")
    except KeyError:
        raise HTTPException(404, "Skill interface not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/skill-interfaces/{entity_id}")
async def skill_interfaces_delete(entity_id: str):
    try:
        return iface_svc.delete_interface(entity_id)
    except KeyError:
        raise HTTPException(404, "Skill interface not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
