"""System observer for macOS events using long-running AppleScript listener."""

import asyncio
from typing import List
from reverb_agent.observers.base import Observer
from reverb_agent.observers.events import ObserverEvent
from reverb_agent.constants import Capability


class SystemObserver(Observer):
    """Observer for system-level events on macOS using event-based listening."""
    
    def __init__(self, interval: int = 5):
        super().__init__("system", app_bundle_id=None)
        self._interval = interval
        self._task = None
        self._last_app = None
        self._last_window = None
        self._process = None
    
    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.FILE_CONTENT,
        ]
    
    async def start(self) -> None:
        await super().start()
        await self._start_listener()
        self._task = asyncio.create_task(self._listen_loop())
    
    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
            except:
                pass
        await super().stop()
    
    async def _start_listener(self) -> None:
        """Start long-running AppleScript listener for app focus events."""
        script = '''
        on run
            set lastApp to ""
            
            tell application "System Events"
                repeat
                    try
                        set frontApp to first application process whose frontmost is true
                        set appName to name of frontApp
                        
                        if appName is not equal to lastApp then
                            set lastApp to appName
                            set windowTitle to ""
                            try
                                set windowTitle to name of first window of frontApp
                            end try
                            -- Use stdout to communicate
                            log appName & "|||" & windowTitle
                        end if
                    end try
                    delay 0.3
                end repeat
            end tell
        end run
        '''
        
        self._process = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL
        )
    
    async def _listen_loop(self) -> None:
        """Listen for events from AppleScript process."""
        if not self._process or not self._process.stderr:
            return
            
        while self._running:
            try:
                line = await asyncio.wait_for(
                    self._process.stderr.readline(),
                    timeout=1.0
                )
                if not line:
                    break
                    
                output = line.decode().strip()
                if output and output != "|||":
                    parts = output.split("|||")
                    app_name = parts[0].strip() if len(parts) > 0 else ""
                    window_title = parts[1].strip() if len(parts) > 1 else ""
                    
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
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error listening: {e}")
                break