"""Resolve live ingress to the canonical Scenario/Workflow store."""

from __future__ import annotations

from typing import Any, Optional

from src.platform.scenarios.errors import ScenarioError


def _ingress_candidates():
    from src.platform.graphs.service import list_graphs

    return [
        rec
        for rec in list_graphs(kind="e2e")
        if rec.launched and rec.current_published_version_id
    ]


def _select_ingress_scenario(flow_key: str | None):
    candidates = _ingress_candidates()
    requested = (flow_key or "").strip()
    if requested:
        aliases = {requested, f"e2e:{requested}"}
        candidates = [
            rec
            for rec in candidates
            if rec.key in aliases
            or str(rec.id) == requested
            or rec.key.split(":", 1)[-1] == requested
        ]

    if not candidates:
        detail = f" for key {requested!r}" if requested else ""
        raise ScenarioError(
            "NO_LAUNCHED_SCENARIO",
            f"NO_LAUNCHED_SCENARIO: no launched E2E scenario{detail}",
        )
    if len(candidates) > 1:
        keys = ", ".join(sorted(rec.key for rec in candidates))
        raise ScenarioError(
            "AMBIGUOUS_LAUNCH",
            f"AMBIGUOUS_LAUNCH: specify scenario_key; launched candidates: {keys}",
        )
    return candidates[0]


def _compiled_plan(rec) -> tuple[dict[str, Any], Any]:
    from src.platform.graphs.service import get_version

    version = get_version(rec.current_published_version_id)
    plan = version.temporal_plan
    if not plan:
        raise ScenarioError(
            "INVALID_PUBLISHED_SCENARIO",
            f"Published scenario {rec.key} has no frozen Temporal plan",
        )
    return plan, version


def resolve_execution_template(
    *,
    primary_skill: str,
    requested_template_id: Optional[str] = None,
    flow_key: Optional[str] = None,
    source: Optional[str] = None,
    project: Optional[str] = None,
    issue_type: Optional[str] = None,
    graph_only: bool = False,
) -> tuple[str, str, dict[str, Any]]:
    """Resolve one launched E2E scenario; legacy flow/template fallbacks are inactive."""
    del primary_skill, requested_template_id, source, project, issue_type, graph_only

    rec = _select_ingress_scenario(flow_key)
    plan, version = _compiled_plan(rec)
    secrets: dict[str, Any] = {}
    try:
        from src.platform.graphs.expressions import workflow_secrets

        secrets = workflow_secrets()
    except Exception:
        pass
    return (
        "__graph_workflow__",
        "scenario_temporal_plan",
        {
            "flow_key": rec.key.split(":", 1)[-1],
            "flow_name": rec.name,
            "graph_id": str(rec.id),
            "version_id": str(version.id),
            "plan": plan,
            "use_graph_interpreter": True,
            "secrets": secrets,
        },
    )
