"""Skill-executor system prompt assembly (no LangChain imports)."""

from __future__ import annotations

import re

EXECUTOR_INSTRUCTIONS = """You are a Skill Executor sub-agent in an enterprise multi-agent platform.
Produce the COMPLETE artifact as specified in the assigned Skill — never summarize or give a high-level overview.
Do NOT call any delivery or publish tools. Your output will be verified independently and published by another agent.
Return the full structured document in your Final Answer.
Default language policy: match the user's message language, BUT any Bound Rules about output language override this completely."""


_FORCE_RU_RE = re.compile(
    r"(ru-output-language|написан[аы]? на русском|полный документ на русском|"
    r"must be written in russian|artifacts must be written in russian)",
    re.IGNORECASE,
)


def forces_russian_output(rules_markdown: str | None) -> bool:
    """True when bound rules require Russian user-facing output."""
    text = (rules_markdown or "").strip()
    return bool(text and _FORCE_RU_RE.search(text))


def language_hard_constraint(rules_markdown: str | None) -> str:
    """Short hard constraint to pin at the top of system + user messages."""
    if forces_russian_output(rules_markdown):
        return (
            "[OUTPUT LANGUAGE — HARD CONSTRAINT]\n"
            "Пиши ВЕСЬ артефакт на русском языке: заголовки, секции, требования, "
            "acceptance criteria, таблицы и списки.\n"
            "English section titles from the skill template are examples only — "
            "переведи их на русский (например: Introduction → Введение, "
            "Functional Requirements → Функциональные требования).\n"
            "Do not mix languages. Russian only."
        )
    return ""


def build_executor_system_prompt(
    skill_instructions: str = "",
    rules_markdown: str | None = None,
    *,
    rework: bool = False,
) -> str:
    """Assemble the skill-executor system prompt (bound rules before skill)."""
    parts: list[str] = []
    hard = language_hard_constraint(rules_markdown)
    if hard:
        parts.append(hard)
    parts.append(EXECUTOR_INSTRUCTIONS)
    if rules_markdown and rules_markdown.strip():
        parts.append(
            "## Bound Rules (MUST APPLY — highest priority)\n"
            "These rules override the Assigned Skill template and any default "
            "language policy. If a Bound Rule conflicts with the skill markdown "
            "(including English headings), follow the Bound Rule.\n\n"
            + rules_markdown.strip()
        )
    if skill_instructions:
        parts.append("## Assigned Skill\n\n" + skill_instructions)
    if rework:
        parts.append(
            "## Rework mode\n"
            "You are revising an existing draft. Apply ALL reviewer/rework feedback.\n"
            "When feedback conflicts with the default skill template (section order, "
            "headings, emphasis), FOLLOW THE FEEDBACK.\n"
            "Do not regenerate from scratch and ignore the draft — edit the draft.\n"
            "Return the COMPLETE revised document."
        )
    return "\n\n".join(parts)
