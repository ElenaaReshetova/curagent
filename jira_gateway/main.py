"""Jira Gateway: polls Jira for issues assigned to bot, produces to Kafka, callback for agent results."""

import asyncio
import base64
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import httpx
from aiokafka import AIOKafkaProducer
from fastapi import FastAPI
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TASKS_TOPIC", "tasks")
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
JIRA_USER_EMAIL = os.environ.get("JIRA_USER_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
JIRA_PROJECT = os.environ.get("JIRA_PROJECT", "CUR")
JIRA_ASSIGNEE_DISPLAY_NAME = os.environ.get("JIRA_ASSIGNEE_DISPLAY_NAME", "").strip()
JIRA_ASSIGNEE_ACCOUNT_ID = os.environ.get("JIRA_ASSIGNEE_ACCOUNT_ID", "").strip()
JIRA_JQL_OVERRIDE = os.environ.get("JIRA_JQL_OVERRIDE", "").strip()
JIRA_CALLBACK_BASE_URL = os.environ.get("JIRA_CALLBACK_BASE_URL", "http://jira_gateway:8091")
POLL_INTERVAL_SEC = float(os.environ.get("JIRA_POLL_INTERVAL", "60"))
DEBUG_JIRA_POLL = os.environ.get("DEBUG_JIRA_POLL", "").lower() in ("1", "true", "yes")

if DEBUG_JIRA_POLL:
    logger.setLevel(logging.DEBUG)

_producer: Optional[AIOKafkaProducer] = None
_http_client: Optional[httpx.AsyncClient] = None
_poller_task: Optional[asyncio.Task] = None
_processed_issue_keys: set[str] = set()
_poll_stats: dict = {"tasks_produced": 0, "last_poll_at": None, "last_error": None}
_assignee_account_id_cache: Optional[str] = None
_assignee_account_id_resolved: bool = False


def _jira_auth_headers() -> dict:
    """Basic auth for Jira Cloud: email:api_token base64."""
    if not JIRA_USER_EMAIL or not JIRA_API_TOKEN:
        return {}
    creds = f"{JIRA_USER_EMAIL}:{JIRA_API_TOKEN}"
    encoded = base64.b64encode(creds.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await _producer.start()
    return _producer


async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=JIRA_BASE_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                **_jira_auth_headers(),
            },
            timeout=30.0,
        )
    return _http_client


def _extract_text_from_adf(adf: dict) -> str:
    """Extract plain text from Atlassian Document Format."""
    if not adf:
        return ""
    parts = []

    def walk(node: dict):
        if isinstance(node, dict):
            if node.get("type") == "text" and "text" in node:
                parts.append(node["text"])
            for v in node.values():
                if isinstance(v, list):
                    for item in v:
                        walk(item)
                elif isinstance(v, dict):
                    walk(v)

    walk(adf)
    return "".join(parts).strip()


def _write_debug_log(msg: str, data: dict):
    log_path = os.environ.get("DEBUG_LOG_PATH", "/Users/nickolaj95/auto_agent/.cursor/debug.log")
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({"timestamp": datetime.utcnow().isoformat(), "message": msg, "data": data}) + "\n")
    except Exception:
        pass


async def _resolve_account_id(display_name: str) -> Optional[str]:
    """Resolve Jira accountId from display name via user search API."""
    if not display_name:
        return None
    client = await get_http_client()
    try:
        resp = await client.get(
            "/rest/api/3/user/assignable/multiProjectSearch",
            params={"query": display_name, "projectKeys": JIRA_PROJECT, "maxResults": 10},
        )
        resp.raise_for_status()
        users = resp.json()
        display_lower = display_name.strip().lower()
        for u in users:
            dn = (u.get("displayName") or "").strip().lower()
            if dn == display_lower:
                return u.get("accountId")
        if users:
            return users[0].get("accountId")
        return None
    except Exception as e:
        logger.warning("Failed to resolve accountId for %r: %s", display_name, e)
        return None


