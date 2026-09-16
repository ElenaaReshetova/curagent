"""Keep committed designer schema copies aligned with their generator."""

from __future__ import annotations

import json

from src.platform.graphs.schema_export import build_schema_bundle, schema_paths


def test_committed_workflow_graph_schemas_are_current() -> None:
    expected = build_schema_bundle()

    for path in schema_paths():
        assert json.loads(path.read_text(encoding="utf-8")) == expected, (
            f"{path} has drifted; run .venv/bin/python scripts/sync_graph_schema.py"
        )


def test_committed_workflow_graph_schema_copies_match() -> None:
    config_schema, frontend_schema = schema_paths()

    assert config_schema.read_bytes() == frontend_schema.read_bytes()
