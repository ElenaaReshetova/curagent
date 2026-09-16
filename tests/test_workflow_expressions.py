"""Template / Slack input helpers used by workflow runtime."""

from __future__ import annotations

from src.platform.graphs.expressions import (
    enrich_run_input,
    parse_structured_json,
    render_templates,
)


def test_enrich_run_input_parses_slack_source_id():
    inp = enrich_run_input(
        {
            "source": "slack",
            "source_id": "slack:C0AKKCGEKL1:1710000000.123456",
            "description": "Нужен BRD",
        }
    )
    assert inp["channel"] == "C0AKKCGEKL1"
    assert inp["thread_ts"] == "1710000000.123456"
    assert inp["text"] == "Нужен BRD"


def test_parse_structured_json_from_fenced_response():
    raw = '```json\n{"scheme": "SRD", "rationale": "API change"}\n```'
    assert parse_structured_json(raw)["scheme"] == "SRD"


def test_render_keeps_unresolved_secrets():
    out = render_templates(
        {"Authorization": 'Bearer {{ .secrets["slack-bot-token"] }}'},
        {"outputs": {}, "secrets": {}},
    )
    assert "{{ .secrets" in out["Authorization"]
    filled = render_templates(out, {"outputs": {}, "secrets": {"slack-bot-token": "xoxb-test"}})
    assert filled["Authorization"] == "Bearer xoxb-test"


def test_rework_prompt_keeps_previous_draft():
    prompt = (
        "Previous BRD:\n{{ .outputs.brd_agent.text }}\n\n"
        "Feedback:\n{{ .outputs.review.comment }}"
    )
    first = render_templates(prompt, {"outputs": {"trigger": {"text": "need BRD"}}})
    assert "Previous BRD:\n\n" in first
    rework = render_templates(
        prompt,
        {
            "outputs": {
                "brd_agent": {"text": "# BRD v1\nGreen button"},
                "review": {"comment": "Add SLA"},
            }
        },
    )
    assert "# BRD v1" in rework
    assert "Add SLA" in rework


def test_render_outputs_trigger_alias():
    ctx = {
        "outputs": {"trigger": {"channel": "C1", "text": "hello"}},
        "secrets": {},
    }
    url = render_templates(
        "https://slack.com/api/conversations.replies?channel={{ .outputs.trigger.channel }}",
        ctx,
    )
    assert url.endswith("channel=C1")


def test_skill_text_reads_playbook_artifact_content():
    from src.platform.graphs.expressions import skill_text

    raw = {"artifact": {"content": "# BRD\n\nЗелёная кнопка"}, "output": {"content": "# BRD\n\nЗелёная кнопка"}}
    assert skill_text(raw).startswith("# BRD")
    assert skill_text({"response": None, "message": ""}) == ""


def test_request_changes_maps_to_decline_outlet():
    from src.platform.graphs.expressions import normalize_hitl_decision

    assert normalize_hitl_decision("REQUEST_CHANGES") == "decline"
    assert normalize_hitl_decision("APPROVE") == "approve"
    assert normalize_hitl_decision("REJECT") == "reject"
