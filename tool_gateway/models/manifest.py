"""Capability Definition + Tool Implementations (concept layer).

Capability = stable platform intent (contract, risk, policy).
ToolImplementation = concrete MCP/system/script realization picked by Resolver.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from src.tool_gateway.models.envelopes import ApprovalTier, ManifestStatus, SideEffectClass

OperationType = Literal["read", "search", "create", "update", "delete", "execute", "publish"]
RiskLevel = Literal["low", "medium", "high", "critical"]
ExecutionMode = Literal["read_only", "draft", "change_proposal", "autonomous"]
ImplStatus = Literal[
    "discovered", "pending_review", "approved", "disabled", "degraded", "quarantined",
]
ImplType = Literal["mcp", "system", "script"]


class ReversalContract(BaseModel):
    reversible: bool = False
    reversal_capability_id: Optional[str] = None
    compensation_hint: Optional[str] = None


class VisibilityRules(BaseModel):
    tenants: list[str] = Field(default_factory=lambda: ["*"])
    roles: list[str] = Field(default_factory=lambda: ["*"])
    skills: list[str] = Field(default_factory=lambda: ["*"])
    playbooks: list[str] = Field(default_factory=lambda: ["*"])


class AdapterBinding(BaseModel):
    """Resolved binding used by Dispatcher (derived from selected implementation)."""

    type: str  # system | script | mcp | http
    handler: Optional[str] = None
    mcp_server: Optional[str] = None
    tool_name: Optional[str] = None


class ToolImplementation(BaseModel):
    id: str
    type: ImplType = "mcp"
    server_id: Optional[str] = None
    tool_name: Optional[str] = None
    handler: Optional[str] = None
    status: ImplStatus = "approved"
    priority: int = 100
    risk_level: RiskLevel = "low"
    adapter_id: Optional[str] = None
    normalizer_id: Optional[str] = None
    selectors: dict[str, list[str]] = Field(default_factory=dict)
    timeout_seconds: int = 30
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_adapter_binding(self) -> AdapterBinding:
        if self.type == "mcp":
            return AdapterBinding(
                type="mcp",
                mcp_server=self.server_id,
                tool_name=self.tool_name,
            )
        return AdapterBinding(type=self.type, handler=self.handler)


_OP_TO_SIDE: dict[str, SideEffectClass] = {
    "read": SideEffectClass.READ,
    "search": SideEffectClass.READ,
    "create": SideEffectClass.WRITE,
    "update": SideEffectClass.WRITE,
    "delete": SideEffectClass.DESTRUCTIVE,
    "execute": SideEffectClass.WRITE,
    "publish": SideEffectClass.EXTERNAL_PUBLISH,
}

_SIDE_TO_OP: dict[str, OperationType] = {
    "read": "read",
    "write": "update",
    "destructive": "delete",
    "external_publish": "publish",
}

_RISK_TO_TIER: dict[str, ApprovalTier] = {
    "low": ApprovalTier.NONE,
    "medium": ApprovalTier.SOFT,
    "high": ApprovalTier.HARD,
    "critical": ApprovalTier.DESTRUCTIVE,
}

_TIER_TO_RISK: dict[str, RiskLevel] = {
    "none": "low",
    "soft": "medium",
    "hard": "high",
    "destructive": "critical",
}


class CapabilityManifest(BaseModel):
    """Stable Capability Definition + optional implementation list."""

    capability_id: str
    version: str = "1.0"
    manifest_version: int = 1
    name: str
    description: str = ""
    group: str = "general"
    status: ManifestStatus = ManifestStatus.PUBLISHED

    operation_type: OperationType = "execute"
    risk_level: RiskLevel = "low"

    idempotent: bool = False
    cacheable: bool = False
    requires_approval: bool = False
    allowed_execution_modes: list[ExecutionMode] = Field(
        default_factory=lambda: ["read_only", "draft", "change_proposal", "autonomous"]
    )

    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    implementations: list[ToolImplementation] = Field(default_factory=list)

    # Compat for existing Resolver / Policy / Dispatcher
    approval_tier: ApprovalTier = ApprovalTier.NONE
    side_effect_class: SideEffectClass = SideEffectClass.READ
    adapter_binding: AdapterBinding = Field(
        default_factory=lambda: AdapterBinding(type="system", handler="noop")
    )
    required_input_fields: list[str] = Field(default_factory=list)
    visibility: VisibilityRules = Field(default_factory=VisibilityRules)
    idempotency_required: bool = False
    reversal: ReversalContract = Field(default_factory=ReversalContract)
    timeout_seconds: int = 120
    evidence_max_age_seconds: int = 86400
    policy_tags: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)

        # Legacy single adapter_binding → implementations
        binding = d.get("adapter_binding")
        impls = d.get("implementations")
        if binding and not impls:
            b = binding if isinstance(binding, dict) else {}
            btype = b.get("type") or "system"
            impl: dict[str, Any] = {
                "id": f"{d.get('capability_id', 'cap')}.{btype}",
                "type": btype if btype in ("mcp", "system", "script") else "system",
                "status": "approved",
                "priority": 100,
                "enabled": True,
                "timeout_seconds": d.get("timeout_seconds", 30),
            }
            if btype == "mcp":
                impl["server_id"] = b.get("mcp_server")
                impl["tool_name"] = b.get("tool_name")
            else:
                impl["handler"] = b.get("handler")
            d["implementations"] = [impl]

        # Derive concept fields from legacy policy fields
        if "operation_type" not in d and "side_effect_class" in d:
            d["operation_type"] = _SIDE_TO_OP.get(str(d["side_effect_class"]), "execute")
        if "risk_level" not in d and "approval_tier" in d:
            d["risk_level"] = _TIER_TO_RISK.get(str(d["approval_tier"]), "low")
        if "requires_approval" not in d and "approval_tier" in d:
            d["requires_approval"] = str(d["approval_tier"]) not in ("none", "None", "")
        if "group" not in d:
            cid = str(d.get("capability_id", ""))
            if cid.startswith("task.") or cid in ("jira-add-comment",):
                d["group"] = "tracker"
            elif cid.startswith(("docs.", "repo.", "ci.", "artifact.")):
                d["group"] = cid.split(".", 1)[0]
            elif cid in (
                "classify-task", "normalize-task", "collect-evidence",
                "compress-context", "compliance-check", "http-callback",
            ):
                d["group"] = "platform"
            else:
                d["group"] = "general"

        schema = d.get("input_schema") or {}
        if isinstance(schema, dict) and "required" in schema and "required_input_fields" not in d:
            d["required_input_fields"] = list(schema.get("required") or [])
        elif "required_input_fields" not in d:
            d["required_input_fields"] = []

        return d

    @model_validator(mode="after")
    def sync_derived(self) -> CapabilityManifest:
        # Sync policy fields from concept fields when concept is authoritative
        side = _OP_TO_SIDE.get(self.operation_type, SideEffectClass.READ)
        object.__setattr__(self, "side_effect_class", side)

        if self.requires_approval:
            tier = _RISK_TO_TIER.get(self.risk_level, ApprovalTier.SOFT)
            if tier == ApprovalTier.NONE:
                tier = ApprovalTier.SOFT
            object.__setattr__(self, "approval_tier", tier)
        else:
            # Keep explicit critical→destructive even without flag
            if self.risk_level == "critical":
                object.__setattr__(self, "approval_tier", ApprovalTier.DESTRUCTIVE)
                object.__setattr__(self, "requires_approval", True)
            elif self.approval_tier == ApprovalTier.NONE:
                object.__setattr__(self, "approval_tier", _RISK_TO_TIER.get(self.risk_level, ApprovalTier.NONE))

        # required_input_fields from schema
        schema_req = list((self.input_schema or {}).get("required") or [])
        if schema_req and not self.required_input_fields:
            object.__setattr__(self, "required_input_fields", schema_req)

        # Ensure adapter_binding from primary approved implementation
        primary = self.resolve_implementation()
        if primary is not None:
            object.__setattr__(self, "adapter_binding", primary.to_adapter_binding())
            object.__setattr__(
                self,
                "timeout_seconds",
                max(self.timeout_seconds, primary.timeout_seconds),
            )
        elif not self.adapter_binding or (
            self.adapter_binding.type == "system" and self.adapter_binding.handler == "noop"
        ):
            # leave default
            pass

        if self.approval_tier == ApprovalTier.DESTRUCTIVE and not self.reversal.reversible:
            if (
                self.reversal.reversal_capability_id is None
                and self.side_effect_class == SideEffectClass.DESTRUCTIVE
            ):
                raise ValueError(
                    f"Destructive capability {self.capability_id} requires reversal contract"
                )

        if self.side_effect_class in (
            SideEffectClass.WRITE,
            SideEffectClass.DESTRUCTIVE,
            SideEffectClass.EXTERNAL_PUBLISH,
        ):
            object.__setattr__(self, "idempotency_required", True)

        return self

    def resolve_implementation(
        self,
        *,
        allowed_servers: Optional[list[str]] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[ToolImplementation]:
        """Pick best approved implementation (Resolver selection MVP)."""
        ctx = context or {}
        candidates: list[ToolImplementation] = []
        for impl in self.implementations:
            if not impl.enabled or impl.status != "approved":
                continue
            if allowed_servers and impl.type == "mcp" and impl.server_id:
                if impl.server_id not in allowed_servers:
                    continue
            if not self._matches_selectors(impl, ctx):
                continue
            candidates.append(impl)
        if not candidates:
            # Fallback: any enabled binding for platform/system
            for impl in self.implementations:
                if impl.enabled and impl.type in ("system", "script"):
                    candidates.append(impl)
        if not candidates:
            return None
        candidates.sort(key=lambda i: i.priority, reverse=True)
        return candidates[0]

    @staticmethod
    def _matches_selectors(impl: ToolImplementation, context: dict[str, Any]) -> bool:
        selectors = impl.selectors or {}
        for key, allowed in selectors.items():
            if not allowed:
                continue
            # Accept both camelCase and snake_case context keys
            snake = "".join("_" + c.lower() if c.isupper() else c for c in key).lstrip("_")
            val = context.get(key) or context.get(snake)
            if val is None:
                continue
            if val not in allowed:
                return False
        return True
