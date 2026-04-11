"""System observer for macOS window focus events using pyobjc."""

import asyncio
from typing import List
import AppKit
from PyObjCTools import AppHelper

from reverb_agent.observers.base import Observer
from reverb_agent.observers.events import ObserverEvent
from reverb_agent.constants import Capability


class SystemObserver(Observer):
    """Observer for system-level events on macOS using AppKit."""

    def __init__(self, interval: int = 2):
        super().__init__("system", app_bundle_id=None)
        self._interval = interval
        self._last_app = None
        self._poll_task = None

    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.FILE_CONTENT,
        ]

    async def start(self) -> None:
        await super().start()
        # macOS GUI events generally require a runloop to use notifications.
        # A simple robust way from a background async process is polling NSWorkspace active application.
        self._poll_task = asyncio.create_task(self._poll_active_app())

    async def stop(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        await super().stop()

    async def _poll_active_app(self) -> None:
        """Poll the active application periodically."""
        workspace = AppKit.NSWorkspace.sharedWorkspace()
        while self._running:
            try:
                active_app = workspace.frontmostApplication()
                if active_app:
                    app_name = active_app.localizedName()
                    if app_name and app_name != self._last_app:
                        self._last_app = app_name
                        self._emit_event(app_name, "")
            except Exception as e:
                pass

            await asyncio.sleep(self._interval)

    def _emit_event(self, app_name: str, window_title: str) -> None:
        event = ObserverEvent(
            observer=self.name,
            type="window_focus",
            source={
                "app": app_name,
                "window": window_title,
            },
            data={}
        )
        self._emit(event)
