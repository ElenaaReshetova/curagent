"""Skills relational + JSONB package persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.platform.db.base import Base, JsonDict


class SkillRow(Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_skills_workspace_key"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    skill_type: Mapped[str] = mapped_column(String(32), nullable=False, default="TEAM")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    owner_team: Mapped[str] = mapped_column(String(255), nullable=False, default="Platform")
    parent_skill_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("skills.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_version_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    current_published_version_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    current_draft_version_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    runs_30d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bindings_json: Mapped[list[Any]] = mapped_column(JsonDict, nullable=False, default=list)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list[SkillVersionRow]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )


class SkillVersionRow(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_id", "semantic_version", name="uq_skill_versions_semver"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    skill_id: Mapped[UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    semantic_version: Mapped[str] = mapped_column(String(32), nullable=False, default="0.1.0")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    skill_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JsonDict, nullable=False, default=dict)
    package_checksum: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    runtime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="qwen-code-cli")
    interface_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    input_contract_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    output_contract_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    allowed_capabilities_json: Mapped[list[Any]] = mapped_column(JsonDict, nullable=False, default=list)
    files_json: Mapped[list[Any]] = mapped_column(JsonDict, nullable=False, default=list)
    test_cases_json: Mapped[list[Any]] = mapped_column(JsonDict, nullable=False, default=list)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    validation_report_json: Mapped[dict[str, Any]] = mapped_column(JsonDict, nullable=False, default=dict)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

    skill: Mapped[SkillRow] = relationship(back_populates="versions")
