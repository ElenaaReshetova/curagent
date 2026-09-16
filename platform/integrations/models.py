"""Protocol integration connections — MCP, A2A, ACP."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ProtocolKind = Literal["MCP", "A2A", "ACP"]
ConnectionStatus = Literal["ready", "misconfigured", "disabled", "unknown"]


class IntegrationConnection(BaseModel):
    """UI/catalog projection of a protocol connection."""

    id: str
    key: str
    name: str
    protocol: ProtocolKind
    description: str = ""
    enabled: bool = True
    status: ConnectionStatus = "unknown"
    transport: str = ""
    tools: list[str] = Field(default_factory=list)
    linked_capabilities: list[str] = Field(default_factory=list)
    # Standard config snippet for this single connection (no root wrapper).
    config: dict[str, Any] = Field(default_factory=dict)


class IntegrationMetrics(BaseModel):
    total: int = 0
    mcp: int = 0
    a2a: int = 0
    acp: int = 0
    ready: int = 0
    misconfigured: int = 0
    disabled: int = 0


class IntegrationCatalogResponse(BaseModel):
    connections: list[IntegrationConnection] = Field(default_factory=list)
    metrics: IntegrationMetrics = Field(default_factory=IntegrationMetrics)
    # Combined standard config document for JSON view.
    config: dict[str, Any] = Field(default_factory=dict)


class IntegrationDetail(BaseModel):
    connection: IntegrationConnection
    # Exact standard document fragment for this protocol (e.g. {mcpServers:{...}}).
    config_document: dict[str, Any] = Field(default_factory=dict)
    linked_capabilities: list[dict[str, Any]] = Field(default_factory=list)
