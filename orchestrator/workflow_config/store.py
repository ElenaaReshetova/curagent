"""JSON file store for workflow templates."""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from src.orchestrator.workflow_config.models import WorkflowTemplate

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "config" / "workflows"


def get_workflows_dir() -> Path:
    env = os.environ.get("WORKFLOW_CONFIG_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return _DEFAULT_DIR


def _template_path(workflows_dir: Path, template_id: str) -> Path:
    safe_id = template_id.replace("/", "_").replace("..", "_")
    return workflows_dir / f"{safe_id}.json"


def _normalize_template_data(data: dict) -> dict:
    """Coerce legacy step types so templates remain loadable after schema changes."""
    for step in data.get("steps") or []:
        if step.get("type") == "decision":
            step["type"] = "gateway_or"
            if step.get("label") in (None, "", "Decision", "OK?"):
                step["label"] = "Gateway ИЛИ"
    return data


def list_templates() -> list[WorkflowTemplate]:
    workflows_dir = get_workflows_dir()
    workflows_dir.mkdir(parents=True, exist_ok=True)
    templates: list[WorkflowTemplate] = []
    for path in sorted(workflows_dir.glob("*.json")):
        try:
            data = _normalize_template_data(json.loads(path.read_text(encoding="utf-8")))
            templates.append(WorkflowTemplate.model_validate(data))
        except Exception as e:
            logger.warning("Skip invalid template %s: %s", path, e)
    return templates


def get_template(template_id: str) -> Optional[WorkflowTemplate]:
    path = _template_path(get_workflows_dir(), template_id)
    if not path.exists():
        return None
    try:
        data = _normalize_template_data(json.loads(path.read_text(encoding="utf-8")))
        return WorkflowTemplate.model_validate(data)
    except Exception as e:
        logger.error("Failed to load template %s: %s", template_id, e)
        raise ValueError(f"Template {template_id} is invalid: {e}") from e


def get_default_template() -> WorkflowTemplate:
    templates = list_templates()
    for t in templates:
        if t.is_default:
            return t
    if templates:
        return templates[0]
    raise FileNotFoundError("No workflow templates found")


def save_template(template: WorkflowTemplate) -> WorkflowTemplate:
    workflows_dir = get_workflows_dir()
    workflows_dir.mkdir(parents=True, exist_ok=True)

    if template.is_default:
        for existing in list_templates():
            if existing.id != template.id and existing.is_default:
                existing.is_default = False
                _write_template(existing)

    _write_template(template)
    return template


def _write_template(template: WorkflowTemplate) -> None:
    path = _template_path(get_workflows_dir(), template.id)
    path.write_text(
        template.model_dump_json(indent=2),
        encoding="utf-8",
    )


def delete_template(template_id: str) -> bool:
    path = _template_path(get_workflows_dir(), template_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def set_default_template(template_id: str) -> WorkflowTemplate:
    target = get_template(template_id)
    if target is None:
        raise KeyError(template_id)
    for t in list_templates():
        t.is_default = t.id == template_id
        save_template(t)
    return target


def clone_template(template_id: str, new_name: Optional[str] = None) -> WorkflowTemplate:
    source = get_template(template_id)
    if source is None:
        raise KeyError(template_id)
    new_id = f"{template_id}-copy-{uuid.uuid4().hex[:6]}"
    clone = source.model_copy(deep=True)
    clone.id = new_id
    clone.name = new_name or f"{source.name} (copy)"
    clone.is_default = False
    clone.version = 1
    return save_template(clone)


def topological_order(template: WorkflowTemplate) -> list[WorkflowStepConfig]:
    """Return steps in execution order based on edges (Kahn's algorithm)."""
    steps_by_id = {s.id: s for s in template.steps}
    in_degree = {s.id: 0 for s in template.steps}
    adj: dict[str, list[str]] = {s.id: [] for s in template.steps}

    for edge in template.edges:
        if edge.from_step in adj and edge.to_step in in_degree:
            adj[edge.from_step].append(edge.to_step)
            in_degree[edge.to_step] += 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    order: list[str] = []
    while queue:
        queue.sort()
        node = queue.pop(0)
        order.append(node)
        for nxt in adj.get(node, []):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(template.steps):
        # Fallback: declaration order if cycle or disconnected
        return list(template.steps)

    return [steps_by_id[sid] for sid in order if sid in steps_by_id]
