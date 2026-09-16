"""workflow persistence: draft → normalize → parse → Temporal run."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4, uuid5

from src.platform.graphs.governance import (
    compile_governance,
    is_fail_connection,
    is_governance_id,
    is_governance_node,
    is_producing_node,
    is_publication_node,
    publication_nodes,
)
from src.platform.graphs.models import (
    GraphKind,
    GraphRecord,
    GraphRun,
    GraphVersion,
    ValidationReport,
)
from src.platform.graphs.normalize import normalize_workflow_dsl
from src.platform.graphs.parse import parse_workflow_to_temporal
from src.platform.graphs.workflow_dsl import WorkflowDsl, parse_workflow_dsl, workflow_dsl_to_canvas
from src.platform.db.settings import workflows_use_postgres
from src.platform.graphs.registry import registry_as_dicts
from src.platform.store import append_audit, get_platform_dir

logger = logging.getLogger(__name__)
NS = UUID("b2c3d4e5-6f70-4890-bcde-f01234567890")
_PG_SEED_CHECKED = False


def _id(kind: str, key: str) -> UUID:
    return uuid5(NS, f"{kind}:{key}")


def reset_graphs_seed_cache() -> None:
    global _PG_SEED_CHECKED
    _PG_SEED_CHECKED = False
    try:
        from src.platform.graphs.activity_catalog import reset_activity_catalog_cache

        reset_activity_catalog_cache()
    except Exception:
        pass


def _pg_session():
    from src.platform.db.session import session_scope

    return session_scope()


def _repo(session):
    from src.platform.graphs.repository import WorkflowsRepository

    return WorkflowsRepository(session)


def _path(name: str) -> Path:
    return get_platform_dir() / name


def _read_json(name: str, default: Any) -> Any:
    path = _path(name)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed reading %s: %s", path, exc)
        return default


def _write_json(name: str, payload: Any) -> None:
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _json_graph_records() -> list[GraphRecord]:
    return [GraphRecord.model_validate(i) for i in _read_json("graph_records.json", {"graphs": []}).get("graphs", [])]


def _parse_json_versions(raw: list[dict[str, Any]]) -> list[GraphVersion]:
    return [GraphVersion.model_validate(i) for i in raw]


def _json_graph_versions() -> list[GraphVersion]:
    raw = _read_json("graph_versions.json", {"versions": []}).get("versions", [])
    return _parse_json_versions(raw)


def _load_records() -> list[GraphRecord]:
    if workflows_use_postgres():
        with _pg_session() as session:
            return _repo(session).list_records()
    return [GraphRecord.model_validate(i) for i in _read_json("graph_records.json", {"graphs": []}).get("graphs", [])]


def _save_records(items: list[GraphRecord]) -> None:
    if workflows_use_postgres():
        with _pg_session() as session:
            repo = _repo(session)
            for rec in items:
                repo.upsert_record(rec)
        return
    _write_json("graph_records.json", {"graphs": [i.model_dump(mode="json") for i in items]})


def save_record(record: GraphRecord, *, expected_revision: int | None = None) -> GraphRecord:
    """Persist one workflow record without rewriting unrelated PostgreSQL rows."""
    if workflows_use_postgres():
        with _pg_session() as session:
            if expected_revision is not None:
                return _repo(session).update_record_if_revision(record, expected_revision)
            return _repo(session).upsert_record(record)
    records = _load_records()
    for index, item in enumerate(records):
        if item.id == record.id:
            records[index] = record
            break
    else:
        records.append(record)
    _save_records(records)
    return record


def _load_versions() -> list[GraphVersion]:
    if workflows_use_postgres():
        with _pg_session() as session:
            return _repo(session).list_versions()
    raw = _read_json("graph_versions.json", {"versions": []}).get("versions", [])
    return _parse_json_versions(raw)


def _save_versions(items: list[GraphVersion]) -> None:
    if workflows_use_postgres():
        with _pg_session() as session:
            repo = _repo(session)
            for ver in items:
                repo.upsert_version(ver)
        return
    _write_json("graph_versions.json", {"versions": [i.model_dump(mode="json") for i in items]})


def _load_runs() -> list[GraphRun]:
    if workflows_use_postgres():
        with _pg_session() as session:
            return _repo(session).list_runs()
    return [GraphRun.model_validate(i) for i in _read_json("graph_runs.json", {"runs": []}).get("runs", [])]


def _save_runs(items: list[GraphRun]) -> None:
    if workflows_use_postgres():
        with _pg_session() as session:
            repo = _repo(session)
            for run in items:
                repo.upsert_run(run)
        return
    _write_json("graph_runs.json", {"runs": [i.model_dump(mode="json") for i in items]})


def save_run(run: GraphRun) -> GraphRun:
    """Persist one execution projection without rewriting unrelated rows."""
    if workflows_use_postgres():
        with _pg_session() as session:
            return _repo(session).upsert_run(run)
    runs = _load_runs()
    for index, item in enumerate(runs):
        if item.id == run.id:
            runs[index] = run
            break
    else:
        runs.append(run)
    _save_runs(runs)
    return run


def ensure_graphs_seeded() -> None:
    """Graphs are persisted from designer saves, not migrated from a legacy catalog."""
    global _PG_SEED_CHECKED
    if workflows_use_postgres():
        from src.platform.db.schema import ensure_schema

        ensure_schema()
        if _PG_SEED_CHECKED:
            return
        with _pg_session() as session:
            repo = _repo(session)
            repo.ensure_workspace()
            repo.ensure_node_types()
            if repo.count_workflows() == 0:
                for rec in _json_graph_records():
                    repo.upsert_record(rec)
                for ver in _json_graph_versions():
                    repo.upsert_version(ver)
        _PG_SEED_CHECKED = True
        return
    marker = _path(".seeded_graphs_v1")
    if not marker.exists():
        if not _path("graph_records.json").exists():
            _save_records([])
            _save_versions([])
        marker.write_text("1\n", encoding="utf-8")


def _as_ui(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def _merge_positions(*sources: dict[str, Any] | None) -> dict[str, Any]:
    """Later sources win. Used so author-saved coordinates beat compile defaults."""
    out: dict[str, Any] = {}
    for src in sources:
        if not isinstance(src, dict):
            continue
        for nid, pos in src.items():
            if nid and isinstance(pos, dict):
                out[str(nid)] = pos
    return out


def prepare_workflow_doc(raw: Any, *, ui: dict[str, Any] | None = None) -> WorkflowDsl:
    """Normalize + inject one locked governance gate at each parallel-branch tip.

    Saved canvas coordinates (``ui.positions``) survive compile: new gates get a
    default slot only when the author has not placed them yet.
    """
    parsed = parse_workflow_dsl(raw.model_dump(mode="json") if hasattr(raw, "model_dump") else raw)
    saved_ui = _as_ui(parsed.ui)
    extra_ui = _as_ui(ui)
    saved_positions = _merge_positions(saved_ui.get("positions"), extra_ui.get("positions"))
    layout_ui = {**saved_ui, **extra_ui}
    if saved_positions:
        layout_ui["positions"] = saved_positions
    normalized = normalize_workflow_dsl(parsed)
    if layout_ui:
        normalized = normalized.model_copy(update={"ui": layout_ui})
    doc = compile_governance(normalized)
    merged_ui = dict(layout_ui)
    if doc.ui:
        merged_ui["positions"] = _merge_positions(
            (doc.ui or {}).get("positions"),
            saved_positions,
        )
        for key, value in doc.ui.items():
            if key != "positions" and key not in merged_ui:
                merged_ui[key] = value
    elif saved_positions:
        merged_ui["positions"] = saved_positions
    if merged_ui:
        doc = doc.model_copy(update={"ui": merged_ui})
    return doc


def validate_workflow(doc: WorkflowDsl) -> ValidationReport:
    report = ValidationReport()
    if not doc.nodes:
        report.add("EMPTY", "Workflow has no nodes")
        return report
    node_ids = [n.identifier for n in doc.nodes]
    if any(not node_id.strip() for node_id in node_ids):
        report.add("EMPTY_NODE_ID", "Workflow node identifiers must not be empty")
    if len(node_ids) != len(set(node_ids)):
        report.add("DUPLICATE_ID", "Duplicate node identifiers")
    node_by_id = {n.identifier: n for n in doc.nodes}
    node_types = {
        node.identifier: str((node.config or {}).get("type") or "").upper()
        for node in doc.nodes
    }
    triggers = [
        node for node in doc.nodes
        if node_types[node.identifier].endswith("TRIGGER")
        or node_types[node.identifier] in {"SELF_SERVE_TRIGGER", "EVENT_TRIGGER", "SCHEDULE_TRIGGER"}
    ]
    if len(triggers) != 1:
        report.add("TRIGGER_COUNT", f"Workflow requires exactly one trigger; found {len(triggers)}")

    unsupported = {"KAFKA", "UPSERT_ENTITY", "INTEGRATION_ACTION"}
    for node in doc.nodes:
        if node_types[node.identifier] in unsupported:
            report.add(
                "UNSUPPORTED_NODE",
                f"{node_types[node.identifier]} is not available in the runtime",
                node_id=node.identifier,
            )

    valid_connections = [
        connection for connection in doc.connections
        if connection.sourceIdentifier in node_by_id and connection.targetIdentifier in node_by_id
    ]
    outgoing: dict[str, list[Any]] = {}
    for connection in valid_connections:
        outgoing.setdefault(connection.sourceIdentifier, []).append(connection)

    if triggers:
        reachable: set[str] = set()
        queue = [triggers[0].identifier]
        while queue:
            current = queue.pop(0)
            if current in reachable:
                continue
            reachable.add(current)
            queue.extend(edge.targetIdentifier for edge in outgoing.get(current, []))
        for node_id in sorted(set(node_ids) - reachable):
            report.add("UNREACHABLE_NODE", f"Node {node_id} is not reachable from the trigger", node_id=node_id)

    # Reject unconditional activity loops. Conditional, INPUT, and governance
    # feedback edges are explicit author/runtime routing and remain supported.
    linear_adj: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for connection in valid_connections:
        source = node_by_id[connection.sourceIdentifier]
        source_type = node_types[source.identifier]
        if source_type in {"CONDITION", "INPUT"} or is_governance_node(source):
            continue
        linear_adj[source.identifier].append(connection.targetIdentifier)
    visiting: set[str] = set()
    visited: set[str] = set()

    def _visit(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        for target_id in linear_adj.get(node_id, []):
            if _visit(target_id):
                return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    if any(_visit(node_id) for node_id in node_ids if node_id not in visited):
        report.add("UNCONDITIONAL_CYCLE", "Workflow contains an unconditional activity cycle")

    pubs = publication_nodes(doc)
    producers = [n for n in doc.nodes if is_producing_node(n)]
    if pubs and producers and not (doc.produces or []):
        report.add(
            "MISSING_PRODUCES",
            "Сценарий публикует результат — укажите тип выходного артефакта на шаге агента (produces)",
        )
    by_id = {n.identifier: n for n in doc.nodes}
    author_sources: dict[str, set[str]] = {}
    for c in doc.connections:
        src = by_id.get(c.sourceIdentifier)
        if src and is_governance_node(src) and is_fail_connection(c):
            continue
        author_sources.setdefault(c.targetIdentifier, set()).add(c.sourceIdentifier)

    def _is_join(nid: str) -> bool:
        node = by_id.get(nid)
        if not node or is_publication_node(node) or is_governance_node(node):
            return False
        t = str((node.config or {}).get("type") or "").upper()
        if t == "CONDITION" or t.endswith("TRIGGER"):
            return False
        return len(author_sources.get(nid, ())) > 1

    def _exempt_source(node) -> bool:
        t = str((node.config or {}).get("type") or "").upper()
        if t.endswith("TRIGGER") or t in {
            "START", "SELF_SERVE_TRIGGER", "EVENT_TRIGGER", "SCHEDULE_TRIGGER", "CONDITION",
        }:
            return True
        return _is_join(node.identifier)

    gov_nodes = [n for n in doc.nodes if is_governance_node(n)]
    if pubs and producers and not gov_nodes:
        report.add(
            "MISSING_GOVERNANCE_GATE",
            "У каждой параллельной ветки с артефактом должен быть control gate",
        )
    terminals = [n for n in doc.nodes if is_publication_node(n) or _is_join(n.identifier)]
    for term in terminals:
        for c in doc.connections:
            if c.targetIdentifier != term.identifier:
                continue
            src = by_id.get(c.sourceIdentifier)
            if not src or is_governance_node(src) or _exempt_source(src):
                continue
            report.add(
                "GOVERNANCE_GATE_BYPASS",
                f"Ветка не может обходить control gate перед «{term.identifier}»",
                node_id=src.identifier,
            )
    by_id = set(node_ids)
    for c in doc.connections:
        if c.sourceIdentifier not in by_id:
            report.add("BAD_CONNECTION", f"Unknown source {c.sourceIdentifier}")
        if c.targetIdentifier not in by_id:
            report.add("BAD_CONNECTION", f"Unknown target {c.targetIdentifier}")
    for n in doc.nodes:
        t = str((n.config or {}).get("type") or "").upper()
        if t == "END":
            report.add(
                "INVALID_NODE",
                "Узел End не используется — выполнение заканчивается на последнем действии",
                node_id=n.identifier,
                severity="warning",
            )
        if t == "WEBHOOK" and not (n.config or {}).get("url"):
            report.add("MISSING_URL", "WEBHOOK requires url", node_id=n.identifier)
        if t == "AI_AGENT" and not (n.config or {}).get("agentIdentifier"):
            report.add("MISSING_AGENT", "AI_AGENT requires agentIdentifier", node_id=n.identifier)
        if t == "AI" and not (n.config or {}).get("userPrompt"):
            report.add("MISSING_PROMPT", "AI requires userPrompt", node_id=n.identifier)
        if t == "INTERNAL_SERVICE" and not (n.config or {}).get("service"):
            report.add("MISSING_SERVICE", "INTERNAL_SERVICE requires service", node_id=n.identifier)
        if t == "SUBFLOW" and not (
            (n.config or {}).get("graph_key")
            or (n.config or {}).get("graph_id")
            or (n.config or {}).get("flow_key")
        ):
            report.add("MISSING_SUBFLOW", "SUBFLOW requires a target scenario", node_id=n.identifier)
        if t == "CONDITION":
            options = (n.config or {}).get("options") or []
            if not isinstance(options, list) or not options:
                report.add("MISSING_OPTIONS", "CONDITION requires options[]", node_id=n.identifier)
            else:
                edges = outgoing.get(n.identifier, [])
                fallback_edges = [edge for edge in edges if edge.fallback]
                if len(fallback_edges) > 1:
                    report.add("MULTIPLE_FALLBACKS", "CONDITION allows at most one fallback", node_id=n.identifier)
                connected_options = {
                    edge.sourceOptionIdentifier or edge.sourceOutletIdentifier
                    for edge in edges
                    if not edge.fallback
                }
                for option in options:
                    if not isinstance(option, dict) or not option.get("identifier"):
                        continue
                    option_id = str(option["identifier"])
                    if option_id not in connected_options:
                        report.add(
                            "UNCONNECTED_CONDITION_OPTION",
                            f"Condition option {option_id} has no outgoing connection",
                            node_id=n.identifier,
                            severity="warning",
                        )
                    if not str(option.get("expression") or "").strip():
                        report.add(
                            "EMPTY_CONDITION_EXPRESSION",
                            f"Condition option {option_id} requires an expression; use a fallback edge for default routing",
                            node_id=n.identifier,
                        )
        if t == "INPUT":
            outlets = (n.config or {}).get("outlets") or []
            edges = outgoing.get(n.identifier, [])
            connected = {
                edge.sourceOutletIdentifier or edge.sourceOptionIdentifier
                for edge in edges
                if not edge.fallback
            }
            for outlet in outlets if isinstance(outlets, list) else []:
                if not isinstance(outlet, dict) or not outlet.get("identifier"):
                    continue
                outlet_id = str(outlet["identifier"])
                if outlet_id not in connected:
                    report.add(
                        "UNCONNECTED_INPUT_OUTLET",
                        f"Input outlet {outlet_id} has no outgoing connection",
                        node_id=n.identifier,
                        severity="warning",
                    )
    try:
        from src.platform.contracts.validation import validate_graph_contracts

        contracts = validate_graph_contracts(doc)
        for issue in contracts.get("errors", []):
            report.add(str(issue.get("code") or "CONTRACT_ERROR"), str(issue.get("message") or "Contract error"))
        for issue in contracts.get("warnings", []):
            report.add(
                str(issue.get("code") or "CONTRACT_WARNING"),
                str(issue.get("message") or "Contract warning"),
                severity="warning",
            )
    except Exception as exc:
        report.add("CONTRACT_VALIDATION_ERROR", str(exc))
    try:
        parse_workflow_to_temporal(doc)
    except Exception as exc:
        report.add("PARSE_ERROR", str(exc))
    return report


def list_graphs(kind: GraphKind | None = None) -> list[GraphRecord]:
    ensure_graphs_seeded()
    items = _load_records()
    if kind:
        items = [i for i in items if i.kind == kind]
    return items


def list_all_versions() -> list[GraphVersion]:
    ensure_graphs_seeded()
    return _load_versions()


def get_graph(graph_id: UUID) -> GraphRecord:
    ensure_graphs_seeded()
    for r in _load_records():
        if r.id == graph_id:
            return r
    raise KeyError(graph_id)


def get_graph_by_key(key: str) -> GraphRecord:
    ensure_graphs_seeded()
    records = _load_records()
    exact = [record for record in records if record.key == key]
    if exact:
        return exact[0]
    if ":" not in key:
        matches = [record for record in records if record.key.endswith(f":{key}")]
        if len(matches) == 1:
            return matches[0]
    raise KeyError(key)


def set_graph_launched(flow_or_graph_key: str, launched: bool) -> None:
    """Keep the linked graph in sync with flow launch/stop."""
    ensure_graphs_seeded()
    records = _load_records()
    changed = False
    for rec in records:
        if rec.key == flow_or_graph_key or rec.key.endswith(f":{flow_or_graph_key}"):
            if rec.launched != launched:
                rec.launched = launched
                rec.updated_at = datetime.utcnow()
                changed = True
    if changed:
        _save_records(records)


def delete_graph(graph_id: UUID) -> None:
    ensure_graphs_seeded()
    if workflows_use_postgres():
        with _pg_session() as session:
            _repo(session).delete_record(graph_id)
        return
    _save_records([r for r in _load_records() if r.id != graph_id])
    _save_versions([v for v in _load_versions() if v.graph_id != graph_id])
    _save_runs([r for r in _load_runs() if r.graph_id != graph_id])


def get_version(version_id: UUID) -> GraphVersion:
    for v in _load_versions():
        if v.id == version_id:
            return v
    raise KeyError(version_id)


def create_graph(
    *,
    key: str,
    name: str,
    kind: GraphKind,
    description: str = "",
    graph: Any = None,
) -> GraphRecord:
    ensure_graphs_seeded()
    if not key:
        raise ValueError("key required")
    full_key = key if ":" in key else f"{kind}:{key}"
    rec = GraphRecord(id=_id(kind, full_key), key=full_key, name=name or key, kind=kind, description=description)
    dsl: dict[str, Any]
    if graph is None:
        # start with a trigger only — no End node (leaves terminate the run)
        dsl = {
            "identifier": key,
            "title": name or key,
            "description": description,
            "nodes": [
                {
                    "identifier": "trigger",
                    "title": "Trigger",
                    "config": {
                        "type": "SELF_SERVE_TRIGGER",
                        "published": True,
                        "userInputs": {"properties": {}, "required": []},
                    },
                },
            ],
            "connections": [],
            "ui": {"kind": kind},
        }
    else:
        doc = normalize_workflow_dsl(graph if isinstance(graph, WorkflowDsl) else parse_workflow_dsl(
            graph.model_dump(mode="json") if hasattr(graph, "model_dump") else graph
        ))
        dsl = doc.model_dump(mode="json")
        dsl["ui"] = {"kind": kind, **(dsl.get("ui") or {})}

    ver = GraphVersion(graph_id=rec.id, dsl=dsl, status="DRAFT")
    report = validate_workflow(normalize_workflow_dsl(dsl))
    ver.validation_status = "valid" if report.ok else "invalid"
    ver.validation_report = report.model_dump(mode="json")
    rec.current_draft_version_id = ver.id
    records = _load_records()
    versions = _load_versions()
    records.append(rec)
    versions.append(ver)
    if workflows_use_postgres():
        # Insert the workflow before its version, then attach the circular
        # current-version pointer once both referenced rows exist.
        detached = rec.model_copy(update={"current_draft_version_id": None})
        _save_records([*records[:-1], detached])
        _save_versions(versions)
        save_record(rec)
    else:
        _save_records(records)
        _save_versions(versions)
    append_audit("create", "graph", str(rec.id), rec.key)
    return rec


def ensure_linked_graph(*, kind: GraphKind, key: str, name: str | None = None) -> GraphRecord:
    full = key if ":" in key else f"{kind}:{key}"
    try:
        return get_graph_by_key(full)
    except KeyError:
        return create_graph(key=full, name=name or key, kind=kind)


def save_draft(graph_id: UUID, graph: Any, revision: int | None = None) -> GraphVersion:
    rec = get_graph(graph_id)
    raw = graph.model_dump(mode="json") if hasattr(graph, "model_dump") else graph
    ui = raw.get("ui") if isinstance(raw, dict) and isinstance(raw.get("ui"), dict) else None
    doc = prepare_workflow_doc(raw, ui=ui)
    dsl = doc.model_dump(mode="json")
    if rec.kind:
        dsl.setdefault("ui", {})
        if isinstance(dsl["ui"], dict):
            dsl["ui"].setdefault("kind", rec.kind)

    versions = _load_versions()
    draft = None
    if rec.current_draft_version_id:
        for v in versions:
            if v.id == rec.current_draft_version_id:
                draft = v
                break
    if draft is None:
        draft = GraphVersion(graph_id=rec.id, status="DRAFT")
        versions.append(draft)
        rec.current_draft_version_id = draft.id

    if revision is not None and draft.revision != revision:
        raise ValueError(f"revision conflict: expected {draft.revision}")

    draft.dsl = dsl
    draft.temporal_plan = None
    draft.revision += 1
    draft.updated_at = datetime.utcnow()
    report = validate_workflow(doc)
    draft.validation_status = "valid" if report.ok else "invalid"
    draft.validation_report = report.model_dump(mode="json")

    records = _load_records()
    for i, r in enumerate(records):
        if r.id == rec.id:
            r.updated_at = datetime.utcnow()
            r.revision += 1
            records[i] = r
            break
    for i, v in enumerate(versions):
        if v.id == draft.id:
            versions[i] = draft
            break
    _save_versions(versions)
    _save_records(records)
    return draft


def publish_version(graph_id: UUID, version_id: UUID | None = None) -> GraphVersion:
    rec = get_graph(graph_id)
    versions = _load_versions()
    vid = version_id or rec.current_draft_version_id
    if not vid:
        raise ValueError("no draft to publish")
    target = next(v for v in versions if v.id == vid)
    if target.status == "PUBLISHED":
        if rec.current_published_version_id == target.id:
            return target
        raise ValueError("published versions are immutable")
    if target.status != "DRAFT":
        raise ValueError("only draft versions can be published")
    ui = target.dsl.get("ui") if isinstance(target.dsl, dict) else None
    doc = prepare_workflow_doc(target.dsl, ui=ui if isinstance(ui, dict) else None)
    report = validate_workflow(doc)
    if not report.ok:
        raise ValueError(f"cannot publish: {[i.code for i in report.issues]}")
    plan = parse_workflow_to_temporal(doc, version=target.semantic_version)
    dsl = doc.model_dump(mode="json")
    if ui:
        dsl["ui"] = ui
    target.dsl = dsl
    target.temporal_plan = plan.to_dict()
    target.status = "PUBLISHED"
    target.validation_status = "valid"
    target.validation_report = report.model_dump(mode="json")
    target.published_at = datetime.utcnow()
    target.updated_at = datetime.utcnow()
    for v in versions:
        if v.graph_id == graph_id and v.id != target.id and v.status == "PUBLISHED":
            v.status = "DEPRECATED"
    records = _load_records()
    for i, r in enumerate(records):
        if r.id == graph_id:
            r.current_published_version_id = target.id
            r.current_draft_version_id = None
            r.status = "active"
            r.updated_at = datetime.utcnow()
            records[i] = r
    for i, v in enumerate(versions):
        if v.id == target.id:
            versions[i] = target
    _save_records(records)
    _save_versions(versions)
    append_audit("publish", "graph", str(graph_id), f"Published {target.id}")
    return target


def create_draft_from_published(graph_id: UUID) -> GraphVersion:
    """Create an editable snapshot without ever mutating a published version."""
    rec = get_graph(graph_id)
    if rec.current_draft_version_id:
        draft = get_version(rec.current_draft_version_id)
        if draft.status == "DRAFT":
            return draft
    if not rec.current_published_version_id:
        raise ValueError("scenario has no published version to draft")
    published = get_version(rec.current_published_version_id)
    now = datetime.utcnow()
    draft = GraphVersion(
        graph_id=rec.id,
        semantic_version=published.semantic_version,
        status="DRAFT",
        dsl=dict(published.dsl or {}),
        temporal_plan=None,
        validation_status=published.validation_status,
        validation_report=dict(published.validation_report or {}),
        revision=1,
        created_at=now,
        updated_at=now,
    )
    versions = _load_versions()
    versions.append(draft)
    records = _load_records()
    for index, item in enumerate(records):
        if item.id == rec.id:
            item.current_draft_version_id = draft.id
            item.status = "draft"
            item.launched = False
            item.revision += 1
            item.updated_at = now
            records[index] = item
            break
    _save_versions(versions)
    _save_records(records)
    return draft


def validate_only(graph: Any) -> ValidationReport:
    raw = graph.model_dump(mode="json") if hasattr(graph, "model_dump") else graph
    return validate_workflow(prepare_workflow_doc(raw))


def node_types(kind: GraphKind | None = None) -> list[dict[str, Any]]:
    from src.platform.graphs.activity_catalog import resolve_worker

    entries = registry_as_dicts(kind, palette_only=True)
    for entry in entries:
        binding = resolve_worker(str(entry.get("type") or ""))
        if binding:
            entry["worker"] = binding.worker
            entry["temporalActivity"] = binding.worker
            entry["family"] = binding.family
    return entries


def create_run(
    *,
    graph_id: UUID,
    input_payload: dict[str, Any] | None = None,
    version_id: UUID | None = None,
    start_temporal: bool = True,
) -> GraphRun:
    rec = get_graph(graph_id)
    payload = dict(input_payload or {})
    is_test = str(payload.pop("_source", "") or "").upper() == "TEST"
    if str(payload.get("source") or "").upper() == "TEST":
        payload.pop("source", None)
        is_test = True
    if is_test:
        vid = version_id or rec.current_draft_version_id or rec.current_published_version_id
    else:
        vid = version_id or rec.current_published_version_id
    if not vid:
        raise ValueError("live run requires a published version" if not is_test else "graph has no version")
    ver = get_version(vid)
    if is_test:
        ui = ver.dsl.get("ui") if isinstance(ver.dsl, dict) else None
        doc = prepare_workflow_doc(ver.dsl, ui=ui if isinstance(ui, dict) else None)
        report = validate_workflow(doc)
        if not report.ok:
            raise ValueError("cannot run invalid workflow: " + ", ".join(i.code for i in report.issues[:5]))
        plan_dict = parse_workflow_to_temporal(doc, version=ver.semantic_version).to_dict()
    else:
        if ver.status != "PUBLISHED" or not ver.temporal_plan:
            raise ValueError("live run requires a frozen published plan")
        plan_dict = dict(ver.temporal_plan)

    run = GraphRun(
        id=uuid4(),
        graph_id=graph_id,
        version_id=vid,
        status="pending",
        input=payload,
        state={
            "outputs": {},
            "source": "TEST" if is_test else "LIVE",
            "plan": plan_dict,
            "engine": "local" if is_test else "temporal",
        },
        events=[{"type": "created", "at": datetime.utcnow().isoformat()}],
    )
    if is_test:
        run.status = "running"
        run.events.append({"type": "local_start", "at": datetime.utcnow().isoformat()})
        save_run(run)
        from src.platform.graphs.local_run import spawn

        spawn(run.id, plan_dict)
        append_audit("run", "graph", str(graph_id), f"Created local test run {run.id}")
        return run
    if start_temporal:
        try:
            wf_id = _start_interpreter(run, plan_dict)
            run.temporal_workflow_id = wf_id
            run.status = "running"
            run.events.append({"type": "started", "workflow_id": wf_id, "at": datetime.utcnow().isoformat()})
        except Exception as exc:
            logger.warning("Temporal start failed: %s", exc)
            run.status = "failed"
            run.error = f"Temporal не запущен: {exc}"
            run.events.append({"type": "start_failed", "error": str(exc), "at": datetime.utcnow().isoformat()})
    save_run(run)
    append_audit("run", "graph", str(graph_id), f"Created run {run.id}")
    return run


async def create_run_and_start(
    *,
    graph_id: UUID,
    input_payload: dict[str, Any] | None = None,
    version_id: UUID | None = None,
) -> GraphRun:
    """Persist a live run and await Temporal's start acknowledgement."""
    run = create_run(
        graph_id=graph_id,
        input_payload=input_payload,
        version_id=version_id,
        start_temporal=False,
    )
    try:
        workflow_id = await _start_interpreter_async(run, dict((run.state or {}).get("plan") or {}))
        run.temporal_workflow_id = workflow_id
        run.status = "running"
        run.events.append({"type": "started", "workflow_id": workflow_id, "at": datetime.utcnow().isoformat()})
    except Exception as exc:
        run.status = "failed"
        run.error = f"Temporal не запущен: {exc}"
        run.events.append({"type": "start_failed", "error": str(exc), "at": datetime.utcnow().isoformat()})
    update_run(run)
    return run


