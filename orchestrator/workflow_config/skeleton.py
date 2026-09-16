"""Fixed process shell: preamble → start_playbook … end_playbook → End.

User-editable region is strictly between start_playbook and end_playbook.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Optional

from src.orchestrator.workflow_config.models import (
    StepType,
    WorkflowEdge,
    WorkflowSettings,
    WorkflowStepConfig,
    WorkflowTemplate,
)

# Canonical ids for the locked process shell
SHELL_START_ID = "step-start"
SHELL_EVIDENCE_ID = "step-evidence"
SHELL_COMPRESS_ID = "step-compress"
SHELL_CLASSIFY_ID = "step-classify"
SHELL_START_PLAYBOOK_ID = "step-start-playbook"
SHELL_END_PLAYBOOK_ID = "step-end-playbook"
SHELL_END_ID = "step-end"

PREAMBLE_IDS = (
    SHELL_EVIDENCE_ID,
    SHELL_COMPRESS_ID,
    SHELL_CLASSIFY_ID,
)

BOUNDARY_TYPES = frozenset({StepType.START_PLAYBOOK, StepType.END_PLAYBOOK})
SHELL_TYPES = frozenset(
    {
        StepType.START,
        StepType.END,
        StepType.START_PLAYBOOK,
        StepType.END_PLAYBOOK,
    }
)

# Preamble script/skill identities (by id or by role)
PREAMBLE_ROLES = (
    ("collect_evidence", "script"),
    ("compress_context", "script"),
    ("classify", "skill"),
)


def is_boundary_type(step_type: StepType | str) -> bool:
    try:
        return StepType(step_type) in BOUNDARY_TYPES
    except ValueError:
        return False


def is_shell_type(step_type: StepType | str) -> bool:
    try:
        return StepType(step_type) in SHELL_TYPES
    except ValueError:
        return False


def find_step(template: WorkflowTemplate, step_id: str) -> Optional[WorkflowStepConfig]:
    return next((s for s in template.steps if s.id == step_id), None)


def find_start_playbook(template: WorkflowTemplate) -> Optional[WorkflowStepConfig]:
    return next((s for s in template.steps if s.enabled and s.type == StepType.START_PLAYBOOK), None)


def find_end_playbook(template: WorkflowTemplate) -> Optional[WorkflowStepConfig]:
    return next((s for s in template.steps if s.enabled and s.type == StepType.END_PLAYBOOK), None)


def playbook_body_step_ids(template: WorkflowTemplate) -> set[str]:
    """Steps strictly between start_playbook and end_playbook (markers excluded)."""
    start_pb = find_start_playbook(template)
    end_pb = find_end_playbook(template)
    if not start_pb or not end_pb:
        return set()

    outs: dict[str, list[str]] = defaultdict(list)
    for e in template.edges:
        outs[e.from_step].append(e.to_step)

    body: set[str] = set()
    q = deque(outs.get(start_pb.id, []))
    seen = {start_pb.id}
    while q:
        cur = q.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        if cur == end_pb.id:
            continue
        body.add(cur)
        for nxt in outs.get(cur, []):
            if nxt not in seen:
                q.append(nxt)
    return body


def is_playbook_body_step(template: WorkflowTemplate, step_id: str) -> bool:
    return step_id in playbook_body_step_ids(template)


def edge_is_inside_playbook(template: WorkflowTemplate, from_id: str, to_id: str) -> bool:
    """True if splicing a node into this edge would place it inside the playbook body."""
    start_pb = find_start_playbook(template)
    end_pb = find_end_playbook(template)
    if not start_pb or not end_pb:
        return False
    body = playbook_body_step_ids(template)
    # Edge start_playbook → X (X body or end_playbook): inside
    if from_id == start_pb.id and (to_id in body or to_id == end_pb.id):
        return True
    # Edge X → end_playbook: inside
    if to_id == end_pb.id and (from_id in body or from_id == start_pb.id):
        return True
    # Edge between body nodes
    if from_id in body and to_id in body:
        return True
    return False


def build_process_skeleton(
    *,
    template_id: str = "playbook-new",
    name: str = "New Playbook",
    description: str = "",
    body_steps: Optional[list[WorkflowStepConfig]] = None,
    body_edges: Optional[list[WorkflowEdge]] = None,
    first_body_id: Optional[str] = None,
    last_body_id: Optional[str] = None,
    settings: Optional[WorkflowSettings] = None,
    is_default: bool = False,
    status: str = "draft",
    version: int = 1,
) -> WorkflowTemplate:
    """
    Build Start → evidence → compress → classify → start_playbook
    → [body] → end_playbook → End.
    """
    y = 40.0
    gap = 110.0

    def _pos(yy: float) -> dict[str, float]:
        return {"x": 520.0, "y": yy}

    steps: list[WorkflowStepConfig] = [
        WorkflowStepConfig(
            id=SHELL_START_ID,
            type=StepType.START,
            label="Start",
            locked=True,
            position=_pos(y),
            output_key="started",
            description="Точка входа процесса",
        ),
    ]
    y += gap
    steps.append(
        WorkflowStepConfig(
            id=SHELL_EVIDENCE_ID,
            type=StepType.SCRIPT,
            label="Collect evidence",
            locked=True,
            position=_pos(y),
            script_id="collect_evidence",
            output_key="evidence",
            description="Сбор первичного контекста по задаче (общий для всех сценариев)",
            config={"timeout_minutes": 2},
        )
    )
    y += gap
    steps.append(
        WorkflowStepConfig(
            id=SHELL_COMPRESS_ID,
            type=StepType.SCRIPT,
            label="Compress context",
            locked=True,
            position=_pos(y),
            script_id="compress_context",
            output_key="evidence_brief",
            description="Нормализация / сжатие контекста → бриф исполнения",
            config={"timeout_minutes": 1},
            input_mappings=[],  # filled below after construction if needed
        )
    )
    # wire compress input mapping
    steps[-1].input_mappings = [
        type(steps[-1].input_mappings)(  # placeholder - use InputMapping
        )
    ]

    from src.orchestrator.workflow_config.models import InputMapping

    steps[-1].input_mappings = [
        InputMapping(param="evidence", source_step=SHELL_EVIDENCE_ID, source_output="evidence")
    ]
    y += gap
    steps.append(
        WorkflowStepConfig(
            id=SHELL_CLASSIFY_ID,
            type=StepType.SKILL,
            label="Classify Task",
            locked=True,
            position=_pos(y),
            skill_id="classify",
            output_key="routing",
            description="Классификация задачи на сценарий (primary_skill)",
            config={"timeout_minutes": 1},
        )
    )
    y += gap
    steps.append(
        WorkflowStepConfig(
            id=SHELL_START_PLAYBOOK_ID,
            type=StepType.START_PLAYBOOK,
            label="Start Playbook",
            locked=True,
            position=_pos(y),
            output_key="playbook_started",
            description="Начало пользовательского сценария",
        )
    )
    y += gap

    body = list(body_steps or [])
    for i, s in enumerate(body):
        if not s.position or s.position.get("y", 0) == 0:
            s.position = _pos(y + i * gap)
    steps.extend(body)
    body_y = y + max(len(body), 1) * gap

    steps.append(
        WorkflowStepConfig(
            id=SHELL_END_PLAYBOOK_ID,
            type=StepType.END_PLAYBOOK,
            label="End Playbook",
            locked=True,
            position=_pos(body_y),
            output_key="playbook_ended",
            description="Конец пользовательского сценария",
        )
    )
    steps.append(
        WorkflowStepConfig(
            id=SHELL_END_ID,
            type=StepType.END,
            label="End",
            locked=True,
            position=_pos(body_y + gap),
            description="Завершение процесса",
        )
    )

    edges: list[WorkflowEdge] = [
        WorkflowEdge(id="e-shell-start-evidence", from_step=SHELL_START_ID, to_step=SHELL_EVIDENCE_ID),
        WorkflowEdge(id="e-shell-evidence-compress", from_step=SHELL_EVIDENCE_ID, to_step=SHELL_COMPRESS_ID),
        WorkflowEdge(id="e-shell-compress-classify", from_step=SHELL_COMPRESS_ID, to_step=SHELL_CLASSIFY_ID),
        WorkflowEdge(id="e-shell-classify-start-pb", from_step=SHELL_CLASSIFY_ID, to_step=SHELL_START_PLAYBOOK_ID),
    ]

    if body:
        first_id = first_body_id or body[0].id
        last_id = last_body_id or body[-1].id
        edges.append(
            WorkflowEdge(id="e-shell-start-pb-body", from_step=SHELL_START_PLAYBOOK_ID, to_step=first_id)
        )
        edges.extend(body_edges or [])
        edges.append(
            WorkflowEdge(id="e-shell-body-end-pb", from_step=last_id, to_step=SHELL_END_PLAYBOOK_ID)
        )
    else:
        edges.append(
            WorkflowEdge(
                id="e-shell-start-pb-end-pb",
                from_step=SHELL_START_PLAYBOOK_ID,
                to_step=SHELL_END_PLAYBOOK_ID,
            )
        )

    edges.append(
        WorkflowEdge(id="e-shell-end-pb-end", from_step=SHELL_END_PLAYBOOK_ID, to_step=SHELL_END_ID)
    )

    return WorkflowTemplate(
        id=template_id,
        name=name,
        description=description,
        version=version,
        is_default=is_default,
        status=status,
        steps=steps,
        edges=edges,
        settings=settings or WorkflowSettings(),
    )
