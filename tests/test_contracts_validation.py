"""Typed contract-flow validation for AI Agent nodes."""

from __future__ import annotations

from src.platform.contracts.validation import validate_graph_contracts
from src.platform.graphs.workflow_dsl import DslConnection, DslNode, WorkflowDsl


def _linear_contract_graph(*, interface_key: str) -> WorkflowDsl:
    return WorkflowDsl(
        identifier="contract-test",
        title="Contract test",
        nodes=[
            DslNode(identifier="start", title="Start", config={"type": "SELF_SERVE_TRIGGER"}),
            DslNode(
                identifier="slot",
                title="Skill slot",
                config={"type": "AI_AGENT", "interface_key": interface_key, "agentIdentifier": interface_key},
            ),
            DslNode(
                identifier="publish",
                title="Publish",
                config={"type": "WEBHOOK", "url": "https://example.invalid", "method": "POST"},
            ),
        ],
        connections=[
            DslConnection(sourceIdentifier="start", targetIdentifier="slot"),
            DslConnection(sourceIdentifier="slot", targetIdentifier="publish"),
        ],
    )


def test_contract_flow_mismatch_entry_contract():
    graph = _linear_contract_graph(interface_key="analysis.system_requirements.generate@1")
    report = validate_graph_contracts(
        graph,
        entry_contract_key="WorkItem@1",
        exit_contract_key="SystemRequirementsArtifact@2",
    )
    assert any(e.get("code") == "CONTRACT_FLOW_MISMATCH" for e in report.get("errors", []))


def test_contract_flow_match_entry_and_exit_contract():
    graph = _linear_contract_graph(interface_key="analysis.system_requirements.generate@1")
    report = validate_graph_contracts(
        graph,
        entry_contract_key="ProblemUnderstandingArtifact@1",
        exit_contract_key="SystemRequirementsArtifact@2",
    )
    assert not report.get("errors")


def test_contract_flow_exit_mismatch():
    graph = _linear_contract_graph(interface_key="analysis.system_requirements.generate@1")
    report = validate_graph_contracts(
        graph,
        entry_contract_key="ProblemUnderstandingArtifact@1",
        exit_contract_key="BusinessRequirementsArtifact@1",
    )
    assert any(
        e.get("code") == "GRAPH_EXIT_CONTRACT_MISMATCH"
        for e in report.get("errors", [])
    )
