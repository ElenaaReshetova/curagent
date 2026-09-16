"""graph contract-flow validation."""

from __future__ import annotations

from typing import Any

from src.platform.contracts.registry import contracts_compatible, interface_contracts
from src.platform.graphs.workflow_dsl import DslNode, WorkflowDsl


def _node_type(node: DslNode) -> str:
    return str((node.config or {}).get("type") or "").upper()


def _is_trigger(node: DslNode) -> bool:
    t = _node_type(node)
    return t.endswith("TRIGGER") or t in {"SELF_SERVE_TRIGGER", "EVENT_TRIGGER", "SCHEDULE_TRIGGER"}


def _interface_key(node: DslNode) -> str:
    cfg = node.config or {}
    return str(cfg.get("interface_key") or cfg.get("agentIdentifier") or "").strip()


def validate_graph_contracts(
    graph: WorkflowDsl,
    *,
    entry_contract_key: str = "",
    exit_contract_key: str = "",
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not graph.nodes:
        return {"errors": errors, "warnings": warnings}

    node_map = {n.identifier: n for n in graph.nodes}
    adj: dict[str, list[str]] = {n.identifier: [] for n in graph.nodes}
    for edge in graph.connections:
        if edge.sourceIdentifier in adj:
            adj[edge.sourceIdentifier].append(edge.targetIdentifier)

    starts = [n for n in graph.nodes if _is_trigger(n)]
    if not starts:
        trigger = graph.trigger_node()
        starts = [trigger] if trigger else []
    if not starts:
        return {"errors": errors, "warnings": warnings}

    initial_contract = entry_contract_key or "WorkItem@1"
    stack: list[tuple[str, str]] = [(start.identifier, initial_contract) for start in starts]
    seen_states: set[tuple[str, str]] = set()
    exit_contracts: set[str] = set()

    while stack:
        node_key, incoming_contract = stack.pop()
        state = (node_key, incoming_contract)
        if state in seen_states:
            continue
        seen_states.add(state)
        node = node_map.get(node_key)
        if not node:
            continue
        outgoing_contract = incoming_contract

        if _node_type(node) == "AI_AGENT":
            iface = _interface_key(node)
            expected_in, expected_out = interface_contracts(iface) if iface else ("", "")
            if expected_in and not contracts_compatible(incoming_contract, expected_in):
                errors.append({
                    "code": "CONTRACT_FLOW_MISMATCH",
                    "message": (
                        f"Step '{node.title or node.identifier}' expects {expected_in}, "
                        f"but upstream produces {incoming_contract}"
                    ),
                })
            if expected_out:
                outgoing_contract = expected_out
            elif expected_in:
                warnings.append({
                    "code": "SKILL_SLOT_NO_OUTPUT_CONTRACT",
                    "message": f"AI Agent '{node.title or node.identifier}' has no output contract mapping",
                })

        next_nodes = adj.get(node_key, [])
        if next_nodes:
            stack.extend((next_node, outgoing_contract) for next_node in next_nodes)
        else:
            exit_contracts.add(outgoing_contract)

    if exit_contract_key:
        for current in sorted(exit_contracts):
            if current and not contracts_compatible(current, exit_contract_key):
                errors.append({
                    "code": "GRAPH_EXIT_CONTRACT_MISMATCH",
                    "message": (
                        f"Graph exit contract '{exit_contract_key}' is incompatible "
                        f"with final step output '{current}'"
                    ),
                })

    return {"errors": errors, "warnings": warnings}
