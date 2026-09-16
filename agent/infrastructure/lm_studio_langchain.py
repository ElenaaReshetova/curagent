"""LM Studio model for LangChain (OpenAI-compatible API)."""

from langchain_openai import ChatOpenAI


def create_lm_studio_model(
    base_url: str = "http://localhost:1234/v1",
    model: str = "local-model",
    api_key: str = "lm-studio",
    temperature: float = 0.7,
    max_tokens: int = 16384,
) -> ChatOpenAI:
    """
    Create ChatOpenAI pointing to LM Studio (OpenAI-compatible API).

    LM Studio exposes OpenAI-compatible API at http://localhost:1234/v1 by default.
    """
    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
