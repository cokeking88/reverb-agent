"""System observer for macOS events."""

import asyncio
from typing import List
from hermes_mac.observers.base import Observer
from hermes_mac.observers.events import ObserverEvent
from hermes_mac.constants import Capability


class SystemObserver(Observer):
    """Observer for system-level events on macOS."""
    
    def __init__(self, interval: int = 5):
        super().__init__("system", app_bundle_id=None)
        self._interval = interval
        self._task = None
        self._last_app = None
        self._last_window = None
    
    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.FILE_CONTENT,
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
        """Poll for active application changes."""
        while self._running:
            try:
                await self._check_active_app()
            except Exception as e:
                print(f"Error checking active app: {e}")
            await asyncio.sleep(self._interval)
    
    async def _check_active_app(self) -> None:
        """Check the currently active application."""
        script = '''
        tell application "System Events"
            set frontApp to first application process whose frontmost is true
            set appName to name of frontApp
            set windowTitle to ""
            try
                set windowTitle to name of first window of frontApp
            end try
            return appName & "|||" & windowTitle
        end tell
        '''
        
        result = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await result.communicate()
        
        if result.returncode == 0:
            output = stdout.decode().strip()
            if output:
                parts = output.split("|||")
                app_name = parts[0] if len(parts) > 0 else ""
                window_title = parts[1] if len(parts) > 1 else ""
                
                if app_name != self._last_app or window_title != self._last_window:
                    self._last_app = app_name
                    self._last_window = window_title
                    
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