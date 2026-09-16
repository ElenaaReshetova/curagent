"""workflow node palette — no legacy aliases."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from src.platform.graphs.models import GraphKind, NodeType


class PortDef(BaseModel):
    id: str
    label: str = ""


class NodeRegistryEntry(BaseModel):
    type: NodeType
    title: str
    category: str
    icon: str
    configSchema: dict[str, Any] = Field(default_factory=dict)
    ports: dict[str, list[PortDef]] = Field(default_factory=dict)
    colorToken: str = "slate"
    kinds: list[GraphKind] = Field(default_factory=lambda: ["e2e", "stage"])
    # Nested ui kept for React designer (reads entry.ui.colorToken)
    ui: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)
    palette: bool = True


def _e(
    type_: NodeType,
    title: str,
    category: str,
    icon: str,
    color: str,
    config: dict[str, Any],
    *,
    ins: bool = True,
    outs: list[str] | None = None,
) -> NodeRegistryEntry:
    return NodeRegistryEntry(
        type=type_,
        title=title,
        category=category,
        icon=icon,
        configSchema=config,
        ports={
            "in": [PortDef(id="in")] if ins else [],
            "out": [PortDef(id=o) for o in (outs if outs is not None else ["out"])],
        },
        colorToken=color,
        ui={"defaultSize": {"w": 200, "h": 64}, "inspector": "schema-form", "colorToken": color},
        runtime={"temporalKind": "entrypoint" if type_ == "trigger" else "activity"},
        palette=True,
    )


NODE_REGISTRY: dict[str, NodeRegistryEntry] = {
    "trigger": _e(
        "trigger", "Trigger", "Triggers", "▶", "emerald",
        {"type": "object", "properties": {
            "type": {"enum": ["SELF_SERVE_TRIGGER", "EVENT_TRIGGER", "SCHEDULE_TRIGGER"]},
            "published": {"type": "boolean"},
            "userInputs": {"type": "object"},
            "event": {"type": "object"},
            "cron": {"type": "string"},
        }},
        ins=False,
    ),
    "ai_agent": _e("ai_agent", "AI Agent", "Actions", "A", "indigo", {
        "type": "object",
        "properties": {
            "type": {"const": "AI_AGENT"},
            "agentIdentifier": {"type": "string"},
            "userPrompt": {"type": "string"},
            "outputSchema": {"type": "object"},
        },
        "required": ["agentIdentifier", "userPrompt"],
    }),
    "ai": _e("ai", "AI", "Actions", "✦", "violet", {
        "type": "object",
        "properties": {
            "type": {"const": "AI"},
            "userPrompt": {"type": "string"},
            "systemPrompt": {"type": "string"},
            "tools": {"type": "array", "items": {"type": "string"}},
            "outputSchema": {"type": "object"},
        },
        "required": ["userPrompt"],
    }),
    "webhook": _e("webhook", "Webhook", "Actions", "⇢", "sky", {
        "type": "object",
        "properties": {
            "type": {"const": "WEBHOOK"},
            "url": {"type": "string"},
            "method": {"enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
            "headers": {"type": "object"},
            "body": {},
            "synchronized": {"type": "boolean"},
            "onTimeout": {"enum": ["fail", "continue"]},
            "onFailure": {"enum": ["continue", "terminate"]},
            "verbose": {"type": "boolean"},
        },
        "required": ["url"],
    }),
    "upsert_entity": _e("upsert_entity", "Upsert entity", "Actions", "▣", "cyan", {
        "type": "object",
        "properties": {
            "type": {"const": "UPSERT_ENTITY"},
            "blueprintIdentifier": {"type": "string"},
            "mapping": {"type": "object"},
            "onFailure": {"enum": ["continue", "terminate"]},
        },
        "required": ["blueprintIdentifier", "mapping"],
    }),
    "kafka": _e("kafka", "Kafka", "Actions", "Κ", "amber", {
        "type": "object",
        "properties": {
            "type": {"const": "KAFKA"},
            "payload": {},
            "onFailure": {"enum": ["continue", "terminate"]},
        },
    }),
    "integration_action": _e("integration_action", "Integration action", "Actions", "⚙", "orange", {
        "type": "object",
        "properties": {
            "type": {"const": "INTEGRATION_ACTION"},
            "integrationProvider": {"type": "string"},
            "repo": {"type": "string"},
            "workflow": {"type": "string"},
            "workflowInputs": {"type": "object"},
            "onFailure": {"enum": ["continue", "terminate"]},
        },
    }),
    "internal_service": _e("internal_service", "Internal service", "Actions", "▣", "teal", {
        "type": "object",
        "properties": {
            "type": {"const": "INTERNAL_SERVICE"},
            "service": {"type": "string"},
            "parameter": {"type": "object"},
            "onTimeout": {"enum": ["fail", "continue"]},
            "onFailure": {"enum": ["continue", "terminate"]},
        },
        "required": ["service"],
    }),
    "subflow": _e("subflow", "Subflow", "Actions", "↳", "purple", {
        "type": "object",
        "properties": {
            "type": {"const": "SUBFLOW"},
            "graph_kind": {"enum": ["e2e", "stage"]},
            "graph_key": {"type": "string"},
            "graph_id": {"type": "string"},
            "input": {"type": "object"},
        },
        "required": ["graph_key"],
    }),
    "condition": _e(
        "condition", "Condition", "Conditions", "◇", "violet",
        {"type": "object", "properties": {
            "type": {"const": "CONDITION"},
            "options": {"type": "array", "description": "CONDITION options (identifier, title, expression)"},
        }},
        outs=["yes", "no"],
    ),
    "input": _e(
        "input", "Input", "Actions", "✓", "pink",
        {"type": "object", "properties": {
            "type": {"const": "INPUT"},
            "description": {"type": "string"},
            "userInputs": {"type": "object", "description": "properties + buttons"},
            "outlets": {"type": "array", "description": "branches; identifier must match a button"},
            "responders": {"type": "object"},
            "notifications": {"type": "array"},
        }},
        outs=["approve", "decline"],
    ),
}

for _unsupported_key in ("upsert_entity", "kafka", "integration_action"):
    NODE_REGISTRY[_unsupported_key].palette = False


def list_registry(kind: GraphKind | None = None, *, palette_only: bool = False) -> list[NodeRegistryEntry]:
    entries = list(NODE_REGISTRY.values())
    if kind is not None:
        entries = [e for e in entries if kind in e.kinds]
    if palette_only:
        entries = [e for e in entries if e.palette]
    return entries


def get_entry(type_: str) -> NodeRegistryEntry | None:
    return NODE_REGISTRY.get(type_)


def registry_as_dicts(kind: GraphKind | None = None, *, palette_only: bool = False) -> list[dict[str, Any]]:
    return [e.model_dump(mode="json") for e in list_registry(kind, palette_only=palette_only)]
