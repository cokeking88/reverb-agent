"""Web UI panel for Reverb Agent using FastAPI."""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import threading

from reverb_agent.observers.events import ObserverEvent
from reverb_agent.logging import logger

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass


manager = ConnectionManager()


class WebUIPanel:
    """Web UI panel server."""

    def __init__(self, host="127.0.0.1", port=19998):
        self._events: List[dict] = []
        self._thoughts: List[str] = []
        self._memories: List[str] = []
        self._status: str = "Initializing..."
        self._current_stream = ""
        self._is_streaming = False
        self._host = host
        self._port = port
        self._server = None
        self._server_thread = None
        self._on_user_reply_callback = None
        self._current_question = None
        self._main_loop = None

        # Hacky global reference for FastAPI routes to access this instance
        global _web_panel_instance
        _web_panel_instance = self

    def set_main_loop(self, loop):
        self._main_loop = loop

    def add_event(self, event: ObserverEvent) -> None:
        source = event.source.get("app") or event.source.get("file", event.source.get("url", "N/A"))
        if len(source) > 50:
            source = source[:50] + "..."

        detail = ""
        if event.type == "user_action":
            action = event.data.get("action", "")
            element = event.data.get("element", "")
            text = event.data.get("text", "")
            value = event.data.get("value", "")
            detail = f"[{action}] {element} '{text or value}'"
        elif event.type == "page_focus":
            detail = f"Title: {event.data.get('title', '')}"
        elif event.type == "user_reply":
            detail = f"Q: {event.data.get('question', '')} | A: {event.data.get('reply', '')}"

        if len(detail) > 100:
            detail = detail[:100] + "..."

        time_str = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")

        evt_dict = {
            "time": time_str,
            "observer": event.observer,
            "source": source,
            "type": event.type,
            "detail": detail
        }
        self._events.append(evt_dict)
        if len(self._events) > 30:
            self._events.pop(0)

        self._broadcast_state()

    def add_thought(self, thought: str) -> None:
        self._thoughts.append(thought)
        if len(self._thoughts) > 15:
            self._thoughts.pop(0)
        self._broadcast_state()

    def add_status_message(self, message: str, is_error: bool = False) -> None:
        prefix = "✗ " if is_error else "✓ "
        self._status = prefix + message
        self._broadcast_state()

    def add_memory(self, memory: str) -> None:
        self._memories.append(memory)
        if len(self._memories) > 15:
            self._memories.pop(0)
        self._broadcast_state()

    def update_status(self, status: str) -> None:
        self._status = status
        self._broadcast_state()

    def set_question(self, question: str, callback: callable) -> None:
        """Set a question from LLM to ask the user."""
        self._current_question = question
        self._on_user_reply_callback = callback

        # Log to thoughts
        self.add_thought(f"🤔 {question}")
        self._broadcast_state()

    def start_stream(self) -> None:
        self._is_streaming = True
        self._current_stream = ""
        self._broadcast_state()

    def add_stream_chunk(self, chunk: str) -> None:
        if self._is_streaming:
            self._current_stream += chunk
            self._broadcast_state()

    def end_stream(self) -> None:
        self._is_streaming = False
        self._broadcast_state()

    def clear_stream(self) -> None:
        self._is_streaming = False
        self._current_stream = ""
        self._broadcast_state()

    def clear_question(self) -> None:
        """Clear the current question."""
        self._current_question = None
        self._on_user_reply_callback = None
        self._broadcast_state()

    def handle_reply(self, reply: str):
        """Handle user reply from websocket."""
        if self._on_user_reply_callback and reply:
            try:
                self.add_thought(f"👤 {reply}")
                self._on_user_reply_callback(reply)
            except Exception as e:
                logger.error(f"Error handling user reply: {e}")
        self.clear_question()

    def _broadcast_state(self):
        """Broadcast current state to all connected websockets."""
        if not manager.active_connections:
            return

        state = {
            "type": "state_update",
            "events": self._events,
            "thoughts": self._thoughts,
            "memories": self._memories,
            "status": self._status,
            "question": self._current_question,
            "stream": self._current_stream if self._is_streaming else None
        }

        # Schedule broadcast safely in main loop
        if self._main_loop and self._main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast(json.dumps(state)),
                self._main_loop
            )

    async def run_server(self):
        config = uvicorn.Config(app, host=self._host, port=self._port, log_level="error")
        self._server = uvicorn.Server(config)
        await self._server.serve()

    def run_in_thread(self):
        """Run the uvicorn server in a separate thread."""
        self._server_thread = threading.Thread(
            target=lambda: asyncio.run(self.run_server()),
            daemon=True
        )
        self._server_thread.start()
        logger.info(f"Web UI Panel running at http://{self._host}:{self._port}")

    def stop(self):
        if self._server:
            self._server.should_exit = True


