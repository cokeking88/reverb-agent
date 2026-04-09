"""Feishu observer for Lark/Feishu desktop app."""

import asyncio
import subprocess
from typing import List
from reverb_agent.observers.ide_observer import IDEObserver
from reverb_agent.observers.events import ObserverEvent
from reverb_agent.constants import Capability


class FeishuObserver(IDEObserver):
    """Observer for Feishu/Lark desktop app."""
    
    def __init__(self, interval: int = 3):
        super().__init__("feishu", app_bundle_id="com.lark.lark")
        self._interval = interval
        self._last_window = None
    
    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.MESSAGE,
        ]
    
    async def start(self) -> None:
        await super().start()
        self._task = asyncio.create_task(self._poll_loop())
    
    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await super().stop()
    
    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._check_feishu()
            except Exception as e:
                print(f"Error checking Feishu: {e}")
            await asyncio.sleep(self._interval)
    
    async def _check_feishu(self) -> None:
        script = '''
        tell application "Feishu"
            if (count of windows) > 0 then
                set w to front window
                set windowTitle to name of w
                return windowTitle
            end if
        end tell
        return ""
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            window_title = result.stdout.strip()
            if window_title != self._last_window:
                self._last_window = window_title
                event = ObserverEvent(
                    observer=self.name,
                    type="window_focus",
                    source={"app": "Feishu", "window": window_title},
                    data={"window_title": window_title}
                )
                self._emit(event)
