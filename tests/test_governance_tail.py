"""Governance compiler: one locked policy gate per parallel branch."""

from __future__ import annotations

from src.platform.graphs.governance import (
    compile_governance,
    evaluate_policy,
    gate_id_for,
)
from src.platform.graphs.normalize import normalize_workflow_dsl
from src.platform.graphs.parse import parse_workflow_to_temporal
from src.platform.graphs.workflow_dsl import DslConnection
from src.platform.graphs.service import prepare_workflow_doc, validate_workflow


def _brd_graph(*, include_gate: bool = False) -> dict:
    nodes = [
        {"identifier": "trigger", "title": "T", "config": {"type": "SELF_SERVE_TRIGGER"}},
        {
            "identifier": "brd_agent",
            "title": "BRD",
            "config": {
                "type": "AI_AGENT",
                "agentIdentifier": "business-requirements",
                "userPrompt": "write",
            },
        },
        {
            "identifier": "publish",
            "title": "Publish",
            "config": {
                "type": "WEBHOOK",
                "url": "https://slack.com/api/chat.postMessage",
                "method": "POST",
            },
        },
    ]
    connections = [
        {"sourceIdentifier": "trigger", "targetIdentifier": "brd_agent"},
        {"sourceIdentifier": "brd_agent", "targetIdentifier": "publish"},
    ]
    if include_gate:
        nodes.append({
            "identifier": "governance-tail",
            "title": "old",
            "config": {"type": "INTERNAL_SERVICE", "service": "policy.evaluate", "governance": True},
        })
    return {"identifier": "brd", "title": "BRD", "nodes": nodes, "connections": connections}


def _branched_graph() -> dict:
    return {
        "identifier": "branched",
        "title": "BRD or SRD",
        "nodes": [
            {"identifier": "trigger", "title": "T", "config": {"type": "SELF_SERVE_TRIGGER"}},
            {
                "identifier": "route",
                "title": "Route",
                "config": {
                    "type": "CONDITION",
                    "options": [
                        {"identifier": "brd", "title": "BRD", "expression": 'input.kind == "brd"'},
                        {"identifier": "srd", "title": "SRD", "expression": 'input.kind == "srd"'},
                    ],
                },
            },
            {
                "identifier": "brd_agent",
                "title": "BRD",
                "config": {"type": "AI_AGENT", "agentIdentifier": "business-requirements"},
            },
            {
                "identifier": "srd_agent",
                "title": "SRD",
                "config": {"type": "AI_AGENT", "agentIdentifier": "system-requirements"},
            },
            {
                "identifier": "publish",
                "title": "Publish",
                "config": {"type": "WEBHOOK", "url": "https://example.com", "method": "POST"},
            },
        ],
        "connections": [
            {"sourceIdentifier": "trigger", "targetIdentifier": "route"},
            {
                "sourceIdentifier": "route",
                "targetIdentifier": "brd_agent",
                "sourceOptionIdentifier": "brd",
            },
            {
                "sourceIdentifier": "route",
                "targetIdentifier": "srd_agent",
                "sourceOptionIdentifier": "srd",
            },
            {"sourceIdentifier": "brd_agent", "targetIdentifier": "publish"},
            {"sourceIdentifier": "srd_agent", "targetIdentifier": "publish"},
        ],
    }


def test_compiler_injects_locked_gate_after_producer():
    doc = compile_governance(normalize_workflow_dsl(_brd_graph()))
    gid = gate_id_for("brd_agent")
    assert "BUSINESS_REQUIREMENTS" in doc.produces
    gate = next(n for n in doc.nodes if n.identifier == gid)
    assert gate.config["immutable"] is True
    assert gate.config["service"] == "policy.evaluate"
    assert gate.config["producer"] == "brd_agent"
    assert gate.config["produces"] == ["BUSINESS_REQUIREMENTS"]
    brd = next(n for n in doc.nodes if n.identifier == "brd_agent")
    assert brd.config["produces"] == "BUSINESS_REQUIREMENTS"
    from_agent = [c.targetIdentifier for c in doc.connections if c.sourceIdentifier == "brd_agent"]
    assert from_agent == [gid]
    incoming = [
        (c.sourceIdentifier, c.sourceOutletIdentifier)
        for c in doc.connections
        if c.targetIdentifier == "publish"
    ]
    assert incoming == [(gid, "pass")]


