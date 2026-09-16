"""Artifact preview helpers used by human checkpoints."""

from __future__ import annotations

from types import SimpleNamespace

from src.orchestrator.pipeline_runner import (
    PipelineContext,
    _artifact_content,
    _coerce_artifact,
    _resolve_artifact_preview,
)
from src.orchestrator.models import ArtifactDraft, ArtifactType, WorkflowInput


def _ctx() -> PipelineContext:
    return PipelineContext(
        raw=WorkflowInput(
            task_id="t1",
            description="desc",
            source="slack",
            source_id="s1",
            created_at="2026-07-23T00:00:00Z",
        ),
        trace_id="tr",
    )


def test_artifact_content_reads_dict_payload():
    payload = {
        "artifact_id": "a1",
        "task_id": "t1",
        "type": "business_requirements",
        "skill": "business-requirements",
        "version": 2,
        "content": "Привет, это BRD " * 20,
        "content_checksum": "x",
    }
    # This is the Temporal default-converter bug: getattr(dict, "content") == "".
    assert getattr(payload, "content", "") == ""
    assert "Привет" in _artifact_content(payload)


def test_resolve_preview_falls_back_to_step_outputs():
    ctx = _ctx()
    body = "Полный текст бизнес-требований " * 30
    ctx.step_outputs["step-refine"] = {
        "artifact": {
            "artifact_id": "a1",
            "task_id": "t1",
            "type": "business_requirements",
            "skill": "business-requirements",
            "version": 2,
            "content": body,
            "content_checksum": "x",
        }
    }
    preview = _resolve_artifact_preview(ctx)
    assert preview.startswith("Полный текст")
    assert len(preview) > 100


def test_coerce_artifact_from_dict():
    payload = {
        "artifact_id": "a1",
        "task_id": "t1",
        "type": ArtifactType.BUSINESS_REQUIREMENTS,
        "skill": "business-requirements",
        "version": 1,
        "content": "body",
        "content_checksum": "x",
    }
    art = _coerce_artifact(payload)
    assert isinstance(art, ArtifactDraft)
    assert art.content == "body"
