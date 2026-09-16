"""workflow Temporal activities — single activity surface.

Names match → Temporal mapping:
  http_webhook | ai_generate_summary | ai_agent_execute | human_review |
  internal_service | kafka_publish | upsert_entity | integration_action

Plus run bookkeeping: graph_record_event | graph_update_run_state
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid5

from temporalio import activity

from src.platform.graphs.expressions import parse_structured_json, render_templates, skill_text

logger = logging.getLogger(__name__)


@activity.defn(name="http_webhook")
async def http_webhook(input_payload: dict[str, Any]) -> dict[str, Any]:
    from src.platform.graphs.expressions import render_templates, workflow_secrets

    cfg = dict(input_payload or {})
    ctx = {
        "outputs": cfg.get("outputs") or {},
        "inputs": cfg.get("inputs") or {},
        "input": cfg.get("inputs") or cfg.get("input") or {},
        "secrets": {**workflow_secrets(), **(cfg.get("secrets") or {})},
    }
    cfg = render_templates(cfg, ctx)
    url = str(cfg.get("url") or "").strip()
    method = str(cfg.get("method") or "POST").upper()
    on_failure = str(cfg.get("onFailure") or "terminate").lower()
    on_timeout = str(cfg.get("onTimeout") or "fail").lower()
    if not url:
        if on_failure == "continue":
            return {"ok": False, "continued": True, "error": "url required", "response": {"body": None, "status": 0}}
        raise RuntimeError("WEBHOOK url is required")

    headers = cfg.get("headers") if isinstance(cfg.get("headers"), dict) else {}
    headers = {str(k): str(v) for k, v in headers.items()}
    idempotency_key = str(cfg.get("idempotency_key") or "").strip()
    if idempotency_key:
        headers.setdefault("Idempotency-Key", idempotency_key)
    body = cfg.get("body")
    try:
        import httpx

        async with httpx.AsyncClient(timeout=float(cfg.get("timeout_seconds") or 30)) as client:
            kwargs: dict[str, Any] = {"headers": headers}
            if method in {"POST", "PUT", "PATCH"} and body is not None:
                if isinstance(body, (dict, list)):
                    kwargs["json"] = body
                else:
                    kwargs["content"] = str(body).encode("utf-8")
            resp = await client.request(method, url, **kwargs)
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            ok = 200 <= resp.status_code < 400
            result = {
                "ok": ok,
                "status_code": resp.status_code,
                "response": {"body": data, "status": resp.status_code},
            }
            if cfg.get("verbose"):
                result["request"] = {"url": url, "method": method, "body": body}
            if not ok and on_failure != "continue":
                raise RuntimeError(f"WEBHOOK HTTP {resp.status_code}")
            if not ok:
                result["continued"] = True
            return result
    except Exception as exc:
        is_timeout = "timeout" in str(exc).lower()
        if is_timeout and on_timeout == "continue":
            return {"ok": True, "timeout": True, "response": {"body": {"timeout": True}, "status": 0}}
        if on_failure == "continue":
            return {"ok": False, "continued": True, "error": str(exc), "response": {"body": None, "status": 0}}
        raise


async def _run_skill(agent_id: str, prompt: str, *, run_id: str, outputs: dict[str, Any], system: str = "") -> dict[str, Any]:
    from src.orchestrator.activities import execute_skill_step_activity
    from src.orchestrator.models import NormalizedTaskSpec

    rendered = str(render_templates(prompt, {"outputs": outputs, "inputs": {}, "secrets": {}}))
    spec = NormalizedTaskSpec(
        task_id=str(run_id or "graph-run"),
        title=str(agent_id),
        description=str(rendered or system or ""),
        source="port",
        source_id=str(run_id or ""),
        trace_id=str(run_id or ""),
    )
    result = await execute_skill_step_activity(spec, str(agent_id), rendered, None, 1, None, None, None, None)
    text = skill_text(result)
    if isinstance(result, dict):
        return {**result, "ok": result.get("ok", True), "response": text or result.get("response") or text}
    return {"ok": True, "response": text or result}


def _with_schema_fields(text: Any, schema: Any) -> dict[str, Any]:
    parsed = parse_structured_json(text) if schema else {}
    return parsed if isinstance(parsed, dict) else {}


@activity.defn(name="ai_generate_summary")
async def ai_generate_summary(input_payload: dict[str, Any]) -> dict[str, Any]:
    prompt = input_payload.get("userPrompt") or input_payload.get("prompt") or ""
    raw = await _run_skill(
        "port-ai",
        str(prompt),
        run_id=str(input_payload.get("run_id") or ""),
        outputs=input_payload.get("outputs") or {},
        system=str(input_payload.get("systemPrompt") or ""),
    )
    text = skill_text(raw)
    extra = _with_schema_fields(text, input_payload.get("outputSchema"))
    return {"ok": True, "response": {"text": text, "raw": raw, **extra}, **extra}


@activity.defn(name="ai_agent_execute")
async def ai_agent_execute(input_payload: dict[str, Any]) -> dict[str, Any]:
    agent_id = input_payload.get("agentIdentifier") or input_payload.get("agent_id") or "agent"
    prompt = input_payload.get("userPrompt") or input_payload.get("prompt") or ""
    raw = await _run_skill(
        str(agent_id),
        str(prompt),
        run_id=str(input_payload.get("run_id") or ""),
        outputs=input_payload.get("outputs") or {},
    )
    text = skill_text(raw)
    extra = _with_schema_fields(text, input_payload.get("outputSchema"))
    return {"ok": True, "response": {"result": raw, "text": text, **extra}, **extra}


@activity.defn(name="human_review")
async def human_review(input_payload: dict[str, Any]) -> dict[str, Any]:
    from src.platform.runtime_bridge import create_approval_checkpoint

    workflow_id = str(input_payload.get("run_id") or "local")
    try:
        workflow_id = activity.info().workflow_id or workflow_id
    except Exception:
        pass
    node_id = str(input_payload.get("node_id") or "review")
    outputs = input_payload.get("outputs") if isinstance(input_payload.get("outputs"), dict) else {}
    scheme = str((outputs.get("routing") or {}).get("scheme") or "").strip().upper()
    brd = skill_text((outputs.get("brd_agent") or {}).get("text") or outputs.get("brd_agent"))
    srd = skill_text((outputs.get("srd_agent") or {}).get("text") or outputs.get("srd_agent"))
    preview = brd or srd or skill_text(input_payload.get("description"))
    art_name = "SystemRequirementsDoc" if scheme == "SRD" else ("BusinessRequirementsDoc" if scheme == "BRD" else "Artifact")
    question = str(input_payload.get("description") or "").strip() or (
        f"Approve the {scheme or 'generated'} artifact or send it back."
    )
    cid = ""
    try:
        cid = create_approval_checkpoint(
            task_id=str(input_payload.get("run_id") or workflow_id),
            workflow_id=workflow_id,
            title=str(input_payload.get("title") or "Human review"),
            artifact_preview=preview,
            artifact_version=1,
            artifact_name=art_name,
            assignee_role="Reviewer",
            question=question,
            checkpoint_key=node_id,
        )
    except Exception as exc:
        logger.warning("human_review checkpoint skipped: %s", exc)
    notify_errors = await _dispatch_input_notifications(
        _render_notifications(input_payload.get("notifications") or [], input_payload)
    )
    return {"ok": True, "checkpoint_id": cid, "signal": {}, "node_id": node_id, "notify_errors": notify_errors}


def _render_notifications(notifications: Any, payload: dict[str, Any]) -> Any:
    from src.platform.graphs.expressions import workflow_secrets

    ctx = {
        "outputs": payload.get("outputs") or {},
        "inputs": payload.get("inputs") or {},
        "input": payload.get("inputs") or payload.get("input") or {},
        "secrets": {**workflow_secrets(), **(payload.get("secrets") or {})},
    }
    return render_templates(notifications, ctx)


async def _dispatch_input_notifications(notifications: Any) -> list[str]:
    """Fire INPUT.notifications webhooks (Slack chat.postMessage, etc.). Fail-open."""
    if not isinstance(notifications, list) or not notifications:
        return []
    errors: list[str] = []
    try:
        import httpx
    except Exception as exc:
        return [str(exc)]
    async with httpx.AsyncClient(timeout=20) as client:
        for item in notifications:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            target = str(item.get("target") or item.get("type") or "").lower()
            if not url or (target and target not in {"webhook", "slack", ""}):
                continue
            headers = item.get("headers") if isinstance(item.get("headers"), dict) else {}
            body = item.get("body")
            try:
                kwargs: dict[str, Any] = {"headers": {str(k): str(v) for k, v in headers.items()}}
                if isinstance(body, (dict, list)):
                    kwargs["json"] = body
                elif body is not None:
                    kwargs["content"] = str(body).encode("utf-8")
                resp = await client.post(url, **kwargs)
                if resp.status_code >= 400:
                    errors.append(f"{url} HTTP {resp.status_code}")
            except Exception as exc:
                errors.append(f"{url}: {exc}")
    if errors:
        try:
            activity.logger.warning("INPUT notifications failed: %s", errors)
        except Exception:
            pass
    return errors


@activity.defn(name="internal_service")
async def internal_service(input_payload: dict[str, Any]) -> dict[str, Any]:
    service = str(input_payload.get("service") or "").strip()
    if not service:
        raise RuntimeError("INTERNAL_SERVICE requires `service`")
    if service == "policy.evaluate" or input_payload.get("governance"):
        from src.platform.graphs.governance import evaluate_policy

        return evaluate_policy(input_payload)
    raise RuntimeError(f"INTERNAL_SERVICE «{service}» is not registered")


@activity.defn(name="execute_subflow")
async def execute_subflow(input_payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve a child scenario / PDLC stage and return its Temporal plan."""
    from src.platform.graphs import service as graphs_svc
    rec = None
    graph_id = input_payload.get("graph_id")
    graph_key = str(
        input_payload.get("graph_key")
        or input_payload.get("flow_key")
        or input_payload.get("playbook_key")
        or ""
    ).strip()
    if graph_id:
        try:
            rec = graphs_svc.get_graph(UUID(str(graph_id)))
        except Exception:
            rec = None
    if rec is None and graph_key:
        rec = graphs_svc.get_graph_by_key(graph_key)
    if rec is None:
        raise RuntimeError("SUBFLOW target graph not found")
    vid = rec.current_published_version_id
    if not vid:
        raise RuntimeError(f"SUBFLOW «{rec.key}» has no published version")
    ver = graphs_svc.get_version(vid)
    if ver.status != "PUBLISHED" or not ver.temporal_plan:
        raise RuntimeError(f"SUBFLOW «{rec.key}» has no frozen published plan")
    parent_execution_id = None
    child_run_id = None
    parent_run_id = input_payload.get("run_id")
    node_id = str(input_payload.get("node_id") or "subflow")
    if parent_run_id:
        try:
            from src.platform.graphs.models import GraphRun

            parent_execution_id = UUID(str(parent_run_id))
            child_run_id = uuid5(parent_execution_id, node_id)
            graphs_svc.save_run(
                GraphRun(
                    id=child_run_id,
                    graph_id=rec.id,
                    version_id=ver.id,
                    status="running",
                    state={"source": "SUBFLOW", "engine": "temporal", "plan": dict(ver.temporal_plan)},
                    temporal_workflow_id=f"{parent_execution_id}-sub-{node_id}",
                    parent_execution_id=parent_execution_id,
                    events=[{"type": "created", "source": "subflow"}],
                )
            )
        except (TypeError, ValueError):
            parent_execution_id = None
            child_run_id = None
    return {
        "ok": True,
        "graph_id": str(rec.id),
        "graph_key": rec.key,
        "graph_kind": rec.kind,
        "name": rec.name,
        "plan": dict(ver.temporal_plan),
        "version_id": str(ver.id),
        "parent_execution_id": str(parent_execution_id) if parent_execution_id else parent_run_id,
        "child_run_id": str(child_run_id) if child_run_id else None,
        "input": input_payload.get("input") if isinstance(input_payload.get("input"), dict) else {},
    }


