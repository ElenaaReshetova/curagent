"""Chat Gateway: REST API, Kafka producer, web chat, callback for agent results."""

import asyncio
import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Chat Gateway")

# Config
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TASKS_TOPIC", "tasks")
CALLBACK_BASE_URL = os.environ.get("CHAT_CALLBACK_BASE_URL", "http://localhost:8080")

# In-memory store: session_id -> list of {role, content, task_id?}
_messages: Dict[str, List[dict]] = defaultdict(list)
_producer: Optional[AIOKafkaProducer] = None
_session_callback_locks: Dict[str, asyncio.Lock] = {}
_session_locks_guard = asyncio.Lock()


async def _session_callback_lock(session_id: str) -> asyncio.Lock:
    async with _session_locks_guard:
        lock = _session_callback_locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            _session_callback_locks[session_id] = lock
        return lock


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await _producer.start()
    return _producer


class CreateSessionResponse(BaseModel):
    session_id: str


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)


class SendMessageResponse(BaseModel):
    task_id: str
    message: str


class CallbackRequest(BaseModel):
    task_id: str
    source_id: str  # session_id
    message: str


@app.on_event("shutdown")
async def shutdown():
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None


@app.post("/api/sessions", response_model=CreateSessionResponse)
async def create_session():
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    _messages[session_id] = []
    return CreateSessionResponse(session_id=session_id)


@app.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    """Get all messages for a session (for polling)."""
    if session_id not in _messages:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"messages": _messages[session_id]}


@app.post("/api/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(session_id: str, req: SendMessageRequest):
    """
    Send a message: creates a task in Kafka and adds user message to session.
    """
    if session_id not in _messages:
        raise HTTPException(status_code=404, detail="Session not found")

    task_id = str(uuid.uuid4())
    callback_url = f"{CALLBACK_BASE_URL.rstrip('/')}/api/callback"

    _messages[session_id].append({
        "role": "user",
        "content": req.content,
        "task_id": task_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })

    task_payload = {
        "task_id": task_id,
        "source": "chat",
        "source_id": session_id,
        "description": req.content,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "callback_url": callback_url,
    }

    producer = await get_producer()
    await producer.send_and_wait(KAFKA_TOPIC, task_payload)

    logger.info("Task %s created for session %s", task_id, session_id)
    return SendMessageResponse(task_id=task_id, message="Task queued")


# Tool confirmation phrases - do not add to chat (agent may resend them)
_CALLBACK_IGNORE = frozenset({
    "message sent successfully.", "ok", "done", "delivered.", "delivered",
    "result delivered.", "sent successfully.", "message delivered.",
})


def _should_ignore_callback_message(msg: str) -> bool:
    """Ignore status/confirmation messages, not actual content."""
    msg_lower = msg.strip().lower()
    if msg_lower in _CALLBACK_IGNORE:
        return True
    if msg_lower.startswith("task completed") or msg_lower.startswith("task completed."):
        return True
    return False


@app.post("/api/callback")
async def callback(req: CallbackRequest):
    """
    Agent callback: receive task result and add to session.
    """
    session_id = req.source_id
    if session_id not in _messages:
        logger.warning("Callback for unknown session %s", session_id)
        return {"status": "ok"}

    if _should_ignore_callback_message(req.message):
        return {"status": "ok"}

    lock = await _session_callback_lock(session_id)
    async with lock:
        existing_for_task = [
            m for m in _messages[session_id]
            if m.get("role") == "assistant" and m.get("task_id") == req.task_id
        ]
        if existing_for_task:
            return {"status": "ok"}

        _messages[session_id].append({
            "role": "assistant",
            "content": req.message,
            "task_id": req.task_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
        logger.info("Callback received for task %s, session %s", req.task_id, session_id)
    return {"status": "ok"}


# Fix: callback needs to receive session_id. The agent's send_to_chat tool
# posts to callback_url with task_id, source_id, message. Our callback_url
# is the same for all - we need source_id (session_id) in the body. Good, we have it.

# But wait - the agent doesn't know the callback_url includes the session. We pass
# callback_url in the task. So when we create the task, we set callback_url.
# The problem: the callback is the same URL for all. The session_id is in source_id
# in the request body. So we're good.

# Actually we need to pass callback_url that the Task Manager will forward to the agent.
# The task has callback_url. When Task Manager POSTs to agent, it includes callback_url.
# So the agent gets it. Good.

# Serve static HTML for chat UI
CHAT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>AI Agent Chat</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }
        .container { max-width: 600px; margin: 0 auto; }
        h1 { color: #0f3460; margin-bottom: 20px; }
        #messages { height: 400px; overflow-y: auto; border: 1px solid #333; border-radius: 8px; padding: 16px; margin-bottom: 16px; background: #16213e; }
        .msg { margin: 8px 0; padding: 10px 12px; border-radius: 8px; max-width: 85%; }
        .msg.user { background: #0f3460; margin-left: 0; }
        .msg.assistant { background: #533483; margin-left: auto; }
        .msg .role { font-size: 11px; opacity: 0.8; margin-bottom: 4px; }
        #input-area { display: flex; gap: 8px; }
        #input { flex: 1; padding: 12px; border-radius: 8px; border: 1px solid #333; background: #16213e; color: #eee; font-size: 16px; }
        #send { padding: 12px 24px; border-radius: 8px; border: none; background: #e94560; color: white; cursor: pointer; font-weight: 600; }
        #send:hover { background: #ff6b6b; }
        #send:disabled { opacity: 0.5; cursor: not-allowed; }
        .loading { opacity: 0.6; }
    </style>
</head>
<body>
    <div class="container">
        <h1>AI Agent Chat</h1>
        <div id="messages"></div>
        <div id="input-area">
            <input id="input" type="text" placeholder="Enter your task..." autocomplete="off">
            <button id="send">Send</button>
        </div>
    </div>
    <script>
        const apiBase = '';
        let sessionId = null;
        let pollInterval = null;

        async function init() {
            const r = await fetch(apiBase + '/api/sessions', { method: 'POST' });
            const d = await r.json();
            sessionId = d.session_id;
            startPolling();
        }

        function startPolling() {
            pollInterval = setInterval(poll, 2000);
        }

        async function poll() {
            if (!sessionId) return;
            const r = await fetch(apiBase + '/api/sessions/' + sessionId + '/messages');
            const d = await r.json();
            renderMessages(d.messages);
        }

        function renderMessages(messages) {
            const el = document.getElementById('messages');
            el.innerHTML = messages.map(m => 
                '<div class="msg ' + m.role + '"><div class="role">' + m.role + '</div>' + 
                escapeHtml(m.content) + '</div>'
            ).join('');
            el.scrollTop = el.scrollHeight;
        }

        function escapeHtml(s) {
            const div = document.createElement('div');
            div.textContent = s;
            return div.innerHTML;
        }

        async function send() {
            const input = document.getElementById('input');
            const sendBtn = document.getElementById('send');
            const text = input.value.trim();
            if (!text || !sessionId) return;
            input.value = '';
            sendBtn.disabled = true;
            try {
                await fetch(apiBase + '/api/sessions/' + sessionId + '/messages', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: text })
                });
                poll();
            } finally {
                sendBtn.disabled = false;
            }
        }

        document.getElementById('send').onclick = send;
        document.getElementById('input').onkeypress = (e) => { if (e.key === 'Enter') send(); };
        init();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def chat_ui():
    """Serve the chat UI."""
    return CHAT_HTML


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