def get_run(run_id: UUID) -> GraphRun:
    for r in _load_runs():
        if r.id == run_id:
            return r
    raise KeyError(run_id)


def ensure_live_run(
    *,
    run_id: str | UUID,
    graph_id: str | UUID,
    version_id: str | UUID | None = None,
    temporal_workflow_id: str | None = None,
) -> GraphRun | None:
    """Attach a GraphRun to a live Slack/Jira task so inspector viewer works.

    Does not start Temporal — the parent TaskLifecycle already runs the interpreter.
    """
    try:
        rid = UUID(str(run_id))
        gid = UUID(str(graph_id))
    except Exception:
        return None
    try:
        existing = get_run(rid)
        if temporal_workflow_id and existing.temporal_workflow_id != temporal_workflow_id:
            existing.temporal_workflow_id = temporal_workflow_id
            return update_run(existing)
        return existing
    except KeyError:
        pass
    rec = get_graph(gid)
    vid = UUID(str(version_id)) if version_id else rec.current_published_version_id
    if not vid:
        return None
    run = GraphRun(
        id=rid,
        graph_id=gid,
        version_id=vid,
        status="running",
        state={"source": "LIVE", "engine": "temporal"},
        temporal_workflow_id=temporal_workflow_id or None,
        events=[{"type": "created", "at": datetime.utcnow().isoformat(), "source": "live_ingress"}],
    )
    save_run(run)
    return run


