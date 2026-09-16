"""Temporal step plan produced from workflow DSL.

This is the ONLY intermediate between normalize(workflow DSL) and Temporal run.
Not a second product DSL — just typed steps for the interpreter.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class ActivityStep:
    id: str
    name: str
    activity_name: str
    input: dict[str, Any]
    output_mapping: list[dict[str, str]] = field(default_factory=list)
    wait_for_signal: bool = False
    signal_name: Optional[str] = None
    next_step: Optional[str] = None
    on_failure: str = "terminate"
    outlets: list[dict[str, Any]] = field(default_factory=list)  # HITL / condition edges
    worker: str = ""  # Temporal activity name from node_types catalog (YAML `worker`)


@dataclass
class ConditionBranch:
    id: str
    expression: str
    next_step: Optional[str]


@dataclass
class ConditionStep:
    id: str
    name: str
    branches: list[ConditionBranch]
    fallback: Optional[str] = None


@dataclass
class TemporalPlan:
    name: str
    version: str
    description: str
    trigger: dict[str, Any]
    inputs: list[dict[str, Any]]
    steps: dict[str, ActivityStep | ConditionStep]
    step_order: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def _step(s: ActivityStep | ConditionStep) -> dict[str, Any]:
            if isinstance(s, ActivityStep):
                return {"kind": "activity", **asdict(s)}
            return {
                "kind": "condition",
                "id": s.id,
                "name": s.name,
                "branches": [asdict(b) for b in s.branches],
                "fallback": s.fallback,
            }

        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "trigger": self.trigger,
            "inputs": self.inputs,
            "step_order": list(self.step_order),
            "steps": {sid: _step(st) for sid, st in self.steps.items()},
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TemporalPlan":
        steps: dict[str, ActivityStep | ConditionStep] = {}
        for sid, st in (raw.get("steps") or {}).items():
            kind = st.get("kind")
            if kind == "activity":
                steps[sid] = ActivityStep(
                    id=st.get("id") or sid,
                    name=st.get("name") or sid,
                    activity_name=st.get("activity_name") or st.get("worker") or "",
                    input=dict(st.get("input") or {}),
                    output_mapping=list(st.get("output_mapping") or []),
                    wait_for_signal=bool(st.get("wait_for_signal")),
                    signal_name=st.get("signal_name"),
                    next_step=st.get("next_step"),
                    on_failure=str(st.get("on_failure") or "terminate"),
                    outlets=list(st.get("outlets") or []),
                    worker=str(st.get("worker") or st.get("activity_name") or ""),
                )
            elif kind == "condition":
                steps[sid] = ConditionStep(
                    id=st.get("id") or sid,
                    name=st.get("name") or sid,
                    branches=[
                        ConditionBranch(
                            id=b["id"],
                            expression=b.get("expression") or "",
                            next_step=b.get("next_step"),
                        )
                        for b in (st.get("branches") or [])
                    ],
                    fallback=st.get("fallback"),
                )
            else:
                raise ValueError(f"unknown step kind: {kind}")
        return cls(
            name=str(raw.get("name") or "workflow"),
            version=str(raw.get("version") or "1.0"),
            description=str(raw.get("description") or ""),
            trigger=dict(raw.get("trigger") or {}),
            inputs=list(raw.get("inputs") or []),
            steps=steps,
            step_order=list(raw.get("step_order") or list(steps.keys())),
        )
