"""Base IDE observer class."""

import asyncio
import subprocess
from abc import abstractmethod
from typing import Optional

from reverb_agent.observers.base import Observer
from reverb_agent.observers.events import ObserverEvent
from reverb_agent.constants import Capability


class IDEObserver(Observer):
    """Base class for IDE observers using AppleScript."""
    
    def __init__(self, name: str, app_bundle_id: str, interval: int = 2):
        super().__init__(name, app_bundle_id)
        self._interval = interval
        self._task: Optional[asyncio.Task] = None
        self._last_file = None
    
    @property
    def capabilities(self) -> list[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.FILE_CONTENT,
            Capability.CURSOR_POSITION,
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
                await self._check_ide()
            except Exception as e:
                print(f"Error checking {self.name}: {e}")
            await asyncio.sleep(self._interval)
    
    async def _check_ide(self) -> None:
        script = self._get_applescript()
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            file_path = result.stdout.strip()
            if file_path and file_path != self._last_file:
                self._last_file = file_path
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                except Exception:
                    content = ""
                event = ObserverEvent(
                    observer=self.name,
                    type="file_focus",
                    source={
                        "app": self.name,
                        "file": file_path,
                    },
                    data={"content": content}
                )
                self._emit(event)
    
    @abstractmethod
    def _get_applescript(self) -> str:
        """Return the AppleScript to check the IDE."""
        pass