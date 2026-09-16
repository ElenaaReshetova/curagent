"""Skills PostgreSQL repository — SoT for catalog + versioned packages."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.platform.db.bootstrap import ensure_default_workspace
from src.platform.db.models.skills import SkillRow, SkillVersionRow
from src.platform.db.settings import DEFAULT_WORKSPACE_ID
from src.platform.skills.models import (
    SkillBindingRef,
    SkillFile,
    SkillRecord,
    SkillTestCase,
    SkillVersion,
)


def _as_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _looks_uuid(value: str) -> bool:
    try:
        UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def row_to_record(row: SkillRow) -> SkillRecord:
    bindings = [SkillBindingRef.model_validate(x) for x in (row.bindings_json or [])]
    return SkillRecord(
        id=row.id,
        workspace_id=str(row.workspace_id),
        key=row.key,
        name=row.name,
        description=row.description or "",
        skill_type=row.skill_type,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
        owner_team=row.owner_team,
        parent_skill_id=row.parent_skill_id,
        parent_version_id=row.parent_version_id,
        current_published_version_id=row.current_published_version_id,
        current_draft_version_id=row.current_draft_version_id,
        runs_30d=row.runs_30d,
        success_rate=row.success_rate,
        bindings=bindings,
        created_at=row.created_at,
        updated_at=row.updated_at,
        revision=row.revision,
    )


def row_to_version(row: SkillVersionRow) -> SkillVersion:
    files = [SkillFile.model_validate(x) for x in (row.files_json or [])]
    tests = [SkillTestCase.model_validate(x) for x in (row.test_cases_json or [])]
    return SkillVersion(
        id=row.id,
        skill_id=row.skill_id,
        semantic_version=row.semantic_version,
        status=row.status,  # type: ignore[arg-type]
        skill_markdown=row.skill_markdown or "",
        manifest=dict(row.manifest_json or {}),
        package_checksum=row.package_checksum or "",
        runtime_type=row.runtime_type or "qwen-code-cli",
        interface_key=row.interface_key or "",
        input_contract_key=row.input_contract_key or "",
        output_contract_key=row.output_contract_key or "",
        allowed_capabilities=list(row.allowed_capabilities_json or []),
        files=files,
        test_cases=tests,
        validation_status=row.validation_status,  # type: ignore[arg-type]
        validation_report=dict(row.validation_report_json or {}),
        revision=row.revision,
        created_at=row.created_at,
        published_at=row.published_at,
        updated_at=row.updated_at,
    )


def version_to_row_fields(ver: SkillVersion) -> dict[str, Any]:
    return {
        "id": ver.id,
        "skill_id": ver.skill_id,
        "semantic_version": ver.semantic_version,
        "status": ver.status,
        "skill_markdown": ver.skill_markdown,
        "manifest_json": ver.manifest,
        "package_checksum": ver.package_checksum,
        "runtime_type": ver.runtime_type,
        "interface_key": ver.interface_key,
        "input_contract_key": ver.input_contract_key,
        "output_contract_key": ver.output_contract_key,
        "allowed_capabilities_json": list(ver.allowed_capabilities),
        "files_json": [f.model_dump(mode="json") for f in ver.files],
        "test_cases_json": [t.model_dump(mode="json") for t in ver.test_cases],
        "validation_status": ver.validation_status,
        "validation_report_json": ver.validation_report,
        "revision": ver.revision,
        "created_at": ver.created_at,
        "updated_at": ver.updated_at,
        "published_at": ver.published_at,
    }


class SkillsRepository:
    def __init__(self, session: Session):
        self.session = session

    def ensure_workspace(self) -> UUID:
        return ensure_default_workspace(self.session).id

    def list_records(self) -> list[SkillRecord]:
        rows = self.session.scalars(select(SkillRow).order_by(SkillRow.name)).all()
        return [row_to_record(r) for r in rows]

    def list_versions(self, skill_id: str | None = None) -> list[SkillVersion]:
        stmt = select(SkillVersionRow)
        if skill_id:
            stmt = stmt.where(SkillVersionRow.skill_id == _as_uuid(skill_id))
        rows = self.session.scalars(stmt).all()
        return [row_to_version(r) for r in rows]

    def get_record(self, skill_id: str) -> SkillRecord | None:
        try:
            uid = _as_uuid(skill_id)
            row = self.session.get(SkillRow, uid)
            if row:
                return row_to_record(row)
        except (ValueError, TypeError):
            pass
        row = self.session.scalar(select(SkillRow).where(SkillRow.key == skill_id))
        return row_to_record(row) if row else None

    def get_version(self, version_id: str) -> SkillVersion | None:
        row = self.session.get(SkillVersionRow, _as_uuid(version_id))
        return row_to_version(row) if row else None

    def count_skills(self) -> int:
        from sqlalchemy import func

        return int(self.session.scalar(select(func.count()).select_from(SkillRow)) or 0)

    def _workspace_uuid(self, workspace_id: str) -> UUID:
        ws_id = self.ensure_workspace()
        if workspace_id in ("default", DEFAULT_WORKSPACE_ID):
            return ws_id
        if _looks_uuid(workspace_id):
            return _as_uuid(workspace_id)
        return ws_id

    def insert_skill_with_version(self, rec: SkillRecord, ver: SkillVersion) -> None:
        self.session.add(
            SkillRow(
                id=rec.id,
                workspace_id=self._workspace_uuid(rec.workspace_id),
                key=rec.key,
                name=rec.name,
                description=rec.description,
                skill_type=rec.skill_type,
                status=rec.status,
                owner_team=rec.owner_team,
                parent_skill_id=rec.parent_skill_id,
                parent_version_id=rec.parent_version_id,
                current_published_version_id=rec.current_published_version_id,
                current_draft_version_id=rec.current_draft_version_id,
                runs_30d=rec.runs_30d,
                success_rate=rec.success_rate,
                bindings_json=[b.model_dump(mode="json") for b in rec.bindings],
                revision=rec.revision,
                created_at=rec.created_at,
                updated_at=rec.updated_at,
            )
        )
        self.session.flush()
        self._insert_version(ver)

    def _insert_version(self, ver: SkillVersion) -> SkillVersionRow:
        row = SkillVersionRow(**version_to_row_fields(ver))
        self.session.add(row)
        self.session.flush()
        return row

    def save_version(self, ver: SkillVersion) -> SkillVersion:
        row = self.session.get(SkillVersionRow, ver.id)
        if not row:
            raise KeyError("Version not found")
        for key, value in version_to_row_fields(ver).items():
            if key in ("id", "skill_id", "created_at"):
                continue
            setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        skill = self.session.get(SkillRow, ver.skill_id)
        if skill:
            skill.updated_at = datetime.utcnow()
        self.session.flush()
        return row_to_version(row)

    def save_record(self, rec: SkillRecord) -> SkillRecord:
        row = self.session.get(SkillRow, rec.id)
        if not row:
            raise KeyError("Skill not found")
        row.key = rec.key
        row.name = rec.name
        row.description = rec.description
        row.skill_type = rec.skill_type
        row.status = rec.status
        row.owner_team = rec.owner_team
        row.parent_skill_id = rec.parent_skill_id
        row.parent_version_id = rec.parent_version_id
        row.current_published_version_id = rec.current_published_version_id
        row.current_draft_version_id = rec.current_draft_version_id
        row.runs_30d = rec.runs_30d
        row.success_rate = rec.success_rate
        row.bindings_json = [b.model_dump(mode="json") for b in rec.bindings]
        row.revision = rec.revision
        row.updated_at = datetime.utcnow()
        self.session.flush()
        return row_to_record(row)

    def publish_version(self, skill_id: UUID, version_id: UUID) -> None:
        versions = self.session.scalars(
            select(SkillVersionRow).where(SkillVersionRow.skill_id == skill_id)
        ).all()
        now = datetime.utcnow()
        target: SkillVersionRow | None = None
        for v in versions:
            if v.id == version_id:
                target = v
                v.status = "PUBLISHED"
                v.published_at = now
            elif v.status == "PUBLISHED":
                v.status = "DEPRECATED"
        if not target:
            raise KeyError("Version not found")
        skill = self.session.get(SkillRow, skill_id)
        if not skill:
            raise KeyError("Skill not found")
        skill.current_published_version_id = version_id
        skill.status = "active"
        skill.updated_at = now

    def add_draft(self, skill_id: UUID, draft: SkillVersion) -> None:
        self._insert_version(draft)
        skill = self.session.get(SkillRow, skill_id)
        if not skill:
            raise KeyError("Skill not found")
        skill.current_draft_version_id = draft.id
        skill.updated_at = datetime.utcnow()

    def delete_skill(self, skill_id: str | UUID) -> None:
        sid = _as_uuid(skill_id)
        row = self.session.get(SkillRow, sid)
        if not row:
            return
        # Clear version pointers before removing versions (no FK, but keeps rows consistent).
        row.current_published_version_id = None
        row.current_draft_version_id = None
        self.session.flush()
        versions = self.session.scalars(
            select(SkillVersionRow).where(SkillVersionRow.skill_id == sid)
        ).all()
        for ver in versions:
            self.session.delete(ver)
        self.session.delete(row)
        self.session.flush()

    def seed_if_empty(self, records: list[SkillRecord], versions: list[SkillVersion]) -> bool:
        if self.count_skills() > 0:
            return False
        self.ensure_workspace()
        by_id = {str(r.id): r for r in records}
        for rec in records:
            self.session.add(
                SkillRow(
                    id=rec.id,
                    workspace_id=self._workspace_uuid(rec.workspace_id),
                    key=rec.key,
                    name=rec.name,
                    description=rec.description,
                    skill_type=rec.skill_type,
                    status=rec.status,
                    owner_team=rec.owner_team,
                    parent_skill_id=rec.parent_skill_id,
                    parent_version_id=rec.parent_version_id,
                    current_published_version_id=None,
                    current_draft_version_id=None,
                    runs_30d=rec.runs_30d,
                    success_rate=rec.success_rate,
                    bindings_json=[b.model_dump(mode="json") for b in rec.bindings],
                    revision=rec.revision,
                    created_at=rec.created_at,
                    updated_at=rec.updated_at,
                )
            )
        self.session.flush()
        for ver in versions:
            if str(ver.skill_id) not in by_id:
                continue
            self._insert_version(ver)
        self.session.flush()
        for rec in records:
            skill = self.session.get(SkillRow, rec.id)
            if not skill:
                continue
            skill.current_published_version_id = rec.current_published_version_id
            skill.current_draft_version_id = rec.current_draft_version_id
        return True