async def _search_issues() -> list[dict]:
    """Search Jira for issues assigned to current user in project CUR."""
    global _assignee_account_id_cache, _assignee_account_id_resolved
    if not JIRA_BASE_URL or not JIRA_API_TOKEN or not JIRA_USER_EMAIL:
        return []

    client = await get_http_client()

    if JIRA_JQL_OVERRIDE:
        jql = JIRA_JQL_OVERRIDE
    else:
        if JIRA_ASSIGNEE_DISPLAY_NAME or JIRA_ASSIGNEE_ACCOUNT_ID:
            account_id = JIRA_ASSIGNEE_ACCOUNT_ID
            if not account_id and JIRA_ASSIGNEE_DISPLAY_NAME:
                if not _assignee_account_id_resolved:
                    _assignee_account_id_cache = await _resolve_account_id(JIRA_ASSIGNEE_DISPLAY_NAME)
                    _assignee_account_id_resolved = True
                    # #region agent log
                    _write_debug_log("accountId resolved", {"display_name": JIRA_ASSIGNEE_DISPLAY_NAME, "account_id": _assignee_account_id_cache})
                    # #endregion
                account_id = _assignee_account_id_cache
            assignee_expr = f'assignee = "{account_id}"' if account_id else (f'assignee = "{JIRA_ASSIGNEE_DISPLAY_NAME}"' if JIRA_ASSIGNEE_DISPLAY_NAME else "assignee = currentUser()")
        else:
            assignee_expr = "assignee = currentUser()"
        jql_base = f"project = {JIRA_PROJECT} AND {assignee_expr}"
        jql = f"{jql_base} AND statusCategory != Done ORDER BY updated DESC"

    # #region agent log
    _write_debug_log("JQL request", {"jql": jql, "assignee_display_name": JIRA_ASSIGNEE_DISPLAY_NAME or None, "override": bool(JIRA_JQL_OVERRIDE)})
    # #endregion

    try:
        resp = await client.post(
            "/rest/api/3/search/jql",
            json={
                "jql": jql,
                "maxResults": 20,
                "fields": ["summary", "description", "status", "issuetype", "key"],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        issues = data.get("issues", [])
        # #region agent log
        _write_debug_log("JQL response", {"status": resp.status_code, "count": len(issues), "keys": [i.get("key") for i in issues[:5]]})
        # #endregion
        if not issues and not JIRA_JQL_OVERRIDE:
            account_id_fb = JIRA_ASSIGNEE_ACCOUNT_ID or _assignee_account_id_cache
            if account_id_fb:
                assignee_expr = f'assignee = "{account_id_fb}"'
            elif JIRA_ASSIGNEE_DISPLAY_NAME:
                assignee_expr = f'assignee = "{JIRA_ASSIGNEE_DISPLAY_NAME}"'
            else:
                assignee_expr = "assignee = currentUser()"
            fallback_jql = f"{assignee_expr} AND statusCategory != Done ORDER BY updated DESC"
            resp_fb = await client.post("/rest/api/3/search/jql", json={"jql": fallback_jql, "maxResults": 20, "fields": ["summary", "description", "status", "issuetype", "key", "project"]})
            if resp_fb.is_success:
                issues_fb = resp_fb.json().get("issues", [])
                issues_fb_filtered = [i for i in issues_fb if (i.get("fields", {}).get("project", {}).get("key") == JIRA_PROJECT)]
                issues = issues_fb_filtered if issues_fb_filtered else issues_fb
        return issues
    except httpx.HTTPStatusError as e:
        logger.warning("Jira search failed: %s %s", e.response.status_code, e.response.text)
        _poll_stats["last_error"] = str(e)
        return []
    except Exception as e:
        logger.warning("Jira search error: %s", e)
        _poll_stats["last_error"] = str(e)
        return []


def _build_task_description(issue: dict) -> str:
    """Build task description from Jira issue."""
    fields = issue.get("fields", {})
    summary = fields.get("summary", "")
    desc = fields.get("description")
    desc_text = _extract_text_from_adf(desc) if isinstance(desc, dict) else (desc or "")
    status = (fields.get("status") or {}).get("name", "")
    issue_type = (fields.get("issuetype") or {}).get("name", "")
    key = issue.get("key", "")

    parts = [f"[{key}] {summary}"]
    if desc_text:
        parts.append(f"Описание: {desc_text}")
    parts.append(f"Тип: {issue_type}, Статус: {status}")
    return "\n\n".join(parts)


async def _add_comment(issue_key: str, body: str) -> bool:
    """Add comment to Jira issue (Atlassian Document Format)."""
    if not JIRA_BASE_URL or not JIRA_API_TOKEN or not JIRA_USER_EMAIL:
        return False

    client = await get_http_client()
    adf_body = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": body}],
            }
        ],
    }
    try:
        resp = await client.post(
            f"/rest/api/3/issue/{issue_key}/comment",
            json={"body": adf_body},
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.warning("Failed to add Jira comment to %s: %s", issue_key, e)
        return False


async def poll_jira_and_produce():
    """Poll Jira for issues assigned to bot and produce tasks to Kafka."""
    issues = await _search_issues()
    if not issues:
        if DEBUG_JIRA_POLL:
            logger.debug("No Jira issues found")
        return

    producer = await get_producer()
    callback_url = f"{JIRA_CALLBACK_BASE_URL.rstrip('/')}/api/callback"

    for issue in issues:
        key = issue.get("key", "")
        if not key:
            continue
        if key in _processed_issue_keys:
            if DEBUG_JIRA_POLL:
                logger.debug("Skip already processed issue %s", key)
            continue

        description = _build_task_description(issue)
        task_id = str(uuid.uuid4())
        source_id = f"jira:{key}"

        task_payload = {
            "task_id": task_id,
            "source": "jira",
            "source_id": source_id,
            "description": description,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "callback_url": callback_url,
        }

        await producer.send_and_wait(KAFKA_TOPIC, task_payload)
        _processed_issue_keys.add(key)
        _poll_stats["tasks_produced"] = _poll_stats.get("tasks_produced", 0) + 1
        _poll_stats["last_poll_at"] = datetime.utcnow().isoformat() + "Z"
        logger.info("Task %s produced to Kafka from Jira %s", task_id, source_id)


async def poll_loop():
    """Main polling loop."""
    if not JIRA_BASE_URL or not JIRA_API_TOKEN or not JIRA_USER_EMAIL:
        logger.warning("JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN not set, Jira polling disabled")
        return

    logger.info("Jira poller started. Project: %s, interval: %ss", JIRA_PROJECT, POLL_INTERVAL_SEC)
    while True:
        try:
            _poll_stats["last_error"] = None
            await poll_jira_and_produce()
            _poll_stats["last_poll_at"] = datetime.utcnow().isoformat() + "Z"
        except Exception as e:
            _poll_stats["last_error"] = str(e)
            logger.exception("Jira poll error: %s", e)
        await asyncio.sleep(POLL_INTERVAL_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start poller on startup, stop on shutdown."""
    global _poller_task
    if JIRA_BASE_URL and JIRA_API_TOKEN and JIRA_USER_EMAIL:
        _poller_task = asyncio.create_task(poll_loop())
    yield
    if _poller_task:
        _poller_task.cancel()
        try:
            await _poller_task
        except asyncio.CancelledError:
            pass
    global _producer, _http_client
    if _producer:
        await _producer.stop()
        _producer = None
    if _http_client:
        await _http_client.aclose()
        _http_client = None


app = FastAPI(title="Jira Gateway", lifespan=lifespan)


class CallbackRequest(BaseModel):
    task_id: str
    source_id: str  # jira:ISSUE_KEY
    message: str


@app.post("/api/callback")
async def callback(req: CallbackRequest):
    """
    Agent callback: receive task result and add comment to Jira issue.
    source_id format: jira:ISSUE_KEY
    """
    parts = req.source_id.split(":", 1)
    if len(parts) != 2 or parts[0] != "jira":
        logger.warning("Invalid source_id for Jira callback: %s", req.source_id)
        return {"status": "ok"}

    _, issue_key = parts
    if await _add_comment(issue_key, req.message):
        logger.info("Callback posted to Jira %s for task %s", issue_key, req.task_id)
    return {"status": "ok"}


@app.get("/")
async def root():
    """Root: links to health and status."""
    return {
        "service": "Jira Gateway",
        "endpoints": {
            "health": "/health",
            "jira_status": "/api/jira/status",
        },
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "jira_configured": bool(JIRA_BASE_URL and JIRA_API_TOKEN and JIRA_USER_EMAIL)}


@app.get("/api/jira/status")
async def jira_status():
    """Diagnostic: show Jira config and poll stats."""
    if not JIRA_BASE_URL or not JIRA_API_TOKEN or not JIRA_USER_EMAIL:
        return {
            "ok": False,
            "error": "JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN not set",
            "hint": "Set env vars for Jira Cloud API access",
        }
    return {
        "ok": True,
        "base_url": JIRA_BASE_URL,
        "project": JIRA_PROJECT,
        "assignee_filter": JIRA_ASSIGNEE_ACCOUNT_ID or JIRA_ASSIGNEE_DISPLAY_NAME or "currentUser()",
        "assignee_account_id": JIRA_ASSIGNEE_ACCOUNT_ID or (_assignee_account_id_cache if _assignee_account_id_resolved else None),
        "poll_stats": _poll_stats,
        "processed_issues_count": len(_processed_issue_keys),
        "assignee_hint": f"Задачи должны быть назначены на {JIRA_ASSIGNEE_DISPLAY_NAME or JIRA_USER_EMAIL}. Укажите JIRA_ASSIGNEE_DISPLAY_NAME (имя и фамилия в Jira) если назначение идёт по имени, а не по email.",
        "debug_hint": "Set DEBUG_JIRA_POLL=1 for verbose poll logs",
    }


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8091)


if __name__ == "__main__":
    main()