def test_compiler_replaces_legacy_publication_tail():
    raw = _brd_graph(include_gate=True)
    raw["connections"] = [
        {"sourceIdentifier": "trigger", "targetIdentifier": "brd_agent"},
        {"sourceIdentifier": "brd_agent", "targetIdentifier": "publish"},
    ]
    doc = compile_governance(normalize_workflow_dsl(raw))
    assert any(n.identifier == gate_id_for("brd_agent") for n in doc.nodes)
    assert not any(n.identifier == "governance-tail" for n in doc.nodes)
    assert not any(
        c.sourceIdentifier == "brd_agent" and c.targetIdentifier == "publish"
        for c in doc.connections
    )


def test_branched_paths_get_separate_gates_and_keep_merge():
    doc = compile_governance(normalize_workflow_dsl(_branched_graph()))
    brd_g = gate_id_for("brd_agent")
    srd_g = gate_id_for("srd_agent")
    assert {n.identifier for n in doc.nodes} >= {"brd_agent", "srd_agent", brd_g, srd_g, "publish", "route"}
    brd_gate = next(n for n in doc.nodes if n.identifier == brd_g)
    srd_gate = next(n for n in doc.nodes if n.identifier == srd_g)
    assert brd_gate.config["produces"] == ["BUSINESS_REQUIREMENTS"]
    assert srd_gate.config["produces"] == ["SYSTEM_REQUIREMENTS"]
    pub_src = {c.sourceIdentifier for c in doc.connections if c.targetIdentifier == "publish"}
    assert pub_src == {brd_g, srd_g}
    route_brd = [
        c for c in doc.connections
        if c.sourceIdentifier == "route" and c.targetIdentifier == "brd_agent"
    ]
    assert route_brd and route_brd[0].sourceOptionIdentifier == "brd"
    fail_brd = [
        c for c in doc.connections
        if c.sourceIdentifier == brd_g and c.sourceOutletIdentifier == "fail"
    ]
    assert fail_brd[0].targetIdentifier == "brd_agent"
    fail_srd = [
        c for c in doc.connections
        if c.sourceIdentifier == srd_g and c.sourceOutletIdentifier == "fail"
    ]
    assert fail_srd[0].targetIdentifier == "srd_agent"
    report = validate_workflow(doc)
    assert report.ok, [i.message for i in report.issues]


def test_validate_rejects_producer_bypass():
    doc = compile_governance(normalize_workflow_dsl(_brd_graph()))
    doc.connections.append(
        DslConnection(sourceIdentifier="brd_agent", targetIdentifier="publish")
    )
    report = validate_workflow(doc)
    assert not report.ok
    assert any(i.code == "GOVERNANCE_GATE_BYPASS" for i in report.issues)


def test_prepare_then_parse_has_policy_step():
    doc = prepare_workflow_doc(_brd_graph())
    report = validate_workflow(doc)
    assert report.ok, [i.message for i in report.issues]
    plan = parse_workflow_to_temporal(doc)
    gid = gate_id_for("brd_agent")
    step = plan.steps[gid]
    assert step.activity_name == "internal_service"
    assert step.input["service"] == "policy.evaluate"
    assert step.input["producer"] == "brd_agent"
    handles = {str(e.get("sourceHandle")) for e in step.outlets}
    assert "pass" in handles
    assert "fail" in handles


def test_prepare_keeps_saved_governance_positions():
    gid = gate_id_for("brd_agent")
    raw = {
        **_brd_graph(),
        "ui": {
            "kind": "e2e",
            "positions": {
                "trigger": {"x": 40, "y": 80},
                "brd_agent": {"x": 280, "y": 80},
                "publish": {"x": 760, "y": 80},
                gid: {"x": 520, "y": 220},
            },
        },
    }
    doc = prepare_workflow_doc(raw)
    assert (doc.ui or {}).get("positions", {}).get(gid) == {"x": 520, "y": 220}
    again = prepare_workflow_doc(doc.model_dump(mode="json"))
    assert (again.ui or {}).get("positions", {}).get(gid) == {"x": 520, "y": 220}


