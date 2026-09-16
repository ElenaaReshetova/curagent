"""Deterministic + heuristic task classification for skill routing."""

from __future__ import annotations

import re

from src.agent.infrastructure.skills_loader import list_skills_metadata
from src.orchestrator.models import ArtifactType, RoutingDecision

# Skill → artifact type mapping
_SKILL_ARTIFACT: dict[str, ArtifactType] = {
    "business-requirements": ArtifactType.BUSINESS_REQUIREMENTS,
    "system-requirements": ArtifactType.SYSTEM_REQUIREMENTS,
    "test-case-design": ArtifactType.TEST_CASE_PACK,
    "code-analysis": ArtifactType.CODE_ANALYSIS,
    "general": ArtifactType.GENERAL,
}

# What the user asked to *produce* (wins over section/topic keywords).
_INTENT_RULES: list[tuple[str, list[str]]] = [
    ("system-requirements", [
        r"системн\w*\s+требован",
        r"\bsystem\s+requirements?\b",
        r"\bsrs\b",
        r"(?:сгенерируй|напиши|подготовь|создай)\s+системн",
        r"\btechnical\s+spec(?:ification)?\b",
        r"\bтехн(?:ическ)?\w*\s+(?:спецификац|требован)",
    ]),
    ("business-requirements", [
        r"бизнес.?требован",
        r"\bbrd\b",
        r"\bprd\b",
        r"(?:сгенерируй|напиши|подготовь|создай)\s+(?:бизнес|prd|brd)",
        r"\bproduct\s+requirements?\b",
        r"\bfeature\s+spec(?:ification)?\b",
    ]),
    ("test-case-design", [
        r"(?:сгенерируй|напиши|подготовь|создай|состав)\w*\s+тест",
        r"\btest\s+(?:case|plan|coverage)\b",
        r"\bплан\s+тестирования\b",
    ]),
    ("code-analysis", [
        r"(?:сделай|проведи)\s+(?:code\s+)?review",
        r"\bcode\s+review\b",
        r"\bанализ\s+кода\b",
        r"\bревью\s+кода\b",
        r"\bsecurity\s+scan\b",
    ]),
]

# Supporting / topical hints — may appear inside another artifact request.
# Kept weak so they cannot override an explicit intent.
_TOPIC_RULES: list[tuple[str, list[str]]] = [
    ("code-analysis", [
        r"\bstatic analysis\b", r"\breview\b.*\bcode\b",
    ]),
    ("test-case-design", [
        r"\btest case\b", r"\btest plan\b", r"\bтест-кейс", r"\bтест кейс",
        r"\bqa\b",
    ]),
    ("system-requirements", [
        r"\bnfr\b", r"\bapi spec\b", r"\bархитектур",
        r"\bfunctional requirements?\b", r"\bнефункциональн",
    ]),
    ("business-requirements", [
        r"\buser stor", r"\bacceptance criteria\b",
        r"\bметрик\w*\s+успех", r"\bsuccess metrics?\b",
        r"\bp0\b", r"\bp1\b", r"\bmoscow\b",
    ]),
]

_INTENT_WEIGHT = 0.75
_TOPIC_WEIGHT = 0.15
_DESC_OVERLAP_CAP = 0.15


def detect_language(text: str) -> str:
    cyrillic = len(re.findall(r"[а-яА-ЯёЁ]", text))
    latin = len(re.findall(r"[a-zA-Z]", text))
    if cyrillic > latin:
        return "ru"
    if latin > 0:
        return "en"
    return "auto"


def _match_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pat, text, re.IGNORECASE) for pat in patterns)


def _score_skill(text: str, skill_name: str, description: str) -> float:
    """Score how well text matches a skill via intent, topics, and description."""
    lower = text.lower()
    score = 0.0

    for skill, patterns in _INTENT_RULES:
        if skill == skill_name and _match_any(lower, patterns):
            score += _INTENT_WEIGHT
            break

    for skill, patterns in _TOPIC_RULES:
        if skill == skill_name and _match_any(lower, patterns):
            score += _TOPIC_WEIGHT
            break

    # Weak metadata overlap — never enough to beat a clear intent alone.
    desc_tokens = set(re.findall(r"\w{4,}", description.lower()))
    text_tokens = set(re.findall(r"\w{4,}", lower))
    overlap = len(desc_tokens & text_tokens)
    score += min(overlap * 0.03, _DESC_OVERLAP_CAP)
    return min(score, 1.0)


def classify_task(description: str, title: str = "") -> RoutingDecision:
    """
    Route task to primary skill using intent-first keyword rules.

    Explicit artifact requests (e.g. «системные требования») outrank
    section/topic keywords that often appear inside that request
    (user stories, P0/P1, metrics, NFR, …).
    """
    combined = f"{title}\n{description}".strip()
    lower = combined.lower()
    skills = list_skills_metadata()
    skill_names = {s["name"] for s in skills}

    # Fast path: first matching intent wins (ordered by specificity in _INTENT_RULES).
    for skill_name, patterns in _INTENT_RULES:
        if skill_name not in skill_names and skill_name not in _SKILL_ARTIFACT:
            continue
        if _match_any(lower, patterns):
            best_skill = skill_name
            best_score = _INTENT_WEIGHT
            break
    else:
        best_skill = "general"
        best_score = 0.0
        for skill_meta in skills:
            name = skill_meta["name"]
            if name in ("general", "classify", "classify-task"):
                continue
            score = _score_skill(combined, name, skill_meta.get("description", ""))
            if score > best_score:
                best_score = score
                best_skill = name

        if best_score < 0.25:
            for skill_name, patterns in _TOPIC_RULES:
                if skill_name not in skill_names and skill_name not in _SKILL_ARTIFACT:
                    continue
                if _match_any(lower, patterns):
                    best_skill = skill_name
                    best_score = 0.4
                    break

    if best_score < 0.25:
        best_skill = "general"
        best_score = 0.5

    complexity = "low"
    word_count = len(combined.split())
    if word_count > 200 or combined.count("\n") > 10:
        complexity = "medium"
    if word_count > 500 or " and " in lower or " и " in lower:
        complexity = "high"

    artifact_type = _SKILL_ARTIFACT.get(best_skill, ArtifactType.GENERAL)
    requires_planning = complexity in ("medium", "high") and best_skill != "general"

    return RoutingDecision(
        primary_skill=best_skill,
        artifact_type=artifact_type,
        complexity=complexity,
        confidence=round(min(best_score, 1.0), 2),
        verifier_rubric_id=f"rubric_{best_skill}",
        requires_planning=requires_planning,
    )
