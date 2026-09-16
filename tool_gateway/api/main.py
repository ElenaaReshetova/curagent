"""Tool Gateway HTTP API (CAP-026, SEC-002)."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.tool_gateway.gateway.gateway import get_gateway
from src.tool_gateway.models.envelopes import ToolIntent
from src.tool_gateway.registry.store import ensure_loaded, list_manifests, reload_registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Tool Gateway", description="Capabilities registry + Resolver + Dispatch")


class InvokeRequest(BaseModel):
    intent: ToolIntent
    execution_context: dict[str, Any] = Field(default_factory=dict)


@app.on_event("startup")
async def startup() -> None:
    ensure_loaded()
    logger.info("Tool Gateway started, manifests loaded")


@app.get("/api/health")
async def health():
    from src.tool_gateway.registry.store import get_snapshot_id, is_registry_available
    return {
        "status": "ok" if is_registry_available() else "degraded",
        "snapshot_id": get_snapshot_id(),
    }


@app.post("/api/v1/invoke")
async def invoke(body: InvokeRequest):
    """Primary invoke endpoint — ToolIntent → InvokeResponse."""
    gw = get_gateway()
    response = await gw.invoke(body.intent, body.execution_context)
    return response.model_dump()


@app.get("/api/v1/capabilities")
async def capabilities():
    return {"capabilities": [m.model_dump() for m in list_manifests()]}


@app.get("/api/v1/capabilities/{capability_id}")
async def get_capability(capability_id: str):
    from src.tool_gateway.registry.store import get_manifest
    m = get_manifest(capability_id)
    if m is None:
        raise HTTPException(404, f"Capability {capability_id} not found")
    return m.model_dump()


@app.post("/api/v1/registry/reload")
async def registry_reload():
    snapshot_id = reload_registry()
    return {"snapshot_id": snapshot_id, "count": len(list_manifests())}


@app.get("/api/v1/decisions/{decision_id}")
async def get_decision(decision_id: str):
    from src.tool_gateway.audit.store import get_decision as load_decision, replay_decision
    record = load_decision(decision_id)
    if record is None:
        raise HTTPException(404, f"Decision {decision_id} not found")
    return {"record": record.model_dump(), "replay": replay_decision(decision_id)}


@app.get("/api/v1/decisions")
async def list_decisions(limit: int = 50):
    from src.tool_gateway.audit.store import list_recent_decisions
    records = list_recent_decisions(limit=limit)
    return {"decisions": [r.model_dump() for r in records], "count": len(records)}


@app.get("/api/v1/metrics")
async def metrics():
    from src.tool_gateway import telemetry
    from src.tool_gateway.registry.store import get_snapshot_id, is_registry_available
    return {
        **telemetry.snapshot(),
        "registry_available": is_registry_available(),
        "snapshot_id": get_snapshot_id(),
    }


@app.get("/api/v1/policy")
async def get_policy():
    from src.tool_gateway.policy.evaluator import load_policy
    return load_policy()


@app.put("/api/v1/policy")
async def put_policy(body: dict[str, Any]):
    from src.tool_gateway.policy.evaluator import save_policy
    return save_policy(body)


def main() -> None:
    import uvicorn
    port = int(os.environ.get("TOOL_GATEWAY_PORT", "8093"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