@activity.defn(name="kafka_publish")
async def kafka_publish(input_payload: dict[str, Any]) -> dict[str, Any]:
    if str(input_payload.get("onFailure") or "terminate").lower() == "continue":
        return {"ok": False, "continued": True, "error": "Kafka publisher not configured"}
    raise RuntimeError("Kafka publisher is not configured")


@activity.defn(name="upsert_entity")
async def upsert_entity(input_payload: dict[str, Any]) -> dict[str, Any]:
    if str(input_payload.get("onFailure") or "terminate").lower() == "continue":
        return {"ok": False, "continued": True, "error": "UPSERT_ENTITY not configured"}
    raise RuntimeError("UPSERT_ENTITY is not configured")


@activity.defn(name="integration_action")
async def integration_action(input_payload: dict[str, Any]) -> dict[str, Any]:
    if str(input_payload.get("onFailure") or "terminate").lower() == "continue":
        return {"ok": False, "continued": True, "error": "INTEGRATION_ACTION not configured"}
    raise RuntimeError("INTEGRATION_ACTION is not configured")


@activity.defn(name="graph_record_event")
async def graph_record_event(payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not run_id:
        raise ValueError("run_id is required")
    ev = payload.get("event") if isinstance(payload.get("event"), dict) else {}
    degraded: list[str] = []
    try:
        from src.platform.graphs import service as graphs_svc

        graphs_svc.append_run_event(UUID(str(run_id)), ev or payload.get("event") or {})
    except Exception as exc:
        logger.exception("record event failed: %s", exc)
        raise
    if ev.get("node") or ev.get("title"):
        try:
            from src.platform.runtime_bridge import update_execution_progress

            update_execution_progress(
                str(run_id),
                stage=str(ev.get("title") or ev.get("node") or ""),
                activity=str(ev.get("title") or ev.get("node") or "step"),
                stage_key=str(ev.get("node") or "") or None,
                stage_status="RUNNING",
                stage_name=str(ev.get("title") or ev.get("node") or "") or None,
                detail=str(ev.get("type") or ""),
            )
        except Exception as exc:
            logger.warning("execution progress projection failed: %s", exc)
            degraded.append(str(exc))
    return {"ok": True, "degraded": degraded}


@activity.defn(name="graph_update_run_state")
async def graph_update_run_state(payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not run_id:
        raise ValueError("run_id is required")
    status = str(payload.get("status") or "")
    try:
        from src.platform.graphs import service as graphs_svc

        run = graphs_svc.get_run(UUID(str(run_id)))
        if payload.get("status"):
            run.status = payload["status"]
        if payload.get("state") is not None:
            run.state = {**(run.state or {}), **(payload.get("state") or {})}
        if payload.get("output") is not None:
            run.output = payload["output"]
        if payload.get("error") is not None:
            run.error = payload["error"]
        graphs_svc.update_run(run)
    except Exception as exc:
        logger.exception("update run state failed: %s", exc)
        raise
    degraded: list[str] = []
    if status in {"completed", "failed"}:
        try:
            from src.platform.runtime_bridge import update_execution_progress

            ok = status == "completed"
            update_execution_progress(
                str(run_id),
                status="COMPLETED" if ok else "FAILED",
                stage="Completed" if ok else "Failed",
                progress_pct=100,
            )
        except Exception as exc:
            logger.warning("execution final projection failed: %s", exc)
            degraded.append(str(exc))
    return {"ok": True, "degraded": degraded}
