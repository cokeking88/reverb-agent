"""VSCode observer for detailed code monitoring."""

import asyncio
import subprocess
from typing import List
from hermes_mac.observers.base import Observer
from hermes_mac.observers.events import ObserverEvent
from hermes_mac.constants import Capability


class VSCodeObserver(Observer):
    """Observer for VSCode events using AppleScript."""
    
    def __init__(self, interval: int = 2):
        super().__init__("vscode", app_bundle_id="com.microsoft.VSCode")
        self._interval = interval
        self._task = None
        self._last_file = None
    
    @property
    def capabilities(self) -> List[str]:
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
                await self._check_vscode()
            except Exception as e:
                print(f"Error checking VSCode: {e}")
            await asyncio.sleep(self._interval)
    
    async def _check_vscode(self) -> None:
        script = '''
        tell application "VSCode"
            if (count of windows) > 0 then
                set w to front window
                if (count of tabs of w) > 0 then
                    return path of active tab of w
                end if
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
            file_path = result.stdout.strip()
            if file_path and file_path != self._last_file:
                self._last_file = file_path
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                except:
                    content = ""
                event = ObserverEvent(
                    observer=self.name,
                    type="file_focus",
                    source={
                        "app": "VSCode",
                        "file": file_path,
                    },
                    data={"content": content}
                )
                self._emit(event)