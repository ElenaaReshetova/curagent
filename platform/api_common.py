"""Shared API helpers for platform routers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.platform import store
from src.platform.domain.models import (
    CapabilityDef,
    SkillInterface,
)


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class ActivateResponse(BaseModel):
    id: str
    status: str


def activate_entity(entity: Any, saver) -> Any:
    entity.status = "active"
    entity.updated_at = datetime.utcnow()
    return saver(entity)


def register_crud(
    router: APIRouter,
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