def update_run(run: GraphRun) -> GraphRun:
    run.updated_at = datetime.utcnow()
    return save_run(run)


def append_run_event(run_id: UUID, event: dict[str, Any]) -> None:
    run = get_run(run_id)
    event_id = event.get("event_id")
    if event_id and any(existing.get("event_id") == event_id for existing in run.events):
        return
    run.events.append({**event, "at": event.get("at") or datetime.utcnow().isoformat()})
    update_run(run)


def signal_run(run_id: UUID, signal: str, payload: dict[str, Any] | None = None) -> GraphRun:
    run = get_run(run_id)
    payload = dict(payload or {})
    decision = str(payload.get("decision") or signal or "").strip() or signal
    if decision == "reject":
        decision = "decline"
    payload["decision"] = decision
    run.events.append({"type": f"signal_{signal}", "payload": payload, "at": datetime.utcnow().isoformat()})
    if run.status == "waiting":
        run.status = "running"
    run = update_run(run)
    if (run.state or {}).get("engine") == "local" or not run.temporal_workflow_id:
        run.state = {**(run.state or {}), "resume_signal": payload}
        run = update_run(run)
        from src.platform.graphs.local_run import spawn

        spawn(run_id, (run.state or {}).get("plan") or {})
        return get_run(run_id)
    if run.temporal_workflow_id:
        try:
            _signal_temporal(run.temporal_workflow_id, signal, payload)
        except Exception as exc:
            logger.warning("Temporal signal failed: %s", exc)
    return update_run(run)


