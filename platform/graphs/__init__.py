"""Workflow graph package.

Pipeline: workflow DSL → normalize → parse → Temporal.
"""

from src.platform.graphs.normalize import normalize_workflow_dsl
from src.platform.graphs.parse import parse_workflow_to_temporal
from src.platform.graphs.workflow_dsl import WorkflowDsl, parse_workflow_dsl
from src.platform.graphs.registry import NODE_REGISTRY, list_registry
from src.platform.graphs.temporal_steps import TemporalPlan

__all__ = [
    "WorkflowDsl",
    "TemporalPlan",
    "NODE_REGISTRY",
    "list_registry",
    "parse_workflow_dsl",
    "normalize_workflow_dsl",
    "parse_workflow_to_temporal",
]
