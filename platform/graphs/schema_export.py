"""Export workflow DSL JSON Schema for the designer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.platform.graphs.workflow_dsl import DslConnection, DslNode, WorkflowDsl
from src.platform.graphs.registry import NODE_REGISTRY


def build_schema_bundle() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Workflow DSL",
        "version": "2",
        "definitions": {
            "WorkflowDsl": WorkflowDsl.model_json_schema(),
            "DslNode": DslNode.model_json_schema(),
            "DslConnection": DslConnection.model_json_schema(),
        },
        "nodeTypes": sorted(NODE_REGISTRY.keys()),
        "nodeRegistry": {
            k: {
                "type": v.type,
                "category": v.category,
                "title": v.title,
                "configSchema": v.configSchema,
            }
            for k, v in NODE_REGISTRY.items()
        },
    }


def schema_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[3]
    return (
        root / "config" / "platform" / "workflow-graph.schema.json",
        root / "frontend" / "src" / "schema" / "workflow-graph.schema.json",
    )


def write_schema_files(bundle: dict[str, Any] | None = None) -> list[Path]:
    payload = bundle or build_schema_bundle()
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    written: list[Path] = []
    for path in schema_paths():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
