"""Publisher: deliver approved artifacts to target systems via HTTP callback."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import httpx

from src.orchestrator.models import ArtifactDraft, NormalizedTaskSpec, PublicationReceipt
from src.orchestrator.validators import checksum

logger = logging.getLogger(__name__)


async def publish_via_callback(
    task: NormalizedTaskSpec,
    artifact: ArtifactDraft,
) -> PublicationReceipt:
    """
    Publish artifact content to the source gateway callback URL.

    Gateways (chat/slack/jira) already expose ``/api/callback`` endpoints.
    """
    if not task.callback_url:
        raise ValueError(f"No callback_url for task {task.task_id}")

    payload = {
        "task_id": task.task_id,
        "source_id": task.source_id,
        "message": artifact.content,
        "artifact_type": artifact.type.value,
        "artifact_id": artifact.artifact_id,
        "artifact_version": artifact.version,
        "skill": artifact.skill,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(task.callback_url, json=payload)
        if not resp.is_success:
            raise RuntimeError(
                f"Delivery failed: {resp.status_code} {resp.text[:500]}"
            )

    now = datetime.now(timezone.utc).isoformat()
    return PublicationReceipt(
        receipt_id=str(uuid.uuid4()),
        task_id=task.task_id,
        artifact_id=artifact.artifact_id,
        artifact_version=artifact.version,
        target=task.source,
        external_id=f"{task.source_id}:v{artifact.version}",
        url=task.callback_url,
        content_checksum=checksum(artifact.content),
        published_at=now,
    )


async def verify_publication(receipt: PublicationReceipt) -> bool:
    """Post-publish verify: receipt must have checksum and external_id."""
    return bool(receipt.receipt_id and receipt.content_checksum and receipt.external_id)
