"""PostgreSQL repository for workflows (scenarios), graph topology, and executions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4, uuid5

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from src.platform.db.bootstrap import ensure_default_workspace
from src.platform.db.models.workflows import (
    ExecutionRow,
    ExecutionStepRow,
    NodeTypeRow,
    TemporalActivityRow,
    WorkflowConnectionRow,
    WorkflowRow,
    WorkflowStageRow,
    WorkflowVersionRow,
)
from src.platform.db.settings import DEFAULT_WORKSPACE_ID
from src.platform.graphs.activity_catalog import DEFAULT_BINDINGS, NodeWorkerBinding
from src.platform.graphs.models import GraphRecord, GraphRun, GraphVersion
from src.platform.graphs.workflow_dsl import _CANVAS_TYPE, _CANVAS_TO_CONFIG

NODE_NS = UUID("b2c3d4e5-6f70-4890-bcde-f01234567890")



def _as_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _looks_uuid(value: str) -> bool:
    try:
        UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def canvas_type_for_node(node: dict[str, Any]) -> str:
    cfg = node.get("config") if isinstance(node.get("config"), dict) else {}
    port_type = str(cfg.get("type") or "").upper()
    if port_type in _CANVAS_TYPE:
        return _CANVAS_TYPE[port_type]
    raw = str(node.get("type") or "").lower()
    if raw in _CANVAS_TO_CONFIG:
        return raw
    return "ai_agent" if port_type else "trigger"


def _xy(pos: Any) -> tuple[float | None, float | None]:
    if not isinstance(pos, dict):
        return None, None
    x = pos.get("x", pos.get("left"))
    y = pos.get("y", pos.get("top"))
    try:
        return (float(x) if x is not None else None, float(y) if y is not None else None)
    except (TypeError, ValueError):
        return None, None


def row_to_record(row: WorkflowRow) -> GraphRecord:
    return GraphRecord(
        id=row.id,
        workspace_id=str(row.workspace_id) if str(row.workspace_id) != DEFAULT_WORKSPACE_ID else "default",
        key=row.key,
        name=row.name,
        description=row.description or "",
        kind=row.kind,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
        launched=bool(row.launched),
        owner_team=row.owner_team,
        current_published_version_id=row.current_published_version_id,
        current_draft_version_id=row.current_draft_version_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        revision=row.revision,
    )


def row_to_version(row: WorkflowVersionRow) -> GraphVersion:
    return GraphVersion(
        id=row.id,
        graph_id=row.workflow_id,
        semantic_version=row.semantic_version,
        status=row.status,  # type: ignore[arg-type]
        dsl=dict(row.dsl or {}),
        temporal_plan=dict(row.plan) if row.plan else None,
        validation_status=row.validation_status,  # type: ignore[arg-type]
        validation_report=dict(row.validation_report or {}),
        revision=row.revision,
        created_at=row.created_at,
        published_at=row.published_at,
        updated_at=row.updated_at,
    )


def row_to_run(row: ExecutionRow) -> GraphRun:
    return GraphRun(
        id=row.id,
        graph_id=row.workflow_id,
        version_id=row.workflow_version_id,
        status=row.status,  # type: ignore[arg-type]
        input=dict(row.input_json or {}),
        output=dict(row.output_json or {}),
        state=dict(row.state_json or {}),
        events=list(row.events_json or []),
        temporal_workflow_id=row.temporal_workflow_id,
        parent_execution_id=row.parent_execution_id,
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class WorkflowsRepository:
    def __init__(self, session: Session):
        self.session = session

    def ensure_workspace(self) -> UUID:
        return ensure_default_workspace(self.session).id

    def _workspace_uuid(self, workspace_id: str) -> UUID:
        ws_id = self.ensure_workspace()
        if workspace_id in ("default", DEFAULT_WORKSPACE_ID, "", None):  # type: ignore[comparison-overlap]
            return ws_id
        if _looks_uuid(str(workspace_id)):
            return _as_uuid(workspace_id)
        return ws_id

    def ensure_node_types(self) -> dict[str, NodeTypeRow]:
        """Idempotent catalog seed: node_types.key → temporal_activities.worker."""
        from src.platform.graphs.registry import NODE_REGISTRY

        existing = {r.key: r for r in self.session.scalars(select(NodeTypeRow)).all()}
        activities = {
            a.node_type_id: a
            for a in self.session.scalars(select(TemporalActivityRow)).all()
        }
        now = datetime.utcnow()
        by_key_binding = {b.key: b for b in DEFAULT_BINDINGS}

        for key, entry in NODE_REGISTRY.items():
            binding = by_key_binding.get(key)
            family = binding.family if binding else "Activity"
            port_type = binding.port_type if binding else _CANVAS_TO_CONFIG.get(key, key.upper())
            row = existing.get(key)
            if row is None:
                row = NodeTypeRow(
                    id=uuid5(NODE_NS, f"node-type:{key}"),
                    key=key,
                    type=family,
                    subtype=port_type,
                    description=entry.title,
                    dsl={
                        "canvas_type": key,
                        "port_type": port_type,
                        "worker": binding.worker if binding else "",
                        "configSchema": entry.configSchema,
                        "ports": {
                            pk: [p.model_dump(mode="json") if hasattr(p, "model_dump") else p for p in (pv or [])]
                            for pk, pv in (entry.ports or {}).items()
                        },
                    },
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(row)
                existing[key] = row
                self.session.flush()
            else:
                row.type = family
                row.subtype = port_type
                dsl = dict(row.dsl or {})
                dsl["canvas_type"] = key
                dsl["port_type"] = port_type
                if binding:
                    dsl["worker"] = binding.worker
                row.dsl = dsl
                row.updated_at = now

            worker = binding.worker if binding else ""
            if not worker:
                continue
            act = activities.get(row.id)
            if act is None:
                act = TemporalActivityRow(
                    id=uuid5(NODE_NS, f"activity:{key}:{worker}"),
                    node_type_id=row.id,
                    worker=worker,
                    activity_name=worker,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(act)
                activities[row.id] = act
            elif not act.worker or act.worker == "default":
                act.worker = worker
                act.activity_name = worker or act.activity_name
                act.updated_at = now

        self.session.flush()
        return {r.key: r for r in self.session.scalars(select(NodeTypeRow)).all()}

    def list_worker_bindings(self) -> list[NodeWorkerBinding]:
        self.ensure_node_types()
        types = {r.id: r for r in self.session.scalars(select(NodeTypeRow)).all()}
        acts = list(self.session.scalars(select(TemporalActivityRow)).all())
        by_type: dict[UUID, TemporalActivityRow] = {}
        for a in acts:
            by_type[a.node_type_id] = a
        out: list[NodeWorkerBinding] = []
        for row in types.values():
            act = by_type.get(row.id)
            worker = (act.worker if act else "") or (act.activity_name if act else "") or str((row.dsl or {}).get("worker") or "")
            family = row.type or "Activity"
            out.append(
                NodeWorkerBinding(
                    key=row.key,
                    family=family,
                    port_type=row.subtype or "",
                    worker=worker,
                    wait_for_signal=family == "Input" or worker == "human_review",
                )
            )
        return out

    def count_workflows(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(WorkflowRow)) or 0)

    def list_records(self) -> list[GraphRecord]:
        rows = self.session.scalars(select(WorkflowRow).order_by(WorkflowRow.name)).all()
        return [row_to_record(r) for r in rows]

    def get_record(self, workflow_id: str | UUID) -> GraphRecord | None:
        try:
            row = self.session.get(WorkflowRow, _as_uuid(workflow_id))
            if row:
                return row_to_record(row)
        except (ValueError, TypeError):
            pass
        row = self.session.scalar(select(WorkflowRow).where(WorkflowRow.key == str(workflow_id)))
        return row_to_record(row) if row else None

    def get_record_by_key(self, key: str) -> GraphRecord | None:
        row = self.session.scalar(select(WorkflowRow).where(WorkflowRow.key == key))
        if row:
            return row_to_record(row)
        rows = self.session.scalars(select(WorkflowRow)).all()
        for r in rows:
            if r.key.endswith(f":{key}") or key.endswith(r.key):
                return row_to_record(r)
        return None

    def list_versions(self, workflow_id: str | UUID | None = None) -> list[GraphVersion]:
        stmt = select(WorkflowVersionRow)
        if workflow_id is not None:
            stmt = stmt.where(WorkflowVersionRow.workflow_id == _as_uuid(workflow_id))
        rows = self.session.scalars(stmt).all()
        return [row_to_version(r) for r in rows]

    def get_version(self, version_id: str | UUID) -> GraphVersion | None:
        row = self.session.get(WorkflowVersionRow, _as_uuid(version_id))
        return row_to_version(row) if row else None

    def list_runs(self) -> list[GraphRun]:
        rows = self.session.scalars(select(ExecutionRow).order_by(ExecutionRow.created_at)).all()
        return [row_to_run(r) for r in rows]

    def get_run(self, run_id: str | UUID) -> GraphRun | None:
        row = self.session.get(ExecutionRow, _as_uuid(run_id))
        return row_to_run(row) if row else None

    def upsert_record(self, rec: GraphRecord) -> GraphRecord:
        self.ensure_workspace()
        self.ensure_node_types()
        row = self.session.get(WorkflowRow, rec.id)
        now = datetime.utcnow()
        fields = dict(
            workspace_id=self._workspace_uuid(rec.workspace_id),
            key=rec.key,
            name=rec.name,
            description=rec.description or "",
            kind=rec.kind,
            segment_id="default",
            status=rec.status,
            launched=bool(rec.launched),
            owner_team=rec.owner_team,
            current_published_version_id=rec.current_published_version_id,
            current_draft_version_id=rec.current_draft_version_id,
            revision=rec.revision,
            updated_at=rec.updated_at or now,
        )
        if row is None:
            row = WorkflowRow(
                id=rec.id,
                version=1,
                created_by="",
                updated_by="",
                created_at=rec.created_at or now,
                **fields,
            )
            self.session.add(row)
        else:
            for key, value in fields.items():
                setattr(row, key, value)
        self.session.flush()
        return row_to_record(row)

    def update_record_if_revision(self, rec: GraphRecord, expected_revision: int) -> GraphRecord:
        """Compare-and-swap workflow metadata to prevent lost updates."""
        now = datetime.utcnow()
        result = self.session.execute(
            update(WorkflowRow)
            .where(WorkflowRow.id == rec.id, WorkflowRow.revision == expected_revision)
            .values(
                key=rec.key,
                name=rec.name,
                description=rec.description or "",
                kind=rec.kind,
                status=rec.status,
                launched=bool(rec.launched),
                owner_team=rec.owner_team,
                current_published_version_id=rec.current_published_version_id,
                current_draft_version_id=rec.current_draft_version_id,
                revision=rec.revision,
                updated_at=rec.updated_at or now,
            )
        )
        if result.rowcount != 1:
            raise ValueError(f"revision conflict: expected {expected_revision}")
        self.session.flush()
        row = self.session.get(WorkflowRow, rec.id)
        if row is None:
            raise KeyError(rec.id)
        return row_to_record(row)

    def upsert_version(self, ver: GraphVersion) -> GraphVersion:
        self.ensure_node_types()
        row = self.session.get(WorkflowVersionRow, ver.id)
        now = datetime.utcnow()
        version_number = 1
        if row is None:
            max_n = self.session.scalar(
                select(func.max(WorkflowVersionRow.version_number)).where(
                    WorkflowVersionRow.workflow_id == ver.graph_id
                )
            )
            version_number = int(max_n or 0) + 1
        else:
            version_number = row.version_number
        fields = dict(
            workflow_id=ver.graph_id,
            semantic_version=ver.semantic_version,
            status=ver.status,
            dsl=dict(ver.dsl or {}),
            plan=dict(ver.temporal_plan) if ver.temporal_plan else None,
            validation_status=ver.validation_status,
            validation_report=dict(ver.validation_report or {}),
            revision=ver.revision,
            updated_at=ver.updated_at or now,
            published_at=ver.published_at,
        )
        if row is None:
            row = WorkflowVersionRow(
                id=ver.id,
                version_number=version_number,
                created_at=ver.created_at or now,
                **fields,
            )
            self.session.add(row)
            self.session.flush()
        else:
            for key, value in fields.items():
                setattr(row, key, value)
            self.session.flush()
        self._sync_topology(row)
        wf = self.session.get(WorkflowRow, ver.graph_id)
        if wf:
            wf.version = version_number
            wf.updated_at = now
        self.session.flush()
        return row_to_version(row)

    def upsert_run(self, run: GraphRun) -> GraphRun:
        row = self.session.get(ExecutionRow, run.id)
        now = datetime.utcnow()
        ver = self.session.get(WorkflowVersionRow, run.version_id)
        version_number = ver.version_number if ver else 1
        plan = (run.state or {}).get("plan") if isinstance(run.state, dict) else None
        if not plan and ver and ver.plan:
            plan = ver.plan
        mode = "test" if str((run.state or {}).get("source") or "").upper() == "TEST" else "live"
        if str((run.state or {}).get("engine") or "") == "local":
            mode = "test"
        temporal_id = run.temporal_workflow_id or None
        fields = dict(
            workflow_id=run.graph_id,
            workflow_version_id=run.version_id,
            version=version_number,
            status=run.status,
            mode=mode,
            started_by="",
            started_at=run.created_at,
            ended_by="",
            ended_at=now if run.status in {"completed", "failed", "cancelled"} else None,
            iteration=1,
            request_id="",
            input_json=dict(run.input or {}),
            output_json=dict(run.output or {}),
            state_json=dict(run.state or {}),
            plan=dict(plan) if isinstance(plan, dict) else None,
            dsl_snapshot=dict(ver.dsl) if ver and ver.dsl else None,
            events_json=list(run.events or []),
            temporal_workflow_id=temporal_id,
            parent_execution_id=run.parent_execution_id,
            error=run.error,
            updated_at=run.updated_at or now,
        )
        if row is None:
            row = ExecutionRow(id=run.id, created_at=run.created_at or now, **fields)
            self.session.add(row)
            self.session.flush()
        else:
            for key, value in fields.items():
                setattr(row, key, value)
            self.session.flush()
        self._sync_steps(row, plan if isinstance(plan, dict) else {}, run)
        self.session.flush()
        return row_to_run(row)

    def _sync_topology(self, version: WorkflowVersionRow) -> None:
        dsl = version.dsl if isinstance(version.dsl, dict) else {}
        nodes = dsl.get("nodes") if isinstance(dsl.get("nodes"), list) else []
        connections = dsl.get("connections") if isinstance(dsl.get("connections"), list) else []
        ui = dsl.get("ui") if isinstance(dsl.get("ui"), dict) else {}
        positions = ui.get("positions") if isinstance(ui.get("positions"), dict) else {}
        catalog = {r.key: r for r in self.session.scalars(select(NodeTypeRow)).all()}

        self.session.execute(
            delete(WorkflowConnectionRow).where(WorkflowConnectionRow.workflow_version_id == version.id)
        )
        self.session.execute(delete(WorkflowStageRow).where(WorkflowStageRow.workflow_version_id == version.id))
        self.session.flush()

        by_identifier: dict[str, WorkflowStageRow] = {}
        now = datetime.utcnow()
        for idx, raw in enumerate(nodes):
            if not isinstance(raw, dict):
                continue
            identifier = str(raw.get("identifier") or f"node-{idx}")
            canvas = canvas_type_for_node(raw)
            node_type = catalog.get(canvas)
            pos_x, pos_y = _xy(positions.get(identifier))
            stage = WorkflowStageRow(
                id=uuid5(version.id, f"stage:{identifier}"),
                workflow_id=version.workflow_id,
                workflow_version_id=version.id,
                node_type_id=node_type.id if node_type else None,
                identifier=identifier,
                name=str(raw.get("title") or identifier),
                description=str(raw.get("description") or ""),
                pos_x=pos_x,
                pos_y=pos_y,
                dsl=dict(raw),
                sort_order=idx,
                created_at=now,
                updated_at=now,
            )
            self.session.add(stage)
            by_identifier[identifier] = stage
        self.session.flush()

        for raw in connections:
            if not isinstance(raw, dict):
                continue
            src = str(raw.get("sourceIdentifier") or "")
            tgt = str(raw.get("targetIdentifier") or "")
            source = by_identifier.get(src)
            target = by_identifier.get(tgt)
            if not source or not target:
                continue
            outlet = raw.get("sourceOutletIdentifier")
            option = raw.get("sourceOptionIdentifier")
            conn_id = uuid5(version.id, f"conn:{src}:{tgt}:{outlet or option or ''}")
            self.session.add(
                WorkflowConnectionRow(
                    id=conn_id,
                    workflow_id=version.workflow_id,
                    workflow_version_id=version.id,
                    source_stage_id=source.id,
                    target_stage_id=target.id,
                    source_outlet=str(outlet) if outlet else None,
                    source_option=str(option) if option else None,
                    fallback=bool(raw.get("fallback")),
                    dsl=dict(raw),
                    created_at=now,
                    updated_at=now,
                )
            )
        self.session.flush()

    def _sync_steps(self, execution: ExecutionRow, plan: dict[str, Any], run: GraphRun) -> None:
        steps = plan.get("steps") if isinstance(plan.get("steps"), dict) else {}
        order = list(plan.get("step_order") or steps.keys())
        current = str((run.state or {}).get("current_node_id") or (run.state or {}).get("cursor") or "")
        outputs = (run.state or {}).get("outputs") if isinstance((run.state or {}).get("outputs"), dict) else {}
        existing = {
            r.node_identifier: r
            for r in self.session.scalars(
                select(ExecutionStepRow).where(ExecutionStepRow.execution_id == execution.id)
            ).all()
        }
        stages = {
            s.identifier: s
            for s in self.session.scalars(
                select(WorkflowStageRow).where(WorkflowStageRow.workflow_version_id == execution.workflow_version_id)
            ).all()
        }
        now = datetime.utcnow()
        seen: set[str] = set()
        reached_current = not current
        for identifier in order:
            spec = steps.get(identifier) if isinstance(steps.get(identifier), dict) else {}
            kind = str(spec.get("kind") or "activity")
            if identifier == current:
                step_status = "waiting" if run.status == "waiting" else "running"
                reached_current = True
            elif not reached_current or run.status in {"completed"}:
                step_status = "completed" if run.status != "pending" else "pending"
            elif run.status == "failed" and not reached_current:
                step_status = "completed"
            else:
                step_status = "pending"
            if run.status == "failed" and identifier == current:
                step_status = "failed"
            if run.status == "cancelled":
                step_status = "skipped" if identifier != current else "cancelled"
            if run.status == "completed":
                step_status = "completed"
            row = existing.get(identifier)
            payload = dict(
                stage_id=stages[identifier].id if identifier in stages else None,
                step_kind=kind,
                status=step_status,
                input_json=dict(spec.get("input") or {}),
                output_json=dict(outputs.get(identifier) or {}),
                error=run.error if step_status == "failed" else None,
                started_at=(existing.get(identifier).started_at if existing.get(identifier) else None)
                or (now if step_status in {"running", "waiting", "completed", "failed", "cancelled"} else None),
                ended_at=(
                    now if step_status in {"completed", "failed", "cancelled", "skipped"}
                    else None
                ),
                updated_at=now,
            )
            if row is None:
                row = ExecutionStepRow(
                    id=uuid4(),
                    execution_id=execution.id,
                    node_identifier=identifier,
                    created_at=now,
                    **payload,
                )
                self.session.add(row)
            else:
                for key, value in payload.items():
                    setattr(row, key, value)
            seen.add(identifier)
        for identifier, row in existing.items():
            if identifier not in seen:
                self.session.delete(row)

    def delete_record(self, workflow_id: str | UUID) -> None:
        row = self.session.get(WorkflowRow, _as_uuid(workflow_id))
        if not row:
            return
        row.current_published_version_id = None
        row.current_draft_version_id = None
        self.session.flush()
        executions = self.session.scalars(
            select(ExecutionRow).where(ExecutionRow.workflow_id == row.id)
        ).all()
        if executions:
            raise ValueError("cannot delete workflow with execution history")
        self.session.delete(row)
        self.session.flush()
