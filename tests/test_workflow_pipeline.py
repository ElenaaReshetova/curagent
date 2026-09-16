"""workflow DSL → normalize → Temporal plan pipeline tests."""

from __future__ import annotations

from src.platform.graphs.normalize import normalize_workflow_dsl
from src.platform.graphs.parse import parse_workflow_to_temporal
from src.platform.graphs.workflow_dsl import parse_workflow_dsl


# Matches AGSW-485 / reference workflow shape (no End node)
WORKFLOW_DSL = {
    "identifier": "brd-from-jira",
    "title": "BRD from Jira",
    "description": "demo",
    "nodes": [
        {
            "identifier": "trigger",
            "title": "Self-serve",
            "config": {
                "type": "SELF_SERVE_TRIGGER",
                "userInputs": {
                    "properties": {"issue_key": {"type": "string", "title": "Issue"}},
                    "required": ["issue_key"],
                },
                "published": True,
            },
        },
        {
            "identifier": "send-webhook",
            "title": "Get Jira",
            "config": {
                "type": "WEBHOOK",
                "url": "https://jira.example.com/issue/{{ .inputs.issue_key }}",
                "method": "GET",
                "testOutputs": {"should": "be stripped"},
            },
        },
        {
            "identifier": "ai-summary",
            "title": "Summarize",
            "config": {"type": "AI", "userPrompt": "Summarize {{ .outputs.send-webhook.body }}"},
        },
        {
            "identifier": "agent",
            "title": "BRD agent",
            "config": {
                "type": "AI_AGENT",
                "agentIdentifier": "business-analyst-agent",
                "userPrompt": "Write BRD",
                "skill_keys": ["should-strip"],
            },
        },
        {
            "identifier": "review",
            "title": "Approve",
            "config": {
                "type": "INPUT",
                "outlets": [
                    {"identifier": "approve", "title": "Approve"},
                    {"identifier": "decline", "title": "Decline"},
                ],
            },
        },
        {
            "identifier": "check",
            "title": "Route",
            "config": {
                "type": "CONDITION",
                "options": [
                    {"identifier": "approve", "title": "Approved", "expression": '.outputs.review.decision == "approve"'},
                    {"identifier": "decline", "title": "Declined", "expression": '.outputs.review.decision == "decline"'},
                ],
            },
        },
        {
            "identifier": "publish",
            "title": "Publish",
            "config": {
                "type": "WEBHOOK",
                "url": "https://confluence.example.com/",
                "method": "POST",
                "body": {"ok": True},
            },
        },
    ],
    "connections": [
        {"sourceIdentifier": "trigger", "targetIdentifier": "send-webhook"},
        {"sourceIdentifier": "send-webhook", "targetIdentifier": "ai-summary"},
        {"sourceIdentifier": "ai-summary", "targetIdentifier": "agent"},
        {"sourceIdentifier": "agent", "targetIdentifier": "review"},
        {
            "sourceIdentifier": "review",
            "targetIdentifier": "check",
            "sourceOutletIdentifier": "approve",
        },
        {
            "sourceIdentifier": "check",
            "targetIdentifier": "publish",
            "sourceOptionIdentifier": "approve",
        },
    ],
    "ui": {"positions": {"trigger": {"x": 0, "y": 0}}, "kind": "e2e"},
}


def test_normalize_strips_ui_and_service_params():
    doc = normalize_workflow_dsl(WORKFLOW_DSL)
    assert doc.ui is None
    hook = next(n for n in doc.nodes if n.identifier == "send-webhook")
    assert "testOutputs" not in hook.config
    agent = next(n for n in doc.nodes if n.identifier == "agent")
    assert "skill_keys" not in agent.config
    assert agent.config["agentIdentifier"] == "business-analyst-agent"


def test_normalize_drops_end_and_uses_condition_options():
    dirty = {
        **WORKFLOW_DSL,
        "nodes": [
            *WORKFLOW_DSL["nodes"],
            {"identifier": "end", "title": "End", "config": {"type": "END"}},
        ],
        "connections": [
            *WORKFLOW_DSL["connections"],
            {"sourceIdentifier": "publish", "targetIdentifier": "end"},
        ],
    }
    doc = normalize_workflow_dsl(dirty)
    assert "end" not in {n.identifier for n in doc.nodes}
    assert all(c.targetIdentifier != "end" for c in doc.connections)
    check = next(n for n in doc.nodes if n.identifier == "check")
    assert "options" in check.config
    assert "outlets" not in check.config
    assert check.config["options"][0]["identifier"] == "approve"


def test_parse_workflow_to_temporal_activities():
    doc = normalize_workflow_dsl(WORKFLOW_DSL)
    plan = parse_workflow_to_temporal(doc)
    assert plan.steps["send-webhook"].activity_name == "http_webhook"
    assert plan.steps["ai-summary"].activity_name == "ai_generate_summary"
    assert plan.steps["agent"].activity_name == "ai_agent_execute"
    assert plan.steps["review"].activity_name == "human_review"
    assert plan.steps["review"].wait_for_signal is True
    assert plan.steps["check"].branches
    assert plan.steps["check"].branches[0].next_step == "publish"
    assert "end" not in plan.steps
    assert "trigger" not in plan.steps


def test_validate_workflow_allows_leaf_without_end():
    from src.platform.graphs.service import validate_workflow

    doc = normalize_workflow_dsl(WORKFLOW_DSL)
    report = validate_workflow(doc)
    assert report.ok is True
    assert not any(i.code == "MISSING_END" for i in report.issues)
    assert "end" not in {n.identifier for n in doc.nodes}


