"""Browser observer via Chrome Extension WebSocket."""

import asyncio
import json
import logging
from typing import List
from reverb_agent.observers.base import Observer
from reverb_agent.observers.events import ObserverEvent
from reverb_agent.constants import Capability
import websockets

logger = logging.getLogger('reverb.browser')


class BrowserObserver(Observer):
    """Observer for browser events via WebSocket Extension."""

    def __init__(self, browser: str = "Google Chrome", interval: int = 3):
        # We still claim it's the specified browser
        super().__init__("browser", app_bundle_id=None)
        self._browser = browser
        self._interval = interval
        self._server = None
        self._server_task = None
        self._port = 19999
        self._last_url = ""

    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.DOM_CONTENT,
            Capability.USER_ACTION,
        ]

    async def start(self) -> None:
        await super().start()

        # Start a websocket server on 127.0.0.1:19999 to listen to the extension
        logger.info(f"Starting Browser Extension WS Server on port {self._port}")
        self._server = await websockets.serve(
            self._handle_client, "127.0.0.1", self._port
        )

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        await super().stop()

    async def _handle_client(self, websocket):
        """Handle incoming connection from the Chrome extension."""
        logger.info("Browser WS Client connected!")
        try:
            async for message in websocket:
                if not self._running:
                    break
                try:
                    payload = json.loads(message)
                    event_type = payload.get("type")
                    data = payload.get("data", {})

                    logger.info(f"Browser WS Message: {event_type}")

                    if event_type == "page_load":
                        url = data.get("url", "")
                        title = data.get("title", "")
                        content = data.get("content", "")
                        if url != self._last_url:
                            self._last_url = url
                            event = ObserverEvent(
                                observer=self.name,
                                type="page_focus",
                                source={"app": self._browser, "url": url},
                                data={"title": title, "url": url, "content": content}
                            )
                            self._emit(event)

                    elif event_type == "user_click":
                        tag = data.get("tag", "")
                        text = data.get("text", "")
                        url = data.get("url", "")
                        event = ObserverEvent(
                            observer=self.name,
                            type="user_action",
                            source={"app": self._browser, "url": url},
                            data={"action": "click", "element": tag, "text": text}
                        )
                        self._emit(event)

                    elif event_type == "user_input":
                        tag = data.get("tag", "")
                        name = data.get("name", "")
                        value = data.get("value_preview", "")
                        url = data.get("url", "")
                        event = ObserverEvent(
                            observer=self.name,
                            type="user_action",
                            source={"app": self._browser, "url": url},
                            data={"action": "input", "element": tag, "name": name, "value": value}
                        )
                        self._emit(event)

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.error(f"Error parsing browser event: {e}")
        except websockets.exceptions.ConnectionClosed:
            pass