async def signal_run_async(run_id: UUID, signal: str, payload: dict[str, Any] | None = None) -> GraphRun:
    run = get_run(run_id)
    payload = dict(payload or {})
    decision = str(payload.get("decision") or signal or "").strip() or signal
    if decision == "reject":
        decision = "decline"
    payload["decision"] = decision
    pending = (run.state or {}).get("pending_approval")
    pending_node = pending.get("node_id") if isinstance(pending, dict) else None
    requested_node = payload.get("node_id")
    if pending_node and requested_node and str(pending_node) != str(requested_node):
        raise ValueError(f"run is waiting for node {pending_node}, not {requested_node}")
    if pending_node:
        payload.setdefault("node_id", pending_node)
    if (run.state or {}).get("engine") == "local" or not run.temporal_workflow_id:
        run.state = {**(run.state or {}), "resume_signal": payload}
        run.status = "running"
        run.events.append({"type": f"signal_{signal}", "payload": payload, "at": datetime.utcnow().isoformat()})
        update_run(run)
        from src.platform.graphs.local_run import spawn

        spawn(run_id, (run.state or {}).get("plan") or {})
        return get_run(run_id)
    await _signal_temporal_async(run.temporal_workflow_id, signal, payload)
    run.events.append({"type": f"signal_{signal}", "payload": payload, "at": datetime.utcnow().isoformat()})
    if run.status == "waiting":
        run.status = "running"
    return update_run(run)


