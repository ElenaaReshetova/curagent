"""LM Studio model configuration (OpenAI-compatible API)."""

from openai import AsyncOpenAI

from agents import OpenAIChatCompletionsModel


def create_lm_studio_model(
    base_url: str = "http://localhost:1234/v1",
    model: str = "local-model",
    api_key: str = "lm-studio",
) -> OpenAIChatCompletionsModel:
    """
    Create OpenAI Chat Completions model pointing to LM Studio.

    LM Studio exposes OpenAI-compatible API at http://localhost:1234/v1 by default.
    """
    client = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
    )
    return OpenAIChatCompletionsModel(model=model, openai_client=client)
