"""Shared publish transition helpers for versioned entity stores."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


def apply_json_publish(
    versions: list[Any],
    records: list[Any],
    *,
    parent_id: str,
    version_id: str,
    parent_attr: str,
    now: datetime | None = None,
    on_published: Callable[[Any], None] | None = None,
) -> tuple[Any, Any]:
    """Deprecate sibling PUBLISHED versions and mark target + parent record active.

    Mutates ``versions`` / ``records`` in place. Returns (published_version, record).
    """
    stamp = now or datetime.utcnow()
    published = None
    for ver in versions:
        if str(getattr(ver, parent_attr)) == parent_id and ver.status == "PUBLISHED":
            ver.status = "DEPRECATED"
        if str(ver.id) == version_id:
            ver.status = "PUBLISHED"
            ver.published_at = stamp
            if on_published:
                on_published(ver)
            published = ver
    if published is None:
        raise KeyError("Version not found")
    record = None
    for rec in records:
        if str(rec.id) == parent_id:
            rec.current_published_version_id = published.id
            rec.status = "active"
            rec.updated_at = stamp
            record = rec
            break
    if record is None:
        raise KeyError("Record not found")
    return published, record
