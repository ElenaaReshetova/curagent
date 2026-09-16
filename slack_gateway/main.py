"""Slack Gateway: polls Slack for tasks assigned to bot, produces to Kafka, callback for agent results."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from aiokafka import AIOKafkaProducer
from fastapi import FastAPI
from pydantic import BaseModel, Field
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Config
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TASKS_TOPIC", "tasks")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_BOT_NAME = os.environ.get("SLACK_BOT_NAME", "My MCP Bot")
SLACK_CALLBACK_BASE_URL = os.environ.get("SLACK_CALLBACK_BASE_URL", "http://slack_gateway:8090")
POLL_INTERVAL_SEC = float(os.environ.get("SLACK_POLL_INTERVAL", "30"))
REACTION_COMPLETED = os.environ.get("SLACK_REACTION_COMPLETED", "white_check_mark")
SLACK_HISTORY_LIMIT = int(os.environ.get("SLACK_HISTORY_LIMIT", "200"))
DEBUG_SLACK_POLL = os.environ.get("DEBUG_SLACK_POLL", "").lower() in ("1", "true", "yes")
# Явно привязать Slack-задачи к playbook (иначе pre-scenario classify выбирает шаблон)
# auto / пусто → classify → skill map; конкретный id → pin (debug)
SLACK_WORKFLOW_TEMPLATE_ID = os.environ.get("SLACK_WORKFLOW_TEMPLATE_ID", "").strip() or None
# Pin live Slack tasks to a launched E2E (AI PDLC). auto/empty → launched graph, else classify.
SLACK_FLOW_KEY = os.environ.get("SLACK_FLOW_KEY", "").strip() or None
if DEBUG_SLACK_POLL:
    logger.setLevel(logging.DEBUG)

_producer: Optional[AIOKafkaProducer] = None
_slack_client: Optional[AsyncWebClient] = None
_bot_user_id: Optional[str] = None
_poller_task: Optional[asyncio.Task] = None

# Diagnostics
_poll_stats: dict = {"tasks_produced": 0, "last_poll_at": None, "last_error": None}
_dm_scope_warned: set = set()  # channel_ids we've already logged missing_scope for (mutable default ok for module-level)
_dispatched_source_ids: set[str] = set()  # in-process dedup when Slack reaction lags


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        last_error = None
        for attempt in range(12):  # ~60s total backoff
            try:
                _producer = AIOKafkaProducer(
                    bootstrap_servers=KAFKA_BOOTSTRAP,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                )
                await _producer.start()
                logger.info("Kafka producer connected (attempt %d)", attempt + 1)
                break
            except Exception as e:
                last_error = e
                if attempt < 11:
                    delay = min(2 ** attempt, 10)
                    logger.warning("Kafka connection attempt %d failed: %s, retry in %ds", attempt + 1, e, delay)
                    await asyncio.sleep(delay)
                else:
                    raise last_error
    return _producer


def get_slack_client() -> AsyncWebClient:
    global _slack_client
    if _slack_client is None:
        _slack_client = AsyncWebClient(token=SLACK_BOT_TOKEN)
    return _slack_client


async def get_bot_user_id() -> Optional[str]:
    """Get bot user ID for mention detection."""
    global _bot_user_id
    if _bot_user_id is not None:
        return _bot_user_id
    try:
        client = get_slack_client()
        resp = await client.auth_test()
        _bot_user_id = resp.get("user_id")
        return _bot_user_id
    except SlackApiError as e:
        logger.error("Failed to get bot user ID: %s", e)
        return None


def _message_mentions_bot(msg: dict, bot_user_id: str) -> bool:
    """Check if message mentions the bot (direct mention or in text)."""
    text = msg.get("text") or ""
    return f"<@{bot_user_id}>" in text


def _has_completed_reaction(msg: dict) -> bool:
    """Check if message already has the 'completed' reaction (from our bot or anyone)."""
    reactions = msg.get("reactions") or []
    for r in reactions:
        if r.get("name") == REACTION_COMPLETED:
            return True
    return False


async def _get_conversation_ids() -> list[tuple[str, bool]]:
    """Get (channel_id, is_dm) for channels and DMs. is_dm=True means no @mention needed."""
    result = []
    try:
        client = get_slack_client()
        resp = await client.conversations_list(
            types="public_channel,private_channel",
            limit=200,
            exclude_archived=True,
        )
        channels = resp.get("channels") or []
        for ch in channels:
            if ch.get("is_member"):
                result.append((ch["id"], False))
        resp_im = await client.conversations_list(types="im", limit=200, exclude_archived=True)
        for im in (resp_im.get("channels") or []):
            result.append((im["id"], True))
    except SlackApiError as e:
        logger.warning("Failed to list conversations: %s", e)
    return result


async def _get_channel_history(channel_id: str, limit: Optional[int] = None) -> list[dict]:
    """Get recent messages from channel (parents only; replies via conversations_replies)."""
    limit = limit or SLACK_HISTORY_LIMIT
    try:
        client = get_slack_client()
        resp = await client.conversations_history(channel=channel_id, limit=limit)
        return resp.get("messages") or []
    except SlackApiError as e:
        err_str = str(e).lower()
        is_dm = channel_id.startswith("D")
        if is_dm and "missing_scope" in err_str and "im:history" in err_str:
            if channel_id not in _dm_scope_warned:
                _dm_scope_warned.add(channel_id)
                logger.warning(
                    "DM needs im:history scope. Add in Slack App → OAuth & Permissions → Reinstall. "
                    "Use a channel with @mention for now."
                )
        else:
            logger.warning("Failed to get history for %s: %s", channel_id, e)
        return []


async def _get_thread_replies(channel_id: str, thread_ts: str) -> list[dict]:
    """Get all replies in a thread. First message is parent, rest are replies."""
    try:
        client = get_slack_client()
        resp = await client.conversations_replies(channel=channel_id, ts=thread_ts, limit=100)
        messages = resp.get("messages") or []
        # First message is parent (same ts), skip it - we already have it from history
        return [m for m in messages if m.get("ts") != thread_ts]
    except SlackApiError as e:
        logger.warning("Failed to get thread replies for %s/%s: %s", channel_id, thread_ts, e)
        return []


async def _add_reaction(channel_id: str, timestamp: str, reaction: str) -> bool:
    """Add reaction to message. Returns True on success."""
    try:
        client = get_slack_client()
        await client.reactions_add(channel=channel_id, timestamp=timestamp, name=reaction)
        return True
    except SlackApiError as e:
        resp = getattr(e, "response", None) or {}
        err = resp.get("error", "") if isinstance(resp, dict) else ""
        if err == "already_reacted":
            return True  # Idempotent
        logger.warning("Failed to add reaction: %s", e)
        return False


async def _post_thread_reply(channel_id: str, thread_ts: str, text: str) -> bool:
    """Post reply to Slack thread."""
    try:
        client = get_slack_client()
        await client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=text)
        return True
    except SlackApiError as e:
        logger.warning("Failed to post reply: %s", e)
        return False


def _is_user_message(msg: dict) -> bool:
    """Skip bot messages, edits, and other subtypes."""
    if msg.get("type") != "message":
        return False
    if msg.get("subtype"):  # bot_message, message_changed, etc.
        return False
    return True


def _is_from_bot(msg: dict, bot_user_id: Optional[str]) -> bool:
    """Check if message is from our bot (to avoid processing bot's own replies)."""
    if not bot_user_id:
        return False
    if msg.get("bot_id"):
        return True
    if msg.get("user") == bot_user_id:
        return True
    return False


def _build_task_description(main_text: str, replies: list[dict]) -> str:
    """Build full task description: main message + all comments."""
    parts = [main_text.strip()] if main_text.strip() else []
    for i, r in enumerate(replies, 1):
        t = (r.get("text") or "").strip()
        if t:
            label = f"[Комментарий {i}]" if len(replies) > 1 else "[Комментарий]"
            parts.append(f"{label}: {t}")
    return "\n\n".join(parts) if parts else ""


async def poll_slack_and_produce():
    """
    Poll Slack for messages mentioning bot (or all DMs), including thread comments.
    Takes task + ALL comments in thread — comments do NOT need to mention the bot.
    Once a task is assigned (main message or any comment mentions bot), all comments
    are included regardless of @mention. Marks main + all comments as completed.
    """
    bot_user_id = await get_bot_user_id()
    if not bot_user_id:
        logger.warning("Bot user ID not available, skipping poll")
        return

    conversations = await _get_conversation_ids()
    if not conversations:
        logger.info(
            "No conversations to poll. Add bot to channels: /invite @%s or send a DM.",
            SLACK_BOT_NAME,
        )
        return

    producer = await get_producer()
    callback_url = f"{SLACK_CALLBACK_BASE_URL.rstrip('/')}/api/callback"

    if DEBUG_SLACK_POLL:
        logger.info("Poll: %d conversations to scan", len(conversations))

    for channel_id, is_dm in conversations:
        messages = await _get_channel_history(channel_id)
        if DEBUG_SLACK_POLL and messages:
            logger.debug("Channel %s: %d messages", channel_id, len(messages))
        for msg in messages:
            if not _is_user_message(msg):
                continue

            ts = msg.get("ts", "")
            main_text = (msg.get("text") or "").strip()

            # In channels: main OR any comment must mention bot (replies checked below)
            main_mentions = _message_mentions_bot(msg, bot_user_id)

            # Get thread replies (comments) — exclude bot's own messages to avoid loops
            replies = await _get_thread_replies(channel_id, ts)
            user_replies = [
                r for r in replies
                if _is_user_message(r) and not _is_from_bot(r, bot_user_id)
            ]

            # In channels: main OR any comment must mention bot
            any_reply_mentions = any(
                _message_mentions_bot(r, bot_user_id) for r in user_replies
            )
            if not is_dm and not main_mentions and not any_reply_mentions:
                if DEBUG_SLACK_POLL:
                    logger.debug("Skip %s: no mention (main=%s, replies=%d)", ts, main_mentions, len(user_replies))
                continue

            # Build full description: main + ALL comments (no filter by @mention in comments)
            description = _build_task_description(main_text, user_replies)
            if not description:
                if DEBUG_SLACK_POLL:
                    logger.debug("Skip %s: empty description", ts)
                continue

            # Skip only if BOTH main and ALL comments have completed reaction
            main_done = _has_completed_reaction(msg)
            replies_done = all(_has_completed_reaction(r) for r in user_replies)
            if main_done and replies_done:
                if DEBUG_SLACK_POLL:
                    logger.debug("Skip %s: already completed (main_done=%s, replies_done=%s)", ts, main_done, replies_done)
                continue

            task_id = str(uuid.uuid4())
            source_id = f"slack:{channel_id}:{ts}"

            if source_id in _dispatched_source_ids:
                if DEBUG_SLACK_POLL:
                    logger.debug("Skip %s: already dispatched this session", source_id)
                continue

            # Mark completed before Kafka so failed polls do not re-enqueue the same thread
            if not await _add_reaction(channel_id, ts, REACTION_COMPLETED):
                logger.warning("Skip %s: could not mark message completed", source_id)
                continue
            for r in user_replies:
                await _add_reaction(channel_id, r.get("ts", ""), REACTION_COMPLETED)

            _dispatched_source_ids.add(source_id)

            task_payload = {
                "task_id": task_id,
                "source": "slack",
                "source_id": source_id,
                "description": description,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "callback_url": callback_url,
            }
            if SLACK_WORKFLOW_TEMPLATE_ID and SLACK_WORKFLOW_TEMPLATE_ID.lower() not in (
                "auto",
                "classify",
                "*",
            ):
                task_payload["workflow_template_id"] = SLACK_WORKFLOW_TEMPLATE_ID
            if SLACK_FLOW_KEY and SLACK_FLOW_KEY.lower() not in ("auto", "classify", "*"):
                task_payload["flow_key"] = SLACK_FLOW_KEY

            await producer.send_and_wait(KAFKA_TOPIC, task_payload)
            _poll_stats["tasks_produced"] = _poll_stats.get("tasks_produced", 0) + 1
            _poll_stats["last_poll_at"] = datetime.utcnow().isoformat() + "Z"
            logger.info(
                "Task %s produced to Kafka from Slack %s (main + %d comments)",
                task_id,
                source_id,
                len(user_replies),
            )


async def poll_loop():
    """Main polling loop."""
    if not SLACK_BOT_TOKEN:
        logger.warning("SLACK_BOT_TOKEN not set, Slack polling disabled")
        return

    logger.info("Slack poller started. Bot: %s, interval: %ss", SLACK_BOT_NAME, POLL_INTERVAL_SEC)
    while True:
        try:
            _poll_stats["last_error"] = None
            await poll_slack_and_produce()
            _poll_stats["last_poll_at"] = datetime.utcnow().isoformat() + "Z"
        except Exception as e:
            _poll_stats["last_error"] = str(e)
            logger.exception("Slack poll error: %s", e)
        await asyncio.sleep(POLL_INTERVAL_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start poller on startup, stop on shutdown."""
    global _poller_task
    if SLACK_BOT_TOKEN:
        _poller_task = asyncio.create_task(poll_loop())
    yield
    if _poller_task:
        _poller_task.cancel()
        try:
            await _poller_task
        except asyncio.CancelledError:
            pass
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None


app = FastAPI(title="Slack Gateway", lifespan=lifespan)


class CallbackRequest(BaseModel):
    task_id: str
    source_id: str  # slack:channel_id:ts
    message: str


@app.post("/api/callback")
async def callback(req: CallbackRequest):
    """
    Agent callback: receive task result and post to Slack thread.
    source_id format: slack:channel_id:thread_ts
    """
    parts = req.source_id.split(":", 2)
    if len(parts) != 3 or parts[0] != "slack":
        logger.warning("Invalid source_id for Slack callback: %s", req.source_id)
        return {"status": "ok"}

    _, channel_id, thread_ts = parts
    if await _post_thread_reply(channel_id, thread_ts, req.message):
        logger.info("Callback posted to Slack for task %s", req.task_id)
    return {"status": "ok"}


@app.get("/")
async def root():
    """Root: links to health and status."""
    return {
        "service": "Slack Gateway",
        "endpoints": {
            "health": "/health",
            "slack_status": "/api/slack/status",
        },
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "slack_configured": bool(SLACK_BOT_TOKEN)}


@app.get("/api/slack/status")
async def slack_status():
    """
    Diagnostic: show what Slack the bot sees (channels, DMs, bot ID).
    Helps debug "bot doesn't see channels" issues.
    """
    if not SLACK_BOT_TOKEN:
        return {
            "ok": False,
            "error": "SLACK_BOT_TOKEN not set",
            "hint": "Set SLACK_BOT_TOKEN env var with xoxb-* token from Slack App",
        }
    try:
        client = get_slack_client()
        auth = await client.auth_test()
        bot_user_id = auth.get("user_id")
        bot_user = auth.get("user")

        resp_ch = await client.conversations_list(
            types="public_channel,private_channel",
            limit=200,
            exclude_archived=True,
        )
        channels_raw = resp_ch.get("channels") or []
        channels_member = [c for c in channels_raw if c.get("is_member")]
        channels_other = [c for c in channels_raw if not c.get("is_member")]

        resp_im = await client.conversations_list(types="im", limit=200, exclude_archived=True)
        dms = resp_im.get("channels") or []

        result = {
            "ok": True,
            "bot_user_id": bot_user_id,
            "bot_user": bot_user,
            "mention_format": f"<@{bot_user_id}>" if bot_user_id else None,
            "channels_where_bot_is_member": len(channels_member),
            "channels_list": [{"id": c["id"], "name": c.get("name", "?")} for c in channels_member],
            "channels_bot_not_in": len(channels_other),
            "hint_if_no_channels": "Invite bot: /invite @My MCP Bot in channel",
            "dm_count": len(dms),
            "poll_stats": _poll_stats,
            "debug_hint": "Set DEBUG_SLACK_POLL=1 for verbose poll logs",
        }
        return result
    except SlackApiError as e:
        resp = getattr(e, "response", None)
        err = resp.get("error", str(e)) if isinstance(resp, dict) else str(e)
        return {
            "ok": False,
            "error": err,
            "hint": "Check token validity and scopes: channels:read, groups:read, im:read, channels:history, im:history",
        }


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)


if __name__ == "__main__":
    main()