def test_registry_has_no_end_aliases():
    from src.platform.graphs.registry import NODE_REGISTRY

    assert "end" not in NODE_REGISTRY
    for bad in ("agent", "tool", "branch", "approval", "parallel", "delay"):
        assert bad not in NODE_REGISTRY
    assert "subflow" in NODE_REGISTRY


def test_subflow_is_kept_and_parsed():
    raw = {
        "identifier": "parent",
        "title": "Parent",
        "nodes": [
            {"identifier": "t", "title": "T", "config": {"type": "SELF_SERVE_TRIGGER"}},
            {
                "identifier": "child",
                "title": "Run BRD",
                "config": {
                    "type": "SUBFLOW",
                    "graph_kind": "e2e",
                    "graph_key": "brd-from-jira",
                    "flow_key": "brd-from-jira",
                    "input": {"issue": "X-1"},
                },
            },
        ],
        "connections": [{"sourceIdentifier": "t", "targetIdentifier": "child"}],
    }
    doc = normalize_workflow_dsl(raw)
    child = next(n for n in doc.nodes if n.identifier == "child")
    assert child.config["type"] == "SUBFLOW"
    assert child.config["graph_key"] == "brd-from-jira"
    plan = parse_workflow_to_temporal(doc)
    assert plan.steps["child"].activity_name == "execute_subflow"
    assert plan.steps["child"].input["graph_key"] == "brd-from-jira"


def test_ai_pdlc_graph_is_slack_ready():
    from src.platform.graphs.service import get_graph_by_key, get_version, prepare_workflow_doc, validate_workflow

    rec = get_graph_by_key("e2e:ai-pdlc-flow")
    ver = get_version(rec.current_published_version_id or rec.current_draft_version_id)
    ids = [n["identifier"] for n in ver.dsl["nodes"]]
    assert ids[:8] == [
        "trigger",
        "context_collection",
        "routing",
        "route",
        "brd_agent",
        "srd_agent",
        "review",
        "publish",
    ]
    by_id = {n["identifier"]: n for n in ver.dsl["nodes"]}
    assert by_id["trigger"]["config"]["type"] == "SELF_SERVE_TRIGGER"
    assert "channel" in by_id["trigger"]["config"]["userInputs"]["properties"]
    collect = by_id["context_collection"]["config"]
    assert collect["url"].startswith("https://slack.com/api/conversations.replies")
    assert "{{ .outputs.trigger.channel }}" in collect["url"]
    assert "{{ .secrets" in collect["headers"]["Authorization"]
    prompt = by_id["routing"]["config"]["userPrompt"]
    assert "{{ .outputs.context_collection.body }}" in prompt
    assert by_id["routing"]["config"]["outputSchema"]["properties"]["scheme"]
    expr = by_id["route"]["config"]["options"][0]["expression"]
    assert "outputs.routing.scheme" in expr
    assert by_id["brd_agent"]["config"]["agentIdentifier"] == "business-requirements"
    brd_prompt = by_id["brd_agent"]["config"]["userPrompt"]
    srd_prompt = by_id["srd_agent"]["config"]["userPrompt"]
    assert "{{ .outputs.trigger.text }}" in brd_prompt
    assert "{{ .outputs.brd_agent.text }}" in brd_prompt
    assert "{{ .outputs.review.comment }}" in brd_prompt
    assert "revise it" in brd_prompt
    assert "{{ .outputs.srd_agent.text }}" in srd_prompt
    assert "{{ .outputs.brd_agent.text }}" in srd_prompt
    publish = by_id["publish"]["config"]
    assert publish["url"] == "https://slack.com/api/chat.postMessage"
    assert publish["method"] == "POST"
    assert "{{ .outputs.brd_agent.text }}" in publish["body"]["text"]
    doc = prepare_workflow_doc(ver.dsl)
    report = validate_workflow(doc)
    assert report.ok, [i.message for i in report.issues]
    assert "BUSINESS_REQUIREMENTS" in doc.produces
    assert "SYSTEM_REQUIREMENTS" in doc.produces
    assert any(n.identifier == "governance-brd_agent" for n in doc.nodes)
    assert any(n.identifier == "governance-srd_agent" for n in doc.nodes)
    plan = parse_workflow_to_temporal(doc)
    assert "{{ .outputs.brd_agent.text }}" in plan.steps["brd_agent"].input["userPrompt"]
    assert plan.steps["review"].wait_for_signal is True
    assert plan.steps["route"].fallback == "brd_agent"
    assert plan.steps["governance-brd_agent"].input["service"] == "policy.evaluate"
    assert plan.steps["governance-srd_agent"].input["producer"] == "srd_agent"


def test_launched_ai_pdlc_beats_classify_for_slack():
    from src.orchestrator.flow_template_resolver import resolve_execution_template

    template_id, reason, meta = resolve_execution_template(
        primary_skill="business-requirements",
        source="slack",
    )
    assert meta.get("use_graph_interpreter") is True
    assert meta.get("plan")
    assert (meta.get("flow_key") or "").endswith("ai-pdlc-flow") or "ai-pdlc" in str(meta.get("flow_key"))
    assert template_id == "__graph_workflow__"
    assert reason == "scenario_temporal_plan"


def test_ingress_has_explicit_no_launched_error(monkeypatch):
    from src.orchestrator import flow_template_resolver as resolver
    from src.platform.scenarios.errors import ScenarioError

    monkeypatch.setattr(resolver, "_ingress_candidates", lambda: [])
    try:
        resolver.resolve_execution_template(
            primary_skill="business-requirements",
            source="slack",
            graph_only=True,
        )
    except ScenarioError as exc:
        assert exc.code == "NO_LAUNCHED_SCENARIO"
    else:
        raise AssertionError("expected NO_LAUNCHED_SCENARIO")