def _run_state_snapshot(run: GraphRun) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "status": run.status,
        "outputs": (run.state or {}).get("outputs") or run.output or {},
        "current_node_id": (run.state or {}).get("current_node_id") or (run.state or {}).get("cursor"),
        "pending_approval": (run.state or {}).get("pending_approval"),
        "run_id": str(run.id),
        "error": run.error,
        "events": (run.events or [])[-12:],
        "engine": (run.state or {}).get("engine"),
    }
    return raw


def query_run_state(run_id: UUID) -> dict[str, Any]:
    run = get_run(run_id)
    raw = _run_state_snapshot(run)
    if run.temporal_workflow_id:
        try:
            ts = _query_temporal(run.temporal_workflow_id)
            if isinstance(ts, dict):
                raw.update({k: v for k, v in ts.items() if v is not None})
        except Exception:
            pass
    pending = raw.get("pending_approval") if isinstance(raw.get("pending_approval"), dict) else {}
    node_id = (pending or {}).get("node_id") or (pending or {}).get("nodeId")
    if node_id:
        raw["pending_approval"] = {"node_id": node_id}
    if not raw.get("error"):
        for ev in reversed(run.events or []):
            if ev.get("error"):
                raw["error"] = ev["error"]
                break
    return raw


async def query_run_state_async(run_id: UUID) -> dict[str, Any]:
    run = get_run(run_id)
    raw = _run_state_snapshot(run)
    if run.temporal_workflow_id:
        try:
            ts = await _query_temporal_async(run.temporal_workflow_id)
            if isinstance(ts, dict):
                raw.update({key: value for key, value in ts.items() if value is not None})
        except Exception as exc:
            raw["projection_status"] = "degraded"
            raw["temporal_query_error"] = str(exc)
    pending = raw.get("pending_approval") if isinstance(raw.get("pending_approval"), dict) else {}
    node_id = pending.get("node_id") or pending.get("nodeId")
    if node_id:
        raw["pending_approval"] = {"node_id": node_id}
    return raw


