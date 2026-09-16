"""workflow DSL — source of truth for the designer.

Document shape matches workflow JSON:
  identifier, title, description,
  nodes[{identifier, title, icon?, description?, config, ...}],
  connections[{sourceIdentifier, targetIdentifier,
               sourceOutletIdentifier? | sourceOptionIdentifier?, fallback?}]

There is no End node — a run finishes when leaf nodes have no outgoing
connections.

UI layout (x/y) is NOT part of workflow DSL — it lives in optional ``ui`` and is
stripped by ``normalize`` before Temporal parse.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

# config.type values (no END)
WORKFLOW_CONFIG_TYPES = {
    "SELF_SERVE_TRIGGER",
    "EVENT_TRIGGER",
    "SCHEDULE_TRIGGER",
    "WEBHOOK",
    "KAFKA",
    "UPSERT_ENTITY",
    "INTEGRATION_ACTION",
    "INTERNAL_SERVICE",
    "AI",
    "AI_AGENT",
    "CONDITION",
    "INPUT",
    "SUBFLOW",
}

_CANVAS_TYPE = {
    "SELF_SERVE_TRIGGER": "trigger",
    "EVENT_TRIGGER": "trigger",
    "SCHEDULE_TRIGGER": "trigger",
    "AI_AGENT": "ai_agent",
    "AI": "ai",
    "WEBHOOK": "webhook",
    "CONDITION": "condition",
    "INPUT": "input",
    "UPSERT_ENTITY": "upsert_entity",
    "KAFKA": "kafka",
    "INTEGRATION_ACTION": "integration_action",
    "INTERNAL_SERVICE": "internal_service",
    "SUBFLOW": "subflow",
}

_CANVAS_TO_CONFIG = {
    "trigger": "SELF_SERVE_TRIGGER",
    "ai_agent": "AI_AGENT",
    "ai": "AI",
    "webhook": "WEBHOOK",
    "condition": "CONDITION",
    "input": "INPUT",
    "upsert_entity": "UPSERT_ENTITY",
    "kafka": "KAFKA",
    "integration_action": "INTEGRATION_ACTION",
    "internal_service": "INTERNAL_SERVICE",
    "subflow": "SUBFLOW",
    # end intentionally omitted — dropped
}


class DslConnection(BaseModel):
    sourceIdentifier: str
    targetIdentifier: str
    sourceOutletIdentifier: Optional[str] = None  # INPUT outlets
    sourceOptionIdentifier: Optional[str] = None  # CONDITION options
    fallback: bool = False


class DslNode(BaseModel):
    identifier: str
    title: str = ""
    icon: Optional[str] = None
    description: Optional[str] = None
    config: dict[str, Any] = Field(default_factory=dict)
    variables: Optional[dict[str, Any]] = None
    links: Optional[list[str]] = None
    verbose: Optional[bool] = None


class WorkflowDsl(BaseModel):
    """workflow document."""

    identifier: str
    title: str = ""
    description: str = ""
    produces: list[str] = Field(default_factory=list)
    nodes: list[DslNode] = Field(default_factory=list)
    connections: list[DslConnection] = Field(default_factory=list)
    ui: Optional[dict[str, Any]] = None

    def trigger_node(self) -> DslNode | None:
        for n in self.nodes:
            cfg_type = str((n.config or {}).get("type") or "").upper()
            if cfg_type.endswith("TRIGGER") or cfg_type in {
                "SELF_SERVE_TRIGGER",
                "EVENT_TRIGGER",
                "SCHEDULE_TRIGGER",
            }:
                return n
        return self.nodes[0] if self.nodes else None


def parse_workflow_dsl(raw: dict[str, Any] | str) -> WorkflowDsl:
    """Parse workflow DSL from dict or JSON string."""
    import json

    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw
    if not isinstance(data, dict):
        raise ValueError("workflow DSL must be an object")
    return WorkflowDsl.model_validate(data)


def _edge_layout_key(source: str, target: str, handle: str | None) -> str:
    h = handle if handle and handle != "out" else ""
    return f"{source}::{target}::{h}"


def workflow_dsl_to_canvas(doc: WorkflowDsl) -> dict[str, Any]:
    """Map workflow DSL → React Flow-friendly structure (designer only)."""
    ui = doc.ui or {}
    positions = ui.get("positions") or {}
    waypoints = ui.get("edgeWaypoints") or {}
    nodes = []
    for n in doc.nodes:
        cfg_type = str((n.config or {}).get("type") or "").upper()
        if cfg_type == "END":
            continue
        cfg = dict(n.config or {})
        meta = {}
        if cfg.get("governance") or cfg.get("immutable") or str(n.identifier).startswith("governance-"):
            meta = {"immutable": True, "governance": True}
        pos = positions.get(n.identifier) if isinstance(positions, dict) else None
        nodes.append({
            "id": n.identifier,
            "type": _CANVAS_TYPE.get(cfg_type, cfg_type.lower() or "webhook"),
            "label": n.title or n.identifier,
            "position": pos if isinstance(pos, dict) else {"x": 0, "y": 0},
            "config": cfg,
            "metadata": meta,
        })
    keep = {n["id"] for n in nodes}
    edges = []
    for i, c in enumerate(doc.connections):
        if c.sourceIdentifier not in keep or c.targetIdentifier not in keep:
            continue
        outlet = c.sourceOptionIdentifier or c.sourceOutletIdentifier
        wp = waypoints.get(_edge_layout_key(c.sourceIdentifier, c.targetIdentifier, outlet)) if isinstance(waypoints, dict) else None
        edges.append({
            "id": f"c{i}-{c.sourceIdentifier}-{c.targetIdentifier}",
            "source": c.sourceIdentifier,
            "target": c.targetIdentifier,
            "sourceHandle": outlet,
            "condition": outlet,
            "waypoint": wp if isinstance(wp, dict) else None,
        })
    return {
        "graphId": doc.identifier,
        "name": doc.title,
        "description": doc.description,
        "kind": ((doc.ui or {}).get("kind") if doc.ui else None) or "e2e",
        "produces": list(doc.produces or []),
        "nodes": nodes,
        "edges": edges,
        "entrypoints": [doc.trigger_node().identifier] if doc.trigger_node() else [],
    }