_web_panel_instance = None


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Reverb Agent Console</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background: #1e1e1e; color: #d4d4d4; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; gap: 20px; height: calc(100vh - 100px); }
        .panel { background: #252526; border: 1px solid #333; border-radius: 6px; padding: 15px; display: flex; flex-direction: column; overflow: hidden; }
        .panel-title { margin-top: 0; border-bottom: 1px solid #444; padding-bottom: 10px; color: #fff; font-size: 16px; font-weight: bold; }
        .panel-content { flex-grow: 1; overflow-y: auto; font-family: "Menlo", "Monaco", monospace; font-size: 13px; line-height: 1.5; }

        .event-row { display: flex; flex-direction: column; border-bottom: 1px solid #333; padding: 6px 0; }
        .event-header { display: flex; align-items: baseline; }
        .event-time { color: #569cd6; width: 70px; flex-shrink: 0; font-size: 12px; }
        .event-source { color: #ce9178; flex-grow: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: bold; }
        .event-detail { color: #888; font-size: 11px; margin-left: 70px; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

        .thought-item { color: #dcdcaa; margin-bottom: 15px; border-left: 3px solid #dcdcaa; padding-left: 10px; }
        .thought-item.user { color: #9cdcfe; border-left-color: #9cdcfe; }
        .thought-item.bot { color: #569cd6; border-left-color: #569cd6; font-weight: bold; }
        .thought-item.think { color: #c586c0; border-left-color: #c586c0; font-style: italic; white-space: pre-wrap; font-size: 12px; }
        .thought-stream { color: #858585; margin-bottom: 15px; border-left: 3px solid #858585; padding-left: 10px; font-style: italic; white-space: pre-wrap; font-size: 12px; }
        .memory-item { color: #4ec9b0; margin-bottom: 10px; border-left: 3px solid #4ec9b0; padding-left: 10px; }

        #status-bar { margin-top: 20px; padding: 10px 15px; background: #007acc; color: white; border-radius: 6px; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }

        #question-overlay { display: none; position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%); width: 80%; max-width: 600px; background: #2d2d30; border: 2px solid #007acc; border-radius: 8px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); z-index: 100; }
        #question-text { color: #569cd6; font-size: 16px; font-weight: bold; margin-bottom: 15px; }
        #reply-input { width: 100%; padding: 10px; box-sizing: border-box; background: #1e1e1e; border: 1px solid #444; color: #fff; font-size: 14px; border-radius: 4px; }
        #reply-input:focus { outline: none; border-color: #007acc; }
        .hint { font-size: 12px; color: #888; margin-top: 8px; }

        /* Custom scrollbar */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #1e1e1e; }
        ::-webkit-scrollbar-thumb { background: #424242; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #4f4f4f; }
    </style>
</head>
<body>
    <div class="grid">
        <div class="panel">
            <h2 class="panel-title">Event Stream</h2>
            <div id="events-content" class="panel-content"></div>
        </div>
        <div class="panel">
            <h2 class="panel-title">Thoughts</h2>
            <div id="thoughts-content" class="panel-content"></div>
        </div>
        <div class="panel">
            <h2 class="panel-title">Memories</h2>
            <div id="memories-content" class="panel-content"></div>
        </div>
        <div class="panel" style="background: transparent; border: none;">
             <!-- Placeholder for future modules -->
             <div style="color: #666; display: flex; justify-content: center; align-items: center; height: 100%; font-style: italic;">
                 Reverb Agent v1.0<br>Web UI Console
             </div>
        </div>
    </div>

    <div id="status-bar">
        <span id="status-text">Connecting...</span>
        <span id="ws-status" style="font-size: 12px; background: rgba(0,0,0,0.2); padding: 3px 8px; border-radius: 10px;">🔴 Offline</span>
    </div>

    <div id="question-overlay">
        <div id="question-text">💡 Question from Reverb:</div>
        <input type="text" id="reply-input" placeholder="Type your reply here..." autocomplete="off">
        <div class="hint">Press Enter to send, Esc to dismiss</div>
    </div>

    <script>
        const eventsContainer = document.getElementById('events-content');
        const thoughtsContainer = document.getElementById('thoughts-content');
        const memoriesContainer = document.getElementById('memories-content');
        const statusText = document.getElementById('status-text');
        const wsStatus = document.getElementById('ws-status');

        const questionOverlay = document.getElementById('question-overlay');
        const questionText = document.getElementById('question-text');
        const replyInput = document.getElementById('reply-input');

        let ws;

        function connect() {
            ws = new WebSocket(`ws://${window.location.host}/ws`);

            ws.onopen = () => {
                wsStatus.innerHTML = "🟢 Connected";
                wsStatus.style.color = "lightgreen";
            };

            ws.onclose = () => {
                wsStatus.innerHTML = "🔴 Offline";
                wsStatus.style.color = "pink";
                setTimeout(connect, 2000);
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);

                if (data.type === "state_update") {
                    // Update Status
                    statusText.innerText = data.status;

                    // Update Events
                    eventsContainer.innerHTML = '';
                    [...data.events].reverse().forEach(e => {
                        let detailHtml = '';
                        if (e.detail && e.detail.trim() !== '') {
                            detailHtml = `<div class="event-detail">${e.detail}</div>`;
                        }
                        eventsContainer.innerHTML += `
                            <div class="event-row">
                                <div class="event-header">
                                    <span class="event-time">${e.time}</span>
                                    <span class="event-source">[${e.observer}] ${e.source} (${e.type})</span>
                                </div>
                                ${detailHtml}
                            </div>
                        `;
                    });

                    // Update Thoughts
                    thoughtsContainer.innerHTML = '';
                    if (data.stream !== null) {
                        thoughtsContainer.innerHTML += `<div class="thought-stream">${data.stream}</div>`;
                    }
                    [...data.thoughts].reverse().forEach(t => {
                        if (t.startsWith("🤔")) {
                            thoughtsContainer.innerHTML += `<div class="thought-item bot">${t}</div>`;
                        } else if (t.startsWith("👤")) {
                            thoughtsContainer.innerHTML += `<div class="thought-item user">${t}</div>`;
                        } else if (t.startsWith("🧠")) {
                            thoughtsContainer.innerHTML += `<div class="thought-item think">${t}</div>`;
                        } else {
                            thoughtsContainer.innerHTML += `<div class="thought-item">${t}</div>`;
                        }
                    });
                    if (data.thoughts.length === 0 && data.stream === null) thoughtsContainer.innerHTML = '<div style="color: #666">Waiting for analysis...</div>';

                    // Update Memories
                    memoriesContainer.innerHTML = '';
                    [...data.memories].reverse().forEach(m => {
                        memoriesContainer.innerHTML += `<div class="memory-item">${m}</div>`;
                    });
                    if (data.memories.length === 0) memoriesContainer.innerHTML = '<div style="color: #666">No memories yet</div>';

                    // Handle Question
                    if (data.question) {
                        questionText.innerText = "💡 " + data.question;
                        questionOverlay.style.display = 'block';
                        replyInput.focus();
                    } else {
                        questionOverlay.style.display = 'none';
                    }
                }
            };
        }

        // Handle input replies
        replyInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const text = replyInput.value.trim();
                ws.send(JSON.stringify({ type: "user_reply", reply: text }));
                replyInput.value = '';
                questionOverlay.style.display = 'none';
            } else if (e.key === 'Escape') {
                ws.send(JSON.stringify({ type: "user_reply", reply: "" }));
                replyInput.value = '';
                questionOverlay.style.display = 'none';
            }
        });

        connect();
    </script>
</body>
</html>
"""


@app.get("/")
async def get_dashboard():
    return HTMLResponse(HTML_TEMPLATE)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Send initial state
    if _web_panel_instance:
        state = {
            "type": "state_update",
            "events": _web_panel_instance._events,
            "thoughts": _web_panel_instance._thoughts,
            "memories": _web_panel_instance._memories,
            "status": _web_panel_instance._status,
            "question": _web_panel_instance._current_question,
            "stream": _web_panel_instance._current_stream if _web_panel_instance._is_streaming else None
        }
        await websocket.send_text(json.dumps(state))

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                if payload.get("type") == "user_reply" and _web_panel_instance:
                    reply_text = payload.get("reply", "")
                    _web_panel_instance.handle_reply(reply_text)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