def test_evaluate_policy_uses_producer_output_not_other_branch():
    packs = [{
        "key": "stage-artifact-completeness",
        "name": "completeness",
        "enforcement": "BLOCK",
        "expression": "context.stage_exit_contract_satisfied == true",
    }]
    srd_only = evaluate_policy({
        "produces": ["SYSTEM_REQUIREMENTS"],
        "producer": "srd_agent",
        "packs": packs,
        "outputs": {
            "brd_agent": {"text": ""},
            "srd_agent": {"text": "# SRD\nService API"},
        },
    })
    assert srd_only["passed"] is True
    empty_srd = evaluate_policy({
        "produces": ["SYSTEM_REQUIREMENTS"],
        "producer": "srd_agent",
        "packs": packs,
        "outputs": {
            "brd_agent": {"text": "# BRD\nfilled"},
            "srd_agent": {"text": ""},
        },
    })
    assert empty_srd["passed"] is False


def test_evaluate_policy_blocks_empty_artifact():
    result = evaluate_policy({
        "produces": ["BUSINESS_REQUIREMENTS"],
        "producer": "brd_agent",
        "packs": [{
            "key": "stage-artifact-completeness",
            "name": "completeness",
            "enforcement": "BLOCK",
            "expression": "context.stage_exit_contract_satisfied == true",
        }],
        "outputs": {"brd_agent": {"text": ""}},
    })
    assert result["passed"] is False
    filled = evaluate_policy({
        "produces": ["BUSINESS_REQUIREMENTS"],
        "producer": "brd_agent",
        "packs": [{
            "key": "stage-artifact-completeness",
            "name": "completeness",
            "enforcement": "BLOCK",
            "expression": "context.stage_exit_contract_satisfied == true",
        }],
        "outputs": {"brd_agent": {"text": "# BRD\nNeed a green button"}},
    })
    assert filled["passed"] is True


def test_evaluate_policy_blocks_secrets_in_brd():
    result = evaluate_policy({
        "produces": ["BUSINESS_REQUIREMENTS"],
        "producer": "brd_agent",
        "packs": [{
            "key": "user-data-protection",
            "enforcement": "BLOCK",
            "expression": "context.artifact.pii_clean == true AND context.artifact.secrets_clean == true",
        }],
        "outputs": {"brd_agent": {"text": "token xoxb-1234567890abcdef"}},
    })
    assert result["passed"] is False


def test_intermediate_agent_does_not_get_a_gate():
    raw = {
        "identifier": "prep-then-brd",
        "title": "prep",
        "nodes": [
            {"identifier": "trigger", "title": "T", "config": {"type": "SELF_SERVE_TRIGGER"}},
            {
                "identifier": "extract",
                "title": "Extract facts",
                "config": {
                    "type": "AI_AGENT",
                    "agentIdentifier": "business-requirements",
                    "produces": "NONE",
                    "userPrompt": "extract",
                },
            },
            {
                "identifier": "brd_agent",
                "title": "BRD",
                "config": {
                    "type": "AI_AGENT",
                    "agentIdentifier": "business-requirements",
                    "userPrompt": "write",
                },
            },
            {
                "identifier": "publish",
                "title": "Publish",
                "config": {"type": "WEBHOOK", "url": "https://example.com", "method": "POST"},
            },
        ],
        "connections": [
            {"sourceIdentifier": "trigger", "targetIdentifier": "extract"},
            {"sourceIdentifier": "extract", "targetIdentifier": "brd_agent"},
            {"sourceIdentifier": "brd_agent", "targetIdentifier": "publish"},
        ],
    }
    doc = compile_governance(normalize_workflow_dsl(raw))
    ids = {n.identifier for n in doc.nodes}
    assert "governance-extract" not in ids
    assert gate_id_for("brd_agent") in ids
    extract_out = [c.targetIdentifier for c in doc.connections if c.sourceIdentifier == "extract"]
    assert extract_out == ["brd_agent"]
    report = validate_workflow(doc)
    assert report.ok, [i.message for i in report.issues]


