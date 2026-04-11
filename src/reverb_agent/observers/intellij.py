"""IntelliJ observer via WebSocket."""

import asyncio
import json
import logging
from typing import List
from reverb_agent.observers.base import Observer
from reverb_agent.observers.events import ObserverEvent
from reverb_agent.constants import Capability
import websockets

logger = logging.getLogger('reverb.intellij')


class IntelliJObserver(Observer):
    """Observer for IntelliJ events via WebSocket Extension."""

    def __init__(self, interval: int = 2):
        super().__init__("intellij", app_bundle_id=None)
        self._interval = interval
        self._server = None
        self._port = 19997

    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.USER_ACTION,
        ]

    async def start(self) -> None:
        await super().start()

        # Start a websocket server on 127.0.0.1:19997 to listen to the IDE plugin
        logger.info(f"Starting IntelliJ Plugin WS Server on port {self._port}")
        self._server = await websockets.serve(
            self._handle_client, "127.0.0.1", self._port
        )

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        await super().stop()

    async def _handle_client(self, websocket):
        """Handle incoming connection from the IDEA plugin."""
        logger.info("IntelliJ WS Client connected!")
        try:
            async for message in websocket:
                if not self._running:
                    break
                try:
                    payload = json.loads(message)
                    event_type = payload.get("type")
                    data = payload.get("data", {})

                    if event_type == "file_focus":
                        path = data.get("path", "")
                        name = data.get("name", "")
                        event = ObserverEvent(
                            observer=self.name,
                            type="file_focus",
                            source={"app": "IntelliJ IDEA", "file": path},
                            data={"name": name}
                        )
                        self._emit(event)

                    elif event_type == "user_action":
                        action = data.get("action", "")
                        element = data.get("element", "")
                        text = data.get("text", "")
                        event = ObserverEvent(
                            observer=self.name,
                            type="user_action",
                            source={"app": "IntelliJ IDEA", "file": element},
                            data={"action": action, "element": "editor", "text": text}
                        )
                        self._emit(event)

                    elif event_type == "ide_execution":
                        action = data.get("action", "")
                        executor = data.get("executor", "")
                        config = data.get("configuration", "")
                        event = ObserverEvent(
                            observer=self.name,
                            type="user_action",
                            source={"app": "IntelliJ IDEA"},
                            data={"action": f"run_{action}", "element": "Run Configurations", "text": f"{executor} on {config}"}
                        )
                        self._emit(event)

                    elif event_type == "ide_debug":
                        action = data.get("action", "")
                        file_path = data.get("file", "")
                        line = data.get("line", "")
                        event = ObserverEvent(
                            observer=self.name,
                            type="user_action",
                            source={"app": "IntelliJ IDEA", "file": file_path},
                            data={"action": action, "element": "breakpoint", "text": f"Line {line}"}
                        )
                        self._emit(event)

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.error(f"Error parsing IntelliJ event: {e}")
        except websockets.exceptions.ConnectionClosed:
            pass