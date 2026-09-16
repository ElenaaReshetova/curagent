"""Gateway integration tests."""

from __future__ import annotations

import asyncio
import os
import uuid

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("CAPABILITY_MANIFESTS_DIR", os.path.join(_ROOT, "config/capabilities/manifests"))
os.environ.setdefault("REGISTRY_CONFIG_DIR", os.path.join(_ROOT, "config/registry"))
os.environ.setdefault("TOOL_GATEWAY_AUDIT_DIR", os.path.join(_ROOT, "data/test_tool_gateway_audit"))

from src.tool_gateway.gateway.gateway import get_gateway
from src.tool_gateway.models.envelopes import CallerIdentity, ToolIntent
from src.tool_gateway.registry.store import reload_registry
from src.orchestrator.models import NormalizedTaskSpec


def test_invoke_classify_accept(monkeypatch):
    async def fake_invoke_mcp(_server, _tool, inputs):
        return {"id": inputs["taskId"], "source": "jira", "title": "T"}

    monkeypatch.setattr("src.tool_gateway.adapters.mcp_bridge.invoke_mcp", fake_invoke_mcp)
    reload_registry()
    gw = get_gateway()
    intent = ToolIntent(
        request_id=str(uuid.uuid4()),
        trace_id="test-trace",
        tenant_id="default",
        caller=CallerIdentity(sub_agent_role="playbook-executor"),
        capability_id="task.read",
        inputs={"taskId": "t1"},
        idempotency_key=f"test-classify-{uuid.uuid4().hex[:8]}",
    )
    spec = NormalizedTaskSpec(
        task_id="t1", trace_id="test-trace", title="T", description="do task",
        source="test", source_id="s1", callback_url="http://localhost/cb",
    )

    async def run():
        return await gw.invoke(intent, {"spec": spec})

    resp = asyncio.run(run())
    assert resp.success is True
    assert resp.result is not None
    assert resp.result.capability_id == "task.read"
    assert resp.result.execution_record_id


def test_invoke_unknown_deny():
    reload_registry()
    gw = get_gateway()

    async def run():
        intent = ToolIntent(
            request_id=str(uuid.uuid4()),
            trace_id="t",
            capability_id="no-such-cap",
            idempotency_key="x",
        )
        return await gw.invoke(intent, {})

    resp = asyncio.run(run())
    assert resp.success is False
    assert resp.denial.denial_code.value == "CAPABILITY_NOT_FOUND"
