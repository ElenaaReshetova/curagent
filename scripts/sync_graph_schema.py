#!/usr/bin/env python3
"""Sync WorkflowGraph JSON Schema to config/ and frontend/src/schema/.

Usage:
  .venv/bin/python scripts/sync_graph_schema.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.platform.graphs.schema_export import build_schema_bundle, write_schema_files


def main() -> int:
    paths = write_schema_files(build_schema_bundle())
    for p in paths:
        print(f"wrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