async def cancel_run_async(run_id: UUID) -> GraphRun:
    run = get_run(run_id)
    if run.temporal_workflow_id:
        await _cancel_temporal_async(run.temporal_workflow_id)
    run.status = "cancelled"
    run.error = run.error or "cancelled"
    run.events.append({"type": "cancelled", "at": datetime.utcnow().isoformat()})
    return update_run(run)


def get_published_temporal_plan(flow_or_graph_key: str) -> dict[str, Any] | None:
    """Resolve published Temporal plan for a flow/graph key."""
    ensure_graphs_seeded()
    key = flow_or_graph_key
    candidates = [key, f"e2e:{key}", f"stage:{key}"]
    rec = None
    for k in candidates:
        try:
            rec = get_graph_by_key(k)
            break
        except KeyError:
            continue
    if rec is None or not rec.current_published_version_id:
        return None
    ver = get_version(rec.current_published_version_id)
    plan = ver.temporal_plan
    if not plan:
        doc = normalize_workflow_dsl(ver.dsl)
        plan = parse_workflow_to_temporal(doc, version=ver.semantic_version).to_dict()
    return {
        "graph_id": str(rec.id),
        "version_id": str(ver.id),
        "plan": plan,
        "graph_key": rec.key,
        "graph_name": rec.name,
    }


