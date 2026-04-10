"""Browser observer for Chrome, Safari, Edge."""

import asyncio
import subprocess
from typing import List
from reverb_agent.observers.base import Observer
from reverb_agent.observers.events import ObserverEvent
from reverb_agent.constants import Capability


class BrowserObserver(Observer):
    """Observer for browser events."""
    
    SUPPORTED_BROWSERS = {
        "Google Chrome": "com.google.Chrome",
        "Safari": "com.apple.Safari",
        "Microsoft Edge": "com.microsoft.edgemac",
    }
    
    def __init__(self, browser: str = "Google Chrome", interval: int = 3):
        bundle_id = self.SUPPORTED_BROWSERS.get(browser, "com.google.Chrome")
        super().__init__("browser", app_bundle_id=bundle_id)
        self._browser = browser
        self._interval = interval
        self._task = None
        self._last_url = None
    
    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.DOM_CONTENT,
            Capability.USER_ACTION,
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
                await self._check_browser()
            except Exception as e:
                print(f"Error checking browser: {e}")
            await asyncio.sleep(self._interval)
    
    async def _check_browser(self) -> None:
        script = f'''
        tell application "{self._browser}"
            if (count of windows) > 0 then
                set w to front window
                if (count of tabs of w) > 0 then
                    set t to active tab of w
                    return URL of t & "|||" & title of t
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
            output = result.stdout.strip()
            if output and output != "|||" and output != self._last_url:
                self._last_url = output
                parts = output.split("|||")
                url = parts[0] if len(parts) > 0 else ""
                title = parts[1] if len(parts) > 1 else ""
                
                event = ObserverEvent(
                    observer=self.name,
                    type="page_focus",
                    source={"app": self._browser, "url": url},
                    data={"title": title, "url": url}
                )
                self._emit(event)
