"""Independent LLM-based semantic verification (separate from Executor)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from src.orchestrator.models import (
    ArtifactDraft,
    NormalizedTaskSpec,
    VerificationFinding,
    VerificationStatus,
)

logger = logging.getLogger(__name__)

VERIFIER_SYSTEM = """You are an Independent Verifier in an enterprise multi-agent platform.
You do NOT produce content. You evaluate artifact quality against the original task and skill rubric.
Be strict but fair: minor formatting issues should be warnings, not blocking rework.
Artifacts may be in Russian or English — evaluate content quality, not language.
Respond ONLY with valid JSON (no markdown fences):
{
  "status": "pass" | "rework" | "fail",
  "scores": {"completeness": 0.0-1.0, "clarity": 0.0-1.0, "task_alignment": 0.0-1.0},
  "findings": [{"section": "...", "severity": "blocking"|"warning", "message": "..."}],
  "required_fixes": ["..."]
}"""


def _build_verify_prompt(task: NormalizedTaskSpec, artifact: ArtifactDraft) -> str:
    return f"""Evaluate this artifact produced for the task below.

## Original Task
Title: {task.title}
Description: {task.description}
Skill: {artifact.skill}
Artifact type: {artifact.type.value}

## Artifact (version {artifact.version})
{artifact.content[:12000]}

## Rubric
- Completeness: all required sections for {artifact.type.value} must be present with concrete content
- Clarity: unambiguous, actionable language
- Task alignment: artifact addresses the original task
- No placeholder text like "TBD", "TODO", "lorem ipsum"
- Blocking issues → status "rework" or "fail"
"""


def _parse_verifier_response(text: str) -> dict[str, Any]:
    """Extract JSON from LLM verifier response."""
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Extract JSON block
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    logger.warning("Verifier returned non-JSON, defaulting to rework")
    return {
        "status": "rework",
        "scores": {"completeness": 0.5},
        "findings": [{"section": "verifier", "severity": "blocking", "message": "Could not parse verifier output"}],
        "required_fixes": ["Regenerate artifact with complete structured sections"],
    }


async def verify_with_llm(
    llm: Any,
    task: NormalizedTaskSpec,
    artifact: ArtifactDraft,
) -> tuple[VerificationStatus, dict[str, float], list[VerificationFinding], list[str]]:
    """Run semantic verification via LLM."""
    prompt = _build_verify_prompt(task, artifact)
    try:
        response = await llm.ainvoke(
            [{"role": "system", "content": VERIFIER_SYSTEM}, {"role": "user", "content": prompt}]
        )
        raw = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.exception("Verifier LLM call failed: %s", e)
        return (
            VerificationStatus.REWORK,
            {"completeness": 0.0},
            [VerificationFinding(section="verifier", severity="blocking", message=str(e))],
            ["Retry verification after LLM availability restored"],
        )

    parsed = _parse_verifier_response(raw)
    status_str = parsed.get("status", "rework")
    try:
        status = VerificationStatus(status_str)
    except ValueError:
        status = VerificationStatus.REWORK

    scores = {k: float(v) for k, v in parsed.get("scores", {}).items()}
    findings = [
        VerificationFinding(
            section=f.get("section", "unknown"),
            severity=f.get("severity", "warning"),
            message=f.get("message", ""),
        )
        for f in parsed.get("findings", [])
    ]
    required_fixes = list(parsed.get("required_fixes", []))
    return status, scores, findings, required_fixes
