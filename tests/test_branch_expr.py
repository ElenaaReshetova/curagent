"""Unit tests for deterministic branch expressions."""

from __future__ import annotations

from src.orchestrator.workflows.branch_expr import (
    eval_expression,
    pick_branch_target,
    pick_condition_outlet,
    resolve_path,
)


def test_eval_simple_comparisons():
    ctx = {"input": {"score": 10, "flag": True}, "outputs": {}, "approvals": {}}
    assert eval_expression("input.score == 10", ctx) is True
    assert eval_expression("input.score > 5", ctx) is True
    assert eval_expression("input.score < 5", ctx) is False
    assert eval_expression("input.flag == true", ctx) is True
    assert eval_expression("not input.flag", ctx) is False
    assert eval_expression("input.score > 5 and input.flag", ctx) is True
    assert eval_expression("input.missing == null", ctx) is True


def test_eval_outputs_path():
    ctx = {
        "input": {},
        "outputs": {"agent1": {"ok": True, "decision": "approve"}},
        "approvals": {},
    }
    assert eval_expression('outputs.agent1.decision == "approve"', ctx) is True
    assert resolve_path("outputs.agent1.ok", {
        "input": {}, "outputs": ctx["outputs"], "approvals": {}, "vars": {},
    }) is True


def test_pick_branch_with_node_expression():
    ctx = {"input": {"n": 2}, "outputs": {}, "approvals": {}}
    edges = [
        {"target": "yes_path", "sourceHandle": "yes"},
        {"target": "no_path", "sourceHandle": "no"},
    ]
    assert pick_branch_target(edges, ctx, node_expression="input.n > 1") == "yes_path"
    assert pick_branch_target(edges, ctx, node_expression="input.n > 5") == "no_path"


def test_pick_condition_outlet():
    outlets = [
        {"identifier": "prod", "expression": 'input.env == "prod"'},
        {"identifier": "dev", "expression": 'input.env == "dev"'},
    ]
    edges = [
        {"target": "t-prod", "sourceHandle": "prod"},
        {"target": "t-dev", "sourceHandle": "dev"},
    ]
    assert pick_condition_outlet(outlets, edges, {"input": {"env": "dev"}, "outputs": {}}) == "t-dev"


def test_pick_condition_outlet_routing_scheme():
    outlets = [
        {"identifier": "brd", "expression": '.outputs.routing.scheme == "BRD"'},
        {"identifier": "srd", "expression": '.outputs.routing.scheme == "SRD"'},
    ]
    edges = [
        {"target": "brd_agent", "sourceHandle": "brd"},
        {"target": "srd_agent", "sourceHandle": "srd"},
        {"target": "brd_agent", "sourceHandle": "fallback", "fallback": True},
    ]
    ctx = {"input": {}, "outputs": {"routing": {"scheme": "SRD", "response": "{}"}}}
    assert pick_condition_outlet(outlets, edges, ctx) == "srd_agent"


def test_empty_condition_expression_uses_fallback_not_first_option():
    outlets = [
        {"identifier": "yes", "expression": ""},
        {"identifier": "no", "expression": ""},
    ]
    edges = [
        {"target": "yes-path", "sourceHandle": "yes"},
        {"target": "fallback-path", "sourceHandle": "fallback", "fallback": True},
    ]
    assert pick_condition_outlet(outlets, edges, {"input": {}, "outputs": {}}) == "fallback-path"
