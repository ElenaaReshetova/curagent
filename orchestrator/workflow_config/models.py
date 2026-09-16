"""Workflow template + registry models for Playbook designer."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class StepType(str, Enum):
    START = "start"
    SKILL = "skill"
    SCRIPT = "script"
    APPROVAL = "approval"
    WAIT_CONTEXT = "wait_context"
    GATEWAY_OR = "gateway_or"
    GATEWAY_AND = "gateway_and"
    START_PLAYBOOK = "start_playbook"
    END_PLAYBOOK = "end_playbook"
    END = "end"
    # Legacy / hidden
    DECISION = "decision"  # alias of gateway_or
    TOOL = "tool"
    SYSTEM = "system"
    VALIDATION = "validation"
    PUBLICATION = "publication"
    PARALLEL = "parallel"
    SUB_PLAYBOOK = "sub_playbook"
    HUMAN_TASK = "human_task"
    NORMALIZE = "normalize"
    CLASSIFY = "classify"
    PLAN = "plan"
    COLLECT_EVIDENCE = "collect_evidence"
    EXECUTE_VERIFY_LOOP = "execute_verify_loop"
    EXECUTE = "execute"
    VERIFY = "verify"
    COMPLIANCE = "compliance"
    PUBLISH = "publish"
    ESCALATE = "escalate"


GATEWAY_OR_TYPES = frozenset({StepType.GATEWAY_OR, StepType.DECISION})
GATEWAY_AND_TYPES = frozenset({StepType.GATEWAY_AND})
GATEWAY_TYPES = GATEWAY_OR_TYPES | GATEWAY_AND_TYPES


def is_gateway_or(step_type: StepType | str) -> bool:
    try:
        return StepType(step_type) in GATEWAY_OR_TYPES
    except ValueError:
        return False


def is_gateway_and(step_type: StepType | str) -> bool:
    try:
        return StepType(step_type) in GATEWAY_AND_TYPES
    except ValueError:
        return False


def is_gateway(step_type: StepType | str) -> bool:
    try:
        return StepType(step_type) in GATEWAY_TYPES
    except ValueError:
        return False


STEP_TYPE_META: dict[str, dict[str, Any]] = {
    StepType.START: {
        "label": "Start",
        "description": "Точка входа playbook",
        "color": "#16a34a",
        "group": "result",
        "icon": "▶",
        "locked_default": True,
    },
    StepType.SKILL: {
        "label": "Skill",
        "description": "LLM skill (SKILL.md); может вызывать Capabilities",
        "color": "#6366f1",
        "group": "execution",
        "icon": "🧠",
    },
    StepType.SCRIPT: {
        "label": "Script",
        "description": "Детерминированный скрипт (evidence, verify, publish…)",
        "color": "#0ea5e9",
        "group": "execution",
        "icon": "⌘",
    },
    StepType.WAIT_CONTEXT: {
        "label": "Wait / Signal",
        "description": "Прерывание: доп. контекст, сигнал, ожидание",
        "color": "#f59e0b",
        "group": "interaction",
        "icon": "⏸",
    },
    StepType.APPROVAL: {
        "label": "Approval",
        "description": "Прерывание: подтверждение человеком",
        "color": "#ec4899",
        "group": "interaction",
        "icon": "👤",
    },
    StepType.GATEWAY_OR: {
        "label": "Gateway ИЛИ",
        "description": "XOR-ветвление: yes/no (verify) или skill id (config.mode=route_skill)",
        "color": "#8b5cf6",
        "group": "execution",
        "icon": "*",
    },
    StepType.GATEWAY_AND: {
        "label": "Gateway И",
        "description": "Параллельный gateway (AND): fork / join",
        "color": "#7c3aed",
        "group": "execution",
        "icon": "+",
    },
    StepType.START_PLAYBOOK: {
        "label": "Start Playbook",
        "description": "Начало пользовательского сценария (после classify)",
        "color": "#0d9488",
        "group": "result",
        "icon": "▸",
        "locked_default": True,
    },
    StepType.END_PLAYBOOK: {
        "label": "End Playbook",
        "description": "Конец пользовательского сценария",
        "color": "#0f766e",
        "group": "result",
        "icon": "◂",
        "locked_default": True,
    },
    StepType.END: {
        "label": "End",
        "description": "Завершение",
        "color": "#94a3b8",
        "group": "result",
        "icon": "⏹",
        "locked_default": True,
    },
}

for st, label in [
    (StepType.DECISION, "Decision (legacy → Gateway ИЛИ)"),
    (StepType.TOOL, "Capability (legacy)"),
    (StepType.SYSTEM, "System"),
    (StepType.VALIDATION, "Validation"),
    (StepType.PUBLICATION, "Publication"),
    (StepType.PARALLEL, "Parallel"),
    (StepType.SUB_PLAYBOOK, "Sub-playbook"),
    (StepType.HUMAN_TASK, "Human Task"),
    (StepType.EXECUTE_VERIFY_LOOP, "Execute + Verify"),
    (StepType.NORMALIZE, "Normalize"),
]:
    STEP_TYPE_META[st] = {
        "label": label,
        "description": "Legacy",
        "color": "#475569",
        "group": "legacy",
        "icon": "•",
        "hidden": True,
    }


# Known script handlers for designer dropdown
SCRIPT_CATALOG: list[dict[str, str]] = [
    {"id": "collect_evidence", "label": "Collect evidence"},
    {"id": "compress_context", "label": "Compress context"},
    {"id": "verify", "label": "Verify artifact"},
    {"id": "publish", "label": "Publish artifact"},
    {"id": "compliance", "label": "Compliance check"},
]


class InputMapping(BaseModel):
    param: str
    source_step: str
    source_output: str = "output"


class WorkflowStepConfig(BaseModel):
    id: str
    type: StepType
    label: str
    enabled: bool = True
    locked: bool = False
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})
    description: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    skill_id: Optional[str] = None
    script_id: Optional[str] = None
    tool_id: Optional[str] = None  # legacy
    capability_id: Optional[str] = None  # legacy step binding; skills use capabilities via LLM tools
    system_handler: Optional[str] = None
    input_mappings: list[InputMapping] = Field(default_factory=list)
    output_key: Optional[str] = None
    model_profile: str = "default"
    max_input_tokens: int = 24000
    max_output_tokens: int = 8000


class WorkflowEdge(BaseModel):
    id: str
    from_step: str
    to_step: str
    label: Optional[str] = None


class WorkflowSettings(BaseModel):
    max_rework: int = 3
    publish_retries: int = 5
    classify_confidence_threshold: float = 0.3
    default_timeout_minutes: int = 10
    publication_target: str = "callback"


class WorkflowTemplate(BaseModel):
    id: str
    name: str
    description: str = ""
    version: int = 1
    is_default: bool = False
    status: str = "draft"
    steps: list[WorkflowStepConfig]
    edges: list[WorkflowEdge]
    settings: WorkflowSettings = Field(default_factory=WorkflowSettings)

    @model_validator(mode="after")
    def validate_graph(self) -> WorkflowTemplate:
        step_ids = {s.id for s in self.steps}
        for edge in self.edges:
            if edge.from_step not in step_ids or edge.to_step not in step_ids:
                raise ValueError(f"Edge {edge.id} references unknown step")
        return self


class SkillDef(BaseModel):
    id: str
    name: str
    description: str = ""
    capability_id: Optional[str] = None
    # Skills may list allowed capability APIs (tool cards for LLM)
    allowed_capabilities: list[str] = Field(default_factory=list)
    path: Optional[str] = None


class ModelProfileDef(BaseModel):
    id: str
    name: str
    description: str = ""