def find_ingress_port_plan(
    *,
    flow_key: str | None = None,
    source: str | None = None,
) -> dict[str, Any] | None:
    """Published plan for live Slack/Jira ingress.

    Prefer an explicit flow key, then env pin, then a launched E2E flow/graph.
    """
    import os

    keys: list[str] = []
    if flow_key:
        keys.append(str(flow_key).strip())
    for env_name in ("SLACK_FLOW_KEY", "DEFAULT_INGRESS_FLOW_KEY"):
        env_key = (os.environ.get(env_name) or "").strip()
        if env_key and env_key.lower() not in {"auto", "classify", "*"}:
            keys.append(env_key)
    try:
        for rec in list_graphs(kind="e2e"):
            if rec.launched and rec.current_published_version_id:
                keys.append(rec.key)
    except Exception:
        logger.debug("ingress port: graph list skipped", exc_info=True)

    seen: set[str] = set()
    for key in keys:
        if not key or key in seen:
            continue
        seen.add(key)
        compiled = get_published_temporal_plan(key)
        if compiled and compiled.get("plan"):
            return {
                **compiled,
                "flow_key": key.split(":", 1)[-1],
                "flow_name": compiled.get("graph_name") or key.split(":", 1)[-1],
            }
    return None


def list_versions(graph_id: UUID) -> list[GraphVersion]:
    return [v for v in _load_versions() if v.graph_id == graph_id]


def get_draft_canvas(graph_id: UUID) -> dict[str, Any]:
    """Return canvas-friendly view of current draft workflow DSL."""
    rec = get_graph(graph_id)
    if not rec.current_draft_version_id:
        raise ValueError("no draft")
    ver = get_version(rec.current_draft_version_id)
    raw = ver.dsl if isinstance(ver.dsl, dict) else {}
    ui = raw.get("ui") if isinstance(raw.get("ui"), dict) else None
    doc = prepare_workflow_doc(raw, ui=ui)
    canvas = workflow_dsl_to_canvas(doc)
    canvas["kind"] = rec.kind
    canvas["produces"] = list(doc.produces or [])
    return canvas


