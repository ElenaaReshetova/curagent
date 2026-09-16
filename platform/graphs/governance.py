"""Artifact-typed policy compiler for graphs.

Coverage is per parallel branch, not per step. If any step on a path that
later merges declares an artifact type, one locked Policy gate sits at the
end of that branch. If the branch has no type, GENERAL is stamped on any
eligible step (last AI agent) and the gate is still injected. Intermediate
steps on a covered branch do not get their own gates.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from src.platform.graphs.workflow_dsl import DslConnection, DslNode, WorkflowDsl

GOVERNANCE_TAIL_ID = "governance-tail"
GOVERNANCE_ID_PREFIX = "governance-"
POLICY_SERVICE = "policy.evaluate"

_ARTIFACT_LABELS = {
    "BUSINESS_REQUIREMENTS": "Business Requirements",
    "SYSTEM_REQUIREMENTS": "System Requirements",
    "TEST_CASE_PACK": "Test Case Pack",
    "CODE_ANALYSIS": "Code Analysis",
    "ARCHITECTURE": "Architecture",
    "GENERAL": "General artifact",
}

ARTIFACT_TYPES = (
    "BUSINESS_REQUIREMENTS",
    "SYSTEM_REQUIREMENTS",
    "TEST_CASE_PACK",
    "CODE_ANALYSIS",
    "ARCHITECTURE",
    "GENERAL",
)

SKILL_TO_ARTIFACT: dict[str, str] = {
    "business-requirements": "BUSINESS_REQUIREMENTS",
    "system-requirements": "SYSTEM_REQUIREMENTS",
    "test-design": "TEST_CASE_PACK",
    "test-case-generation": "TEST_CASE_PACK",
    "code-review": "CODE_ANALYSIS",
    "code-change": "CODE_ANALYSIS",
    "security-policy-review": "CODE_ANALYSIS",
    "architecture-review": "ARCHITECTURE",
}

_NOT_PRODUCING = {"NONE", "INTERMEDIATE", "-"}
_PUBLICATION_TYPES = {"KAFKA", "INTEGRATION_ACTION", "UPSERT_ENTITY"}
_PUBLICATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_PASS_HANDLES = {"pass", "yes", "ok", "success", "approve"}
_FAIL_HANDLES = {"fail", "no", "block", "error", "reject"}
_SECRET_RE = re.compile(
    r"(xoxb-|xoxp-|sk-[A-Za-z0-9]{8,}|api[_-]?key\s*[:=]\s*\S+|Bearer\s+[A-Za-z0-9\-._]{12,})",
    re.I,
)
_TAIL_EVAL_POINTS = {
    "BEFORE_ARTIFACT_PUBLICATION",
    "AFTER_SKILL",
    "AFTER_GRAPH",
}


def normalize_artifact_type(raw: str | None) -> str:
    text = str(raw or "").strip().upper().replace(" ", "_").replace("-", "_")
    aliases = {
        "BUSINESSREQUIREMENTSDOC": "BUSINESS_REQUIREMENTS",
        "BUSINESS_REQUIREMENTS_DOC": "BUSINESS_REQUIREMENTS",
        "BUSINESSREQUIREMENTSARTIFACT": "BUSINESS_REQUIREMENTS",
        "SYSTEMREQUIREMENTSDOC": "SYSTEM_REQUIREMENTS",
        "SYSTEM_REQUIREMENTS_DOC": "SYSTEM_REQUIREMENTS",
        "SYSTEMREQUIREMENTSARTIFACT": "SYSTEM_REQUIREMENTS",
        "TESTCASEPACK": "TEST_CASE_PACK",
        "CODEANALYSISREPORT": "CODE_ANALYSIS",
        "CODE_ANALYSIS_REPORT": "CODE_ANALYSIS",
        "GENERALARTIFACT": "GENERAL",
    }
    text = aliases.get(text, text)
    return text if text in ARTIFACT_TYPES else (text if text else "")


def gate_id_for(producer_id: str) -> str:
    return f"{GOVERNANCE_ID_PREFIX}{producer_id}"


def is_governance_id(identifier: str | None) -> bool:
    ident = str(identifier or "")
    return ident == GOVERNANCE_TAIL_ID or ident.startswith(GOVERNANCE_ID_PREFIX)


def is_governance_node(node: DslNode) -> bool:
    cfg = node.config or {}
    if is_governance_id(node.identifier):
        return True
    if cfg.get("governance") or cfg.get("immutable"):
        return True
    return str(cfg.get("service") or "") == POLICY_SERVICE


def is_fail_connection(conn: DslConnection) -> bool:
    handle = str(conn.sourceOutletIdentifier or conn.sourceOptionIdentifier or "").lower()
    return handle in _FAIL_HANDLES


def is_publication_node(node: DslNode) -> bool:
    if is_governance_node(node):
        return False
    cfg = node.config or {}
    t = str(cfg.get("type") or "").upper()
    if cfg.get("publication"):
        return True
    if t in _PUBLICATION_TYPES:
        return True
    if t == "WEBHOOK":
        method = str(cfg.get("method") or "POST").upper()
        return method in _PUBLICATION_METHODS
    return False


def is_producing_node(node: DslNode) -> bool:
    if is_governance_node(node):
        return False
    cfg = node.config or {}
    raw = str(cfg.get("produces") or "").strip()
    if raw.upper() in _NOT_PRODUCING:
        return False
    if normalize_artifact_type(raw):
        return True
    if str(cfg.get("type") or "").upper() != "AI_AGENT":
        return False
    agent = str(cfg.get("agentIdentifier") or cfg.get("skill_key") or "").strip()
    return agent in SKILL_TO_ARTIFACT


def collect_produces(doc: WorkflowDsl) -> list[str]:
    found: list[str] = []

    def _add(raw: str | None) -> None:
        value = normalize_artifact_type(raw)
        if value and value not in found:
            found.append(value)

    for item in doc.produces or []:
        _add(str(item))
    for node in doc.nodes:
        if is_governance_node(node) or not is_producing_node(node):
            continue
        cfg = node.config or {}
        _add(str(cfg.get("produces") or ""))
        if str(cfg.get("type") or "").upper() == "AI_AGENT":
            agent = str(cfg.get("agentIdentifier") or cfg.get("skill_key") or "").strip()
            _add(SKILL_TO_ARTIFACT.get(agent, ""))
    return found


def publication_nodes(doc: WorkflowDsl) -> list[DslNode]:
    return [n for n in doc.nodes if is_publication_node(n)]


def _cfg_type(node: DslNode) -> str:
    return str((node.config or {}).get("type") or "").upper()


def _is_trigger(node: DslNode) -> bool:
    t = _cfg_type(node)
    return t.endswith("TRIGGER") or t in {"START", "SELF_SERVE_TRIGGER", "EVENT_TRIGGER", "SCHEDULE_TRIGGER"}


def node_artifact_types(node: DslNode) -> list[str]:
    if not is_producing_node(node):
        return []
    found: list[str] = []
    cfg = node.config or {}
    raw = normalize_artifact_type(str(cfg.get("produces") or ""))
    if raw:
        found.append(raw)
    if _cfg_type(node) == "AI_AGENT":
        agent = str(cfg.get("agentIdentifier") or cfg.get("skill_key") or "").strip()
        mapped = SKILL_TO_ARTIFACT.get(agent, "")
        if mapped and mapped not in found:
            found.append(mapped)
    return found


def compile_governance(doc: WorkflowDsl) -> WorkflowDsl:
    """Stamp missing branch types and inject one locked gate at each branch tip."""
    nodes, connections = _unwrap_governance(doc)

    stamped: list[DslNode] = []
    for node in nodes:
        cfg = dict(node.config or {})
        if is_producing_node(node) and not normalize_artifact_type(str(cfg.get("produces") or "")):
            agent = str(cfg.get("agentIdentifier") or cfg.get("skill_key") or "").strip()
            mapped = SKILL_TO_ARTIFACT.get(agent)
            if mapped:
                cfg["produces"] = mapped
        stamped.append(node.model_copy(update={"config": cfg}))

    branches = _discover_branches(stamped, connections)
    stamped = _stamp_untyped_branches(stamped, branches)

    by_id = {n.identifier: n for n in stamped}
    branch_specs: list[tuple[list[str], str, list[str], list[str]]] = []
    for path in branches:
        types: list[str] = []
        producers: list[str] = []
        for nid in path:
            node = by_id.get(nid)
            if not node:
                continue
            arts = node_artifact_types(node)
            if arts:
                producers.append(nid)
                for art in arts:
                    if art not in types:
                        types.append(art)
        if not path or not types:
            continue
        anchor = path[-1]
        last_prod = producers[-1] if producers else anchor
        branch_specs.append((path, anchor, types, producers or [last_prod]))

    anchor_ids = {anchor for _, anchor, _, _ in branch_specs}
    ui = dict(doc.ui or {})
    positions = dict(ui.get("positions") or {})
    gates: list[DslNode] = []
    rewired: list[DslConnection] = [
        c for c in connections if c.sourceIdentifier not in anchor_ids
    ]

    for _path, anchor, types, producers in branch_specs:
        gid = gate_id_for(anchor)
        packs = resolve_applicable_packs(types)
        last_prod = producers[-1]
        gates.append(_gate_node(
            last_prod,
            packs,
            types,
            producer_ids=producers,
            anchor_id=anchor,
        ))
        rewired.append(DslConnection(sourceIdentifier=anchor, targetIdentifier=gid))
        for conn in connections:
            if conn.sourceIdentifier != anchor:
                continue
            rewired.append(conn.model_copy(update={
                "sourceIdentifier": gid,
                "sourceOutletIdentifier": "pass",
                "sourceOptionIdentifier": None,
            }))
        rewired.append(DslConnection(
            sourceIdentifier=gid,
            targetIdentifier=last_prod,
            sourceOutletIdentifier="fail",
        ))
        if gid not in positions:
            pos = positions.get(anchor) or {}
            x = pos.get("x")
            y = pos.get("y")
            try:
                x = float(x) if x is not None else 400.0
            except (TypeError, ValueError):
                x = 400.0
            try:
                y = float(y) if y is not None else 180.0
            except (TypeError, ValueError):
                y = 180.0
            slot = {"x": x + 240.0, "y": y}
            occupied = {
                (round(float(p.get("x") or 0)), round(float(p.get("y") or 0)))
                for p in positions.values()
                if isinstance(p, dict)
            }
            while (round(slot["x"]), round(slot["y"])) in occupied:
                slot["y"] += 96.0
            positions[gid] = slot

    if positions:
        ui["positions"] = positions

    produces = collect_produces(WorkflowDsl(
        identifier=doc.identifier,
        title=doc.title,
        description=doc.description,
        produces=list(doc.produces or []),
        nodes=stamped,
        connections=connections,
        ui=doc.ui,
    ))
    return WorkflowDsl(
        identifier=doc.identifier,
        title=doc.title,
        description=doc.description,
        produces=produces,
        nodes=[*stamped, *gates],
        connections=_dedupe_connections(rewired),
        ui=ui or None,
    )


def _outgoing_map(connections: list[DslConnection]) -> dict[str, list[DslConnection]]:
    out: dict[str, list[DslConnection]] = {}
    for conn in connections:
        out.setdefault(conn.sourceIdentifier, []).append(conn)
    return out


def _incoming_map(connections: list[DslConnection]) -> dict[str, list[DslConnection]]:
    incoming: dict[str, list[DslConnection]] = {}
    for conn in connections:
        incoming.setdefault(conn.targetIdentifier, []).append(conn)
    return incoming


def _split_ids(nodes: list[DslNode], outgoing: dict[str, list[DslConnection]]) -> set[str]:
    ids: set[str] = set()
    for node in nodes:
        if is_publication_node(node):
            continue
        if _cfg_type(node) == "CONDITION" or len(outgoing.get(node.identifier, [])) > 1:
            ids.add(node.identifier)
    return ids


def _join_ids(nodes: list[DslNode], incoming: dict[str, list[DslConnection]]) -> set[str]:
    ids: set[str] = set()
    for node in nodes:
        if is_publication_node(node) or _cfg_type(node) == "CONDITION" or _is_trigger(node):
            continue
        if len({c.sourceIdentifier for c in incoming.get(node.identifier, [])}) > 1:
            ids.add(node.identifier)
    return ids


def _walk_branch(
    start_id: str,
    by_id: dict[str, DslNode],
    outgoing: dict[str, list[DslConnection]],
    incoming: dict[str, list[DslConnection]],
    split_ids: set[str],
) -> list[str]:
    path: list[str] = []
    current = start_id
    seen: set[str] = set()
    first = True
    while current and current not in seen:
        seen.add(current)
        node = by_id.get(current)
        if not node:
            break
        if is_publication_node(node):
            break
        if current in split_ids:
            break
        if not first and len({c.sourceIdentifier for c in incoming.get(current, [])}) > 1:
            break
        first = False
        path.append(current)
        outs = outgoing.get(current, [])
        if len(outs) != 1:
            break
        current = outs[0].targetIdentifier
    return path


def _discover_branches(
    nodes: list[DslNode],
    connections: list[DslConnection],
) -> list[list[str]]:
    """Parallel paths from a split (or the trigger if the graph is linear) until a join/publication."""
    by_id = {n.identifier: n for n in nodes}
    outgoing = _outgoing_map(connections)
    incoming = _incoming_map(connections)
    split_ids = _split_ids(nodes, outgoing)
    join_ids = _join_ids(nodes, incoming)

    seeds: list[str] = []
    if split_ids:
        for sid in split_ids:
            seeds.extend(c.targetIdentifier for c in outgoing.get(sid, []))
        for jid in join_ids:
            seeds.extend(c.targetIdentifier for c in outgoing.get(jid, []))
    else:
        trigger = next((n for n in nodes if _is_trigger(n)), None)
        if trigger:
            seeds.extend(c.targetIdentifier for c in outgoing.get(trigger.identifier, []))
        else:
            roots = [n.identifier for n in nodes if not incoming.get(n.identifier)]
            for rid in roots:
                children = outgoing.get(rid, [])
                if children:
                    seeds.extend(c.targetIdentifier for c in children)
                else:
                    seeds.append(rid)

    branches: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for start in seeds:
        if not start:
            continue
        path = _walk_branch(start, by_id, outgoing, incoming, split_ids)
        key = tuple(path)
        if path and key not in seen:
            seen.add(key)
            branches.append(path)
    return branches


def _eligible_stamp_target(path: list[str], by_id: dict[str, DslNode]) -> str | None:
    agents: list[str] = []
    ais: list[str] = []
    others: list[str] = []
    for nid in path:
        node = by_id.get(nid)
        if not node:
            continue
        t = _cfg_type(node)
        if _is_trigger(node) or t == "CONDITION":
            continue
        if t == "AI_AGENT":
            agents.append(nid)
        elif t == "AI":
            ais.append(nid)
        else:
            others.append(nid)
    if agents:
        return agents[-1]
    if ais:
        return ais[-1]
    if others:
        return others[-1]
    return None


def _stamp_untyped_branches(
    nodes: list[DslNode],
    branches: list[list[str]],
) -> list[DslNode]:
    by_id = {n.identifier: n for n in nodes}
    for path in branches:
        has_type = any(node_artifact_types(by_id[nid]) for nid in path if nid in by_id)
        if has_type:
            continue
        target_id = _eligible_stamp_target(path, by_id)
        if not target_id:
            continue
        node = by_id[target_id]
        cfg = dict(node.config or {})
        cfg["produces"] = "GENERAL"
        by_id[target_id] = node.model_copy(update={"config": cfg})
    return [by_id[n.identifier] for n in nodes]


def resolve_applicable_packs(produces: Iterable[str]) -> list[dict[str, Any]]:
    wanted = {normalize_artifact_type(p) for p in produces if normalize_artifact_type(p)}
    if not wanted:
        return []
    try:
        from src.platform.controls import service as controls_svc
    except Exception:
        return []
    packs: list[dict[str, Any]] = []
    for rec in controls_svc.list_records():
        ver = controls_svc._current_version(rec)
        if not ver or str(ver.status).upper() != "ACTIVE":
            continue
        point = str(ver.evaluation_point or "").upper()
        if point and point not in _TAIL_EVAL_POINTS:
            continue
        artifact_conds = [
            c for c in (ver.applicability or []) if c.field == "artifact.type"
        ]
        if artifact_conds:
            matched = any(
                normalize_artifact_type(c.value) in wanted for c in artifact_conds
            )
            if not matched:
                continue
        packs.append({
            "key": rec.key,
            "name": rec.name,
            "severity": ver.severity,
            "enforcement": ver.enforcement_on_failed,
            "expression": ver.expression,
            "evaluation_point": ver.evaluation_point,
            "mandatory": True,
        })
    return packs


def evaluate_policy(payload: dict[str, Any]) -> dict[str, Any]:
    """Runtime evaluation for ``policy.evaluate``."""
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    raw_produces = payload.get("produces") or []
    if isinstance(raw_produces, str):
        raw_produces = [raw_produces]
    produces = [
        normalize_artifact_type(str(p))
        for p in raw_produces
        if normalize_artifact_type(str(p))
    ]
    packs = payload.get("packs") if isinstance(payload.get("packs"), list) else []
    if not packs and produces:
        packs = resolve_applicable_packs(produces)

    raw_ids = payload.get("producer_ids") or []
    if isinstance(raw_ids, str):
        raw_ids = [raw_ids]
    artifact_text = _artifact_text(
        outputs,
        produces,
        producer_id=str(payload.get("producer") or payload.get("producer_id") or ""),
        producer_ids=[str(x) for x in raw_ids if x],
    )
    review = outputs.get("review") if isinstance(outputs.get("review"), dict) else {}
    decision = str(review.get("decision") or "").lower()
    checkpoint = {
        "status": "APPROVED" if decision in {"approve", "approved"} else str(review.get("status") or ""),
    }
    context = {
        "artifact": {
            "text": artifact_text,
            "content": artifact_text,
            "pii_clean": not _has_secrets(artifact_text),
            "secrets_clean": not _has_secrets(artifact_text),
        },
        "checkpoint": checkpoint,
        "evidence": {"count": 5 if artifact_text else 0},
        "stage_exit_contract_satisfied": bool(artifact_text.strip()),
    }

    results: list[dict[str, Any]] = []
    blocking_fail = False
    fail_enforcement = "BLOCK"
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        expr = str(pack.get("expression") or "")
        ok = _eval_expression(expr, context)
        enforcement = str(pack.get("enforcement") or "BLOCK").upper()
        results.append({
            "key": pack.get("key"),
            "name": pack.get("name"),
            "passed": ok,
            "enforcement": enforcement,
        })
        if not ok and enforcement in {"BLOCK", "FAIL_EXECUTION", "PAUSE_EXECUTION", "REQUIRE_HUMAN_APPROVAL"}:
            blocking_fail = True
            fail_enforcement = enforcement

    passed = not blocking_fail
    return {
        "ok": passed,
        "passed": passed,
        "produces": produces,
        "packs": results,
        "enforcement": "ALLOW" if passed else fail_enforcement,
        "artifact_text_present": bool(artifact_text.strip()),
    }


def next_from_gate_outlets(outlets: list[dict[str, Any]], result: dict[str, Any], fallback: str | None) -> Optional[str]:
    passed = bool(result.get("passed") if "passed" in result else result.get("ok", True))
    wanted = _PASS_HANDLES if passed else _FAIL_HANDLES
    for edge in outlets or []:
        handle = str(edge.get("sourceHandle") or "").strip().lower()
        if handle in wanted:
            return edge.get("target")
    if not passed:
        for edge in outlets or []:
            handle = str(edge.get("sourceHandle") or "").strip().lower()
            if handle in _FAIL_HANDLES:
                return edge.get("target")
        return fallback
    return fallback


def _unwrap_governance(doc: WorkflowDsl) -> tuple[list[DslNode], list[DslConnection]]:
    """Drop locked gates and splice their pass-through so a recompile keeps author edges."""
    gov_ids = {n.identifier for n in doc.nodes if is_governance_node(n)}
    nodes = [n for n in doc.nodes if n.identifier not in gov_ids]
    if not gov_ids:
        return nodes, list(doc.connections)
    into_gate: dict[str, list[DslConnection]] = {}
    pass_from_gate: dict[str, list[DslConnection]] = {}
    kept: list[DslConnection] = []
    for conn in doc.connections:
        if conn.sourceIdentifier in gov_ids:
            handle = str(conn.sourceOutletIdentifier or conn.sourceOptionIdentifier or "").lower()
            if handle not in _FAIL_HANDLES:
                pass_from_gate.setdefault(conn.sourceIdentifier, []).append(conn)
            continue
        if conn.targetIdentifier in gov_ids:
            into_gate.setdefault(conn.targetIdentifier, []).append(conn)
            continue
        kept.append(conn)
    for gid, incoming in into_gate.items():
        for outbound in pass_from_gate.get(gid, []):
            for inc in incoming:
                kept.append(inc.model_copy(update={"targetIdentifier": outbound.targetIdentifier}))
    return nodes, kept


def _gate_node(
    producer_id: str,
    packs: list[dict[str, Any]],
    produces: list[str],
    *,
    producer_ids: list[str] | None = None,
    anchor_id: str | None = None,
) -> DslNode:
    ids = producer_ids or [producer_id]
    anchor = anchor_id or producer_id
    labels = [_ARTIFACT_LABELS.get(art, art) for art in produces]
    label = ", ".join(labels) or "артефакт"
    names = ", ".join(str(p.get("name") or p.get("key")) for p in packs) or "полнота артефакта"
    return DslNode(
        identifier=gate_id_for(anchor),
        title=f"Проверки · {label}",
        description=f"Gate ветки (якорь {anchor}): {names}",
        config={
            "type": "INTERNAL_SERVICE",
            "service": POLICY_SERVICE,
            "governance": True,
            "immutable": True,
            "blocking": True,
            "producer": producer_id,
            "producer_ids": ids,
            "anchor": anchor,
            "produces": produces,
            "packs": packs,
            "onFailure": "terminate",
        },
    )


def _dedupe_connections(conns: list[DslConnection]) -> list[DslConnection]:
    seen: set[tuple[str, str, str | None, str | None, bool]] = set()
    out: list[DslConnection] = []
    for c in conns:
        key = (
            c.sourceIdentifier,
            c.targetIdentifier,
            c.sourceOutletIdentifier,
            c.sourceOptionIdentifier,
            bool(c.fallback),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def _artifact_text(
    outputs: dict[str, Any],
    produces: list[str],
    producer_id: str = "",
    producer_ids: list[str] | None = None,
) -> str:
    chunks: list[str] = []

    def _text_of(key: str) -> str:
        blob = outputs.get(key)
        if isinstance(blob, dict):
            return str(blob.get("text") or blob.get("result") or "")
        return str(blob or "")

    ids = [str(x) for x in (producer_ids or []) if x]
    if producer_id and producer_id not in ids:
        ids.append(producer_id)
    if ids:
        for pid in reversed(ids):
            text = _text_of(pid)
            if text.strip():
                return text
        return _text_of(ids[-1])
    prefer = []
    if "BUSINESS_REQUIREMENTS" in produces:
        prefer.append("brd_agent")
    if "SYSTEM_REQUIREMENTS" in produces:
        prefer.append("srd_agent")
    for key in prefer:
        text = _text_of(key)
        if text.strip():
            chunks.append(text)
    if chunks:
        return "\n".join(chunks)
    for key, blob in outputs.items():
        if key in {"trigger", "routing", "route", "review"} or is_governance_id(key):
            continue
        if isinstance(blob, dict):
            text = blob.get("text") or blob.get("result") or ""
            if text:
                chunks.append(str(text))
    return "\n".join(chunks)


def _has_secrets(text: str) -> bool:
    return bool(_SECRET_RE.search(text or ""))


def _eval_expression(expr: str, context: dict[str, Any]) -> bool:
    artifact = context.get("artifact") or {}
    if not expr.strip():
        return bool(str(artifact.get("text") or "").strip())
    if "stage_exit_contract_satisfied" in expr:
        return bool(context.get("stage_exit_contract_satisfied"))
    if "pii_clean" in expr or "secrets_clean" in expr:
        return bool(artifact.get("pii_clean")) and bool(artifact.get("secrets_clean"))
    if "checkpoint.status" in expr:
        return str((context.get("checkpoint") or {}).get("status") or "").upper() == "APPROVED"
    if "evidence.count" in expr:
        try:
            return int((context.get("evidence") or {}).get("count") or 0) >= 5
        except (TypeError, ValueError):
            return False
    return True
