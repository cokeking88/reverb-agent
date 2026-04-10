"""System observer for macOS window focus events using daemon poller."""

import asyncio
import subprocess
import os
from typing import List
from reverb_agent.observers.base import Observer
from reverb_agent.observers.events import ObserverEvent
from reverb_agent.constants import Capability


DAEMON_LOG = "/tmp/reverb_daemon.log"
DAEMON_SCRIPT = "/tmp/reverb_daemon.py"


class SystemObserver(Observer):
    """Observer for system-level events on macOS using background daemon."""
    
    def __init__(self, interval: int = 2):
        super().__init__("system", app_bundle_id=None)
        self._interval = interval
        self._task = None
        self._last_app = None
        self._daemon_pid = None
    
    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.FILE_CONTENT,
        ]
    
    async def start(self) -> None:
        await super().start()
        await self._start_daemon()
        self._task = asyncio.create_task(self._read_loop())
    
    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._daemon_pid:
            try:
                subprocess.run(["kill", str(self._daemon_pid)], timeout=1)
            except:
                pass
        await super().stop()
    
    async def _start_daemon(self) -> None:
        daemon_script = f"""#!/usr/bin/env python3
import subprocess
import os
import time
import sys

LOG = "{DAEMON_LOG}"
last = ''

while True:
    try:
        result = subprocess.run(
            ["osascript", "/tmp/test_front.app"],
            capture_output=True, text=True, timeout=2
        )
        app = result.stdout.strip()
        if app and app != last:
            with open(LOG, 'a') as f:
                f.write(time.strftime("%H:%M:%S") + ': ' + app + '\\n')
            last = app
    except:
        pass
    time.sleep(1)
"""
        
        with open(DAEMON_SCRIPT, 'w') as f:
            f.write(daemon_script)
        os.chmod(DAEMON_SCRIPT, 0o755)
        
        proc = subprocess.Popen(
            ["/usr/bin/python3", DAEMON_SCRIPT],
            cwd="/tmp",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True
        )
        self._daemon_pid = proc.pid
    
    async def _read_loop(self) -> None:
        last_pos = 0
        while self._running:
            try:
                if os.path.exists(DAEMON_LOG):
                    stat = os.stat(DAEMON_LOG)
                    if stat.st_size > last_pos:
                        with open(DAEMON_LOG, 'r') as f:
                            f.seek(last_pos)
                            new_lines = f.readlines()
                        last_pos = stat.st_size
                        
                        for line in new_lines:
                            line = line.strip()
                            if ':' in line:
                                app = line.split(':', 1)[1].strip()
                                if app and app != self._last_app:
                                    self._last_app = app
                                    self._emit_event(app, "")
            except:
                pass
            await asyncio.sleep(0.5)
    
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