def workflow_dsl_to_flow_graph(dsl: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Map workflow DSL → flow stages/edges so the E2E designer (flows UI) shows the same graph."""
    positions = ((dsl.get("ui") or {}) if isinstance(dsl.get("ui"), dict) else {}).get("positions") or {}
    producer_by_gate: dict[str, str] = {}
    for n in dsl.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("identifier") or "")
        if not is_governance_id(nid):
            continue
        cfg = n.get("config") if isinstance(n.get("config"), dict) else {}
        producer_by_gate[nid] = str(cfg.get("producer") or nid.removeprefix("governance-") or "")
    stages: list[dict[str, Any]] = []
    for n in dsl.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("identifier") or "")
        if not nid or is_governance_id(nid):
            continue
        cfg = dict(n.get("config") or {})
        t = str(cfg.get("type") or "").upper()
        if t == "END":
            continue
        stage_type = "START" if t.endswith("TRIGGER") else (t or "WEBHOOK")
        pos = positions.get(nid) if isinstance(positions, dict) else None
        if isinstance(pos, dict) and pos:
            cfg["position"] = {"x": pos.get("x") or 0, "y": pos.get("y") or 0}
        stages.append({
            "key": nid,
            "name": n.get("title") or nid,
            "type": stage_type,
            "flow_key": cfg.get("graph_key") or cfg.get("flow_key") or None,
            "knowledge_space_key": None,
            "timeout_seconds": int(cfg.get("timeout_seconds") or 3600),
            "failure_behavior": str(cfg.get("failure_behavior") or "ASK_HUMAN"),
            "config": cfg,
        })
    keep = {s["key"] for s in stages}
    edges: list[dict[str, Any]] = []
    for i, c in enumerate(dsl.get("connections") or []):
        if not isinstance(c, dict):
            continue
        src = str(c.get("sourceIdentifier") or "")
        tgt = str(c.get("targetIdentifier") or "")
        handle = c.get("sourceOptionIdentifier") or c.get("sourceOutletIdentifier")
        if is_governance_id(tgt):
            continue
        if is_governance_id(src):
            src = producer_by_gate.get(src) or src
            if str(handle or "").lower() in {"fail", "no", "block", "error", "reject"}:
                continue
            handle = None
        if not src or not tgt or src not in keep or tgt not in keep:
            continue
        if c.get("fallback") and not handle:
            handle = "fallback"
        handle = str(handle) if handle else None
        edges.append({
            "key": f"e-{src}-{tgt}-{handle or i}",
            "source": src,
            "target": tgt,
            "condition": handle,
        })
    return stages, edges


def _layout_xy(data: dict[str, Any], cfg: dict[str, Any]) -> dict[str, float] | None:
    """Read canvas coordinates from stage payload or config.position (0 is valid)."""
    x: float | None = None
    y: float | None = None
    pos = cfg.get("position") if isinstance(cfg.get("position"), dict) else None
    if pos:
        if pos.get("x") is not None:
            try:
                x = float(pos["x"])
            except (TypeError, ValueError):
                x = None
        if pos.get("y") is not None:
            try:
                y = float(pos["y"])
            except (TypeError, ValueError):
                y = None
    if data.get("x") is not None:
        try:
            x = float(data["x"])
        except (TypeError, ValueError):
            pass
    if data.get("y") is not None:
        try:
            y = float(data["y"])
        except (TypeError, ValueError):
            pass
    if x is None or y is None:
        return None
    return {"x": x, "y": y}


def _existing_ui(rec: GraphRecord) -> dict[str, Any]:
    if not rec.current_draft_version_id:
        return {}
    try:
        ver = get_version(rec.current_draft_version_id)
    except KeyError:
        return {}
    raw = ver.dsl if isinstance(ver.dsl, dict) else {}
    ui = raw.get("ui")
    return dict(ui) if isinstance(ui, dict) else {}


def mirror_flow_to_graph(
    *,
    flow_key: str,
    name: str,
    description: str = "",
    stages: list[Any],
    edges: list[Any],
    flow_id: str | None = None,
) -> GraphVersion:
    """Persist a flows-designer save into the linked graph."""
    rec = ensure_linked_graph(kind="e2e", key=flow_key, name=name or flow_key)
    existing_ui = _existing_ui(rec)
    nodes: list[dict[str, Any]] = []
    positions: dict[str, Any] = dict(existing_ui.get("positions") or {})
    for s in stages or []:
        data = s.model_dump(mode="json") if hasattr(s, "model_dump") else dict(s)
        cfg = dict(data.get("config") or {})
        stype = str(data.get("type") or cfg.get("type") or "WEBHOOK").upper()
        if stype == "END":
            continue
        if stype == "SUBFLOW":
            cfg["type"] = "SUBFLOW"
            target = data.get("flow_key") or cfg.get("graph_key") or cfg.get("flow_key")
            if target:
                cfg["graph_key"] = target
                cfg["flow_key"] = target
            cfg.setdefault("graph_kind", "e2e")
        elif stype == "START" and not str(cfg.get("type") or "").endswith("TRIGGER"):
            cfg["type"] = cfg.get("triggerType") or "SELF_SERVE_TRIGGER"
        elif "type" not in cfg:
            cfg["type"] = "SELF_SERVE_TRIGGER" if stype == "START" else stype
        nid = str(data.get("key") or "")
        xy = _layout_xy(data, cfg)
        if xy and nid:
            positions[nid] = xy
        cfg.pop("position", None)
        nodes.append({
            "identifier": nid,
            "title": data.get("name") or nid,
            "config": cfg,
        })
    connections: list[dict[str, Any]] = []
    for e in edges or []:
        data = e.model_dump(mode="json") if hasattr(e, "model_dump") else dict(e)
        handle = data.get("condition") or data.get("sourceHandle")
        src_type = ""
        for n in nodes:
            if n["identifier"] == data.get("source"):
                src_type = str((n.get("config") or {}).get("type") or "").upper()
                break
        conn: dict[str, Any] = {
            "sourceIdentifier": data.get("source"),
            "targetIdentifier": data.get("target"),
            "fallback": str(handle or "").lower() in {"fallback", "default", "else"},
        }
        if src_type == "CONDITION":
            conn["sourceOptionIdentifier"] = handle
        elif src_type == "INPUT":
            conn["sourceOutletIdentifier"] = handle
        elif handle and str(handle).lower() not in {"out", "fallback"}:
            conn["sourceOutletIdentifier"] = handle
        connections.append(conn)
    ui = {k: v for k, v in existing_ui.items() if k != "positions"}
    ui["kind"] = existing_ui.get("kind") or "e2e"
    ui["positions"] = positions
    dsl = {
        "identifier": str(rec.id),
        "title": name or rec.name,
        "description": description or rec.description,
        "nodes": nodes,
        "connections": connections,
        "ui": ui,
    }
    return save_draft(rec.id, dsl)


def _run_secrets() -> dict[str, str]:
    from src.platform.graphs.expressions import workflow_secrets

    return workflow_secrets()


async def _start_interpreter_async(run: GraphRun, plan: dict[str, Any]) -> str:
    import os

    from temporalio.client import Client

    from src.orchestrator.workflows.workflow_interpreter import WorkflowInterpreter

    workflow_id = f"graph-run-{run.id}"
    host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    queue = os.environ.get("TEMPORAL_TASK_QUEUE", "agent-task-queue")
    client = await Client.connect(host)
    await client.start_workflow(
        WorkflowInterpreter.run,
        args=[{
                "run_id": str(run.id),
                "plan": plan,
                "input": run.input,
                "secrets": _run_secrets(),
            }],
        id=workflow_id,
        task_queue=queue,
    )
    return workflow_id


def _start_interpreter(run: GraphRun, plan: dict[str, Any]) -> str:
    import asyncio

    return asyncio.run(_start_interpreter_async(run, plan))


async def _signal_temporal_async(workflow_id: str, signal: str, payload: dict[str, Any]) -> None:
    import os

    from temporalio.client import Client

    client = await Client.connect(os.environ.get("TEMPORAL_HOST", "localhost:7233"))
    handle = client.get_workflow_handle(workflow_id)
    if signal == "resume":
        try:
            await handle.execute_update("resume", payload)
            return
        except Exception:
            signal = "resume"
    decision = "request_change" if signal in {"changes", "request_changes"} else signal
    await handle.signal("review_decision", {**payload, "decision": decision})


async def _query_temporal_async(workflow_id: str) -> dict[str, Any]:
    import os

    from temporalio.client import Client

    client = await Client.connect(os.environ.get("TEMPORAL_HOST", "localhost:7233"))
    handle = client.get_workflow_handle(workflow_id)
    return await handle.query("getRunState")


async def _cancel_temporal_async(workflow_id: str) -> None:
    import os

    from temporalio.client import Client

    client = await Client.connect(os.environ.get("TEMPORAL_HOST", "localhost:7233"))
    await client.get_workflow_handle(workflow_id).cancel()


def _signal_temporal(workflow_id: str, signal: str, payload: dict[str, Any]) -> None:
    import asyncio

    asyncio.run(_signal_temporal_async(workflow_id, signal, payload))


def _query_temporal(workflow_id: str) -> dict[str, Any]:
    import asyncio

    return asyncio.run(_query_temporal_async(workflow_id))
