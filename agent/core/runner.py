"""Agent runner: LangChain ReAct agent with GigaChat, Skills, and tools."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

try:
    # LangChain 0.3.x
    from langchain.agents import AgentExecutor, create_react_agent
except (ImportError, TypeError):
    # LangChain 1.x: ReAct + AgentExecutor live in langchain-classic (pulled in by langchain 1.x)
    # Also catch TypeError: some Python 3.14 + pydantic combos break langchain.agents import.
    from langchain_classic.agents import AgentExecutor, create_react_agent

from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool

from src.agent.core.task_context import TaskContext
from src.agent.core.executor_prompt import EXECUTOR_INSTRUCTIONS, build_executor_system_prompt
from src.agent.infrastructure.delivery_resolver import (
    format_delivery_instructions,
    resolve_delivery,
)
from src.agent.infrastructure.gigachat import create_gigachat_model
from src.agent.infrastructure.langchain_chat_tool import create_send_to_chat_tool
from src.agent.infrastructure.lm_studio_langchain import create_lm_studio_model
from src.agent.infrastructure.skills_loader import load_skills

logger = logging.getLogger(__name__)

DEFAULT_INSTRUCTIONS = """You are an autonomous AI agent that executes assigned tasks.
Always respond in the SAME language as the user's message (Russian → Russian, English → English).
When you complete a task, deliver the result using the tool specified in the task instructions.
Use available Skills when they help with the task.
When delivering: pass your FULL output to the delivery tool — never summarize or shorten the response."""

REACT_PROMPT = PromptTemplate.from_template(
    """{system}

Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}"""
)


class ReActAgentWrapper:
    """Wrapper for LangChain ReAct agent with GigaChat. Builds executor per task for context-bound tools."""

    def __init__(
        self,
        llm: Any,
        skills_instructions: str,
        mcp_tools: list[BaseTool],
    ):
        self.llm = llm
        self.skills_instructions = skills_instructions
        self.mcp_tools = mcp_tools

    async def run(
        self,
        description: str,
        task_context: TaskContext,
        available_mcp_names: list[str],
        max_iterations: int = 10,
    ) -> str:
        """Execute task with ReAct agent."""
        send_to_chat = create_send_to_chat_tool(task_context)
        tools: list[BaseTool] = [send_to_chat] + self.mcp_tools

        full_instructions = DEFAULT_INSTRUCTIONS
        if self.skills_instructions:
            full_instructions += "\n\n## Available Skills\n\n" + self.skills_instructions

        delivery = resolve_delivery(
            source=task_context.source,
            source_id=task_context.source_id,
            available_mcp_names=available_mcp_names,
        )
        if not delivery:
            task_preface = (
                "[RESPONSE INSTRUCTIONS] To deliver your answer, call send_to_chat with your message.\n\n"
            )
        else:
            task_preface = format_delivery_instructions(delivery)
        full_task = task_preface + f"[TASK]\n{description}"

        prompt = REACT_PROMPT.partial(system=full_instructions)
        agent = create_react_agent(self.llm, tools, prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=max_iterations,
        )

        result = await executor.ainvoke({"input": full_task})
        return result.get("output", "") or ""

    async def run_execute_only(
        self,
        description: str,
        skill_instructions: str,
        rework_fixes: list[str] | None = None,
        previous_artifact: str | None = None,
        rules_markdown: str | None = None,
        max_iterations: int = 12,
    ) -> str:
        """Execute skill without delivery tools — used by Temporal Skill Executor activity."""
        from src.agent.core.executor_prompt import language_hard_constraint

        full_instructions = build_executor_system_prompt(
            skill_instructions,
            rules_markdown,
            rework=bool(rework_fixes or previous_artifact),
        )
        parts: list[str] = []
        hard = language_hard_constraint(rules_markdown)
        if hard:
            parts.append(hard)
        if rework_fixes:
            fixes = "\n".join(f"- {f}" for f in rework_fixes)
            parts.append(f"[REVIEWER / REWORK FEEDBACK — MUST APPLY]\n{fixes}")
        if previous_artifact and previous_artifact.strip():
            parts.append(
                "[CURRENT DRAFT TO REVISE — return the full updated document]\n"
                + previous_artifact.strip()[:14000]
            )
        parts.append(f"[TASK]\n{description}")
        if rework_fixes and previous_artifact:
            parts.append(
                "[INSTRUCTION]\n"
                "Apply every feedback item to the current draft above. "
                "Keep valid content that is not contradicted by feedback. "
                "Output only the full revised artifact."
            )
        if hard:
            parts.append(
                "[FINAL REMINDER]\n"
                "Output language is Russian for the entire document. "
                "Translate template headings into Russian."
            )
        task_body = "\n\n".join(parts)

        # Direct LLM invoke (no ReAct loop) — executor does not deliver or call tools
        messages = [
            {"role": "system", "content": full_instructions},
            {"role": "user", "content": task_body},
        ]
        response = await self.llm.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        return content or ""


def build_agent(
    skills_dir: Optional[Path] = None,
    skills_dirs: Optional[list[Path]] = None,
    project_root: Optional[Path] = None,
    gigachat_credentials: Optional[str] = None,
    gigachat_model: str = "GigaChat",
    lm_studio_url: Optional[str] = None,
    lm_studio_model: str = "local-model",
    mcp_servers: Optional[list] = None,
) -> ReActAgentWrapper:
    """Build ReAct agent with GigaChat or LM Studio, Skills, and tools.

    Backend selection:
    - GigaChat if gigachat_credentials is set
    - LM Studio (OpenAI-compatible) otherwise
    - LM Studio defaults: lm_studio_url=http://localhost:1234/v1, lm_studio_model=local-model

    Skills are loaded from Anthropic-style directories.
    MCP tools are not yet integrated with LangChain; pass empty list for now.
    """
    skills_instructions = load_skills(
        skills_dir=skills_dir,
        skills_dirs=skills_dirs,
        project_root=project_root,
    )

    if gigachat_credentials:
        llm = create_gigachat_model(
            credentials=gigachat_credentials,
            model=gigachat_model,
        )
        logger.info("Using GigaChat backend (model=%s)", gigachat_model)
    else:
        base_url = lm_studio_url or "http://localhost:1234/v1"
        llm = create_lm_studio_model(
            base_url=base_url,
            model=lm_studio_model,
        )
        logger.info("Using LM Studio backend (url=%s, model=%s)", base_url, lm_studio_model)

    mcp_tools: list[BaseTool] = []
    if mcp_servers:
        logger.info("MCP servers provided but LangChain MCP integration not yet configured")

    return ReActAgentWrapper(
        llm=llm,
        skills_instructions=skills_instructions,
        mcp_tools=mcp_tools,
    )


async def run_task(
    agent: ReActAgentWrapper,
    description: str,
    task_context: TaskContext,
    max_turns: int = 10,
    available_mcp_names: list[str] | None = None,
) -> str:
    """
    Execute a task with the ReAct agent.

    Returns the final output text.
    """
    mcp_names = available_mcp_names or []
    return await agent.run(
        description=description,
        task_context=task_context,
        available_mcp_names=mcp_names,
        max_iterations=max_turns,
    )


async def execute_skill(
    agent: ReActAgentWrapper,
    description: str,
    skill_name: str,
    project_root: Optional[Path] = None,
    rework_fixes: list[str] | None = None,
    previous_artifact: str | None = None,
    rules_markdown: str | None = None,
    max_turns: int = 12,
) -> str:
    """Execute a task with a single skill binding, no delivery."""
    from src.agent.infrastructure.skills_loader import load_skill_by_name

    skill_instructions = load_skill_by_name(skill_name, project_root=project_root)
    if not skill_instructions and skill_name != "general":
        logger.warning("Skill %r not found, falling back to general", skill_name)
        skill_instructions = load_skill_by_name("general", project_root=project_root)
    return await agent.run_execute_only(
        description=description,
        skill_instructions=skill_instructions,
        rework_fixes=rework_fixes,
        previous_artifact=previous_artifact,
        rules_markdown=rules_markdown,
        max_iterations=max_turns,
    )
