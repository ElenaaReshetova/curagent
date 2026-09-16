"""GigaChat model configuration for LangChain ReAct agent."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def create_gigachat_model(
    credentials: str | None = None,
    model: str = "GigaChat",
    scope: str | None = None,
    verify_ssl_certs: bool = True,
    timeout: int = 60,
):
    """
    Create GigaChat chat model for LangChain.

    Args:
        credentials: OAuth token or path to credentials file. Defaults to GIGACHAT_CREDENTIALS env.
        model: Model name (e.g. GigaChat, GigaChat-Pro).
        scope: OAuth scope. Defaults to GIGACHAT_SCOPE env or GIGACHAT_API_CORP.
        verify_ssl_certs: Whether to verify SSL certificates.
        timeout: Request timeout in seconds.

    Returns:
        GigaChat chat model instance.
    """
    from langchain_gigachat.chat_models import GigaChat

    creds = credentials or os.environ.get("GIGACHAT_CREDENTIALS")
    if not creds:
        raise ValueError(
            "GigaChat credentials required. Set GIGACHAT_CREDENTIALS env or pass credentials=..."
        )

    scope_val = scope or os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_CORP")

    return GigaChat(
        credentials=creds,
        model=model,
        scope=scope_val,
        verify_ssl_certs=verify_ssl_certs,
        timeout=timeout,
    )