def test_untyped_parallel_branch_gets_general_on_any_step():
    raw = {
        "identifier": "mixed-branches",
        "title": "typed vs untyped",
        "nodes": [
            {"identifier": "trigger", "title": "T", "config": {"type": "SELF_SERVE_TRIGGER"}},
            {
                "identifier": "route",
                "title": "Route",
                "config": {
                    "type": "CONDITION",
                    "options": [
                        {"identifier": "brd", "title": "BRD", "expression": 'input.kind == "brd"'},
                        {"identifier": "other", "title": "Other", "expression": 'input.kind == "other"'},
                    ],
                },
            },
            {
                "identifier": "brd_agent",
                "title": "BRD",
                "config": {"type": "AI_AGENT", "agentIdentifier": "business-requirements"},
            },
            {
                "identifier": "rewrite",
                "title": "Rewrite",
                "config": {"type": "AI_AGENT", "agentIdentifier": "generic-rewrite"},
            },
            {
                "identifier": "publish",
                "title": "Publish",
                "config": {"type": "WEBHOOK", "url": "https://example.com", "method": "POST"},
            },
        ],
        "connections": [
            {"sourceIdentifier": "trigger", "targetIdentifier": "route"},
            {
                "sourceIdentifier": "route",
                "targetIdentifier": "brd_agent",
                "sourceOptionIdentifier": "brd",
            },
            {
                "sourceIdentifier": "route",
                "targetIdentifier": "rewrite",
                "sourceOptionIdentifier": "other",
            },
            {"sourceIdentifier": "brd_agent", "targetIdentifier": "publish"},
            {"sourceIdentifier": "rewrite", "targetIdentifier": "publish"},
        ],
    }
    doc = compile_governance(normalize_workflow_dsl(raw))
    rewrite = next(n for n in doc.nodes if n.identifier == "rewrite")
    assert rewrite.config["produces"] == "GENERAL"
    brd_g = gate_id_for("brd_agent")
    other_g = gate_id_for("rewrite")
    assert {n.identifier for n in doc.nodes} >= {brd_g, other_g}
    other_gate = next(n for n in doc.nodes if n.identifier == other_g)
    assert other_gate.config["produces"] == ["GENERAL"]
    assert other_gate.config["producer"] == "rewrite"
    pub_src = {c.sourceIdentifier for c in doc.connections if c.targetIdentifier == "publish"}
    assert pub_src == {brd_g, other_g}
    report = validate_workflow(doc)
    assert report.ok, [i.message for i in report.issues]


def test_one_gate_per_branch_even_with_two_producers():
    raw = {
        "identifier": "extract-then-brd",
        "title": "two producers one path",
        "nodes": [
            {"identifier": "trigger", "title": "T", "config": {"type": "SELF_SERVE_TRIGGER"}},
            {
                "identifier": "extract",
                "title": "Extract",
                "config": {
                    "type": "AI_AGENT",
                    "agentIdentifier": "business-requirements",
                    "produces": "BUSINESS_REQUIREMENTS",
                },
            },
            {
                "identifier": "brd_agent",
                "title": "BRD",
                "config": {
                    "type": "AI_AGENT",
                    "agentIdentifier": "business-requirements",
                    "produces": "BUSINESS_REQUIREMENTS",
                },
            },
            {
                "identifier": "publish",
                "title": "Publish",
                "config": {"type": "WEBHOOK", "url": "https://example.com", "method": "POST"},
            },
        ],
        "connections": [
            {"sourceIdentifier": "trigger", "targetIdentifier": "extract"},
            {"sourceIdentifier": "extract", "targetIdentifier": "brd_agent"},
            {"sourceIdentifier": "brd_agent", "targetIdentifier": "publish"},
        ],
    }
    doc = compile_governance(normalize_workflow_dsl(raw))
    ids = {n.identifier for n in doc.nodes}
    assert "governance-extract" not in ids
    assert gate_id_for("brd_agent") in ids
    extract_out = [c.targetIdentifier for c in doc.connections if c.sourceIdentifier == "extract"]
    assert extract_out == ["brd_agent"]
    gate = next(n for n in doc.nodes if n.identifier == gate_id_for("brd_agent"))
    assert gate.config["producer"] == "brd_agent"
    assert gate.config["producer_ids"] == ["extract", "brd_agent"]
    report = validate_workflow(doc)
    assert report.ok, [i.message for i in report.issues]
