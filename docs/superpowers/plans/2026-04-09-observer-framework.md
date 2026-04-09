# Observer Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the observer framework with base classes, registry, and SystemObserver for window focus/app events.

**Architecture:** Observer pattern with registry. Base Observer class defines interface, each specific observer implements the capability. Events flow through registry to Agent Loop.

**Tech Stack:** Python 3.11+, asyncio, AppleScript integration

---

## File Structure

```
src/hermes_mac/
├── observers/
│   ├── __init__.py
│   ├── base.py           # Base Observer class
│   ├── registry.py       # ObserverRegistry
│   ├── system.py         # SystemObserver
│   └── events.py        # ObserverEvent dataclass
├── cli.py               # Updated with observe command
└── config.py            # Updated with observer settings
```

### Task 1: Create Observer event and base classes

**Files:**
- Create: `src/hermes_mac/observers/__init__.py`
- Create: `src/hermes_mac/observers/events.py`
- Create: `src/hermes_mac/observers/base.py`

- [ ] **Step 1: Create events.py**

```python
"""Observer event definitions."""

import uuid
from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime


@dataclass
class ObserverEvent:
    """Event from an observer."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    observer: str = ""           # Observer name
    type: str = ""               # Event type
    timestamp: float = field(default_factory=lambda: time.time())
    source: dict = field(default_factory=dict)
    data: dict = field(default_factory=dict)
    task_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "observer": self.observer,
            "type": self.type,
            "timestamp": self.timestamp,
            "source": self.source,
            "data": self.data,
            "task_id": self.task_id,
        }


import time
```

- [ ] **Step 2: Create base.py**

```python
"""Base observer class."""

from abc import ABC, abstractmethod
from typing import Callable, List
from hermes_mac.observers.events import ObserverEvent


class Observer(ABC):
    """Base class for all observers."""
    
    def __init__(self, name: str, app_bundle_id: str = None):
        self.name = name
        self.app_bundle_id = app_bundle_id
        self._callbacks: List[Callable[[ObserverEvent], None]] = []
        self._running = False
    
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """Return list of capabilities this observer supports."""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start observing."""
        self._running = True
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop observing."""
        self._running = False
    
    def on_event(self, callback: Callable[[ObserverEvent], None]) -> None:
        """Register a callback for events."""
        self._callbacks.append(callback)
    
    def _emit(self, event: ObserverEvent) -> None:
        """Emit an event to all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"Error in callback for {self.name}: {e}")
    
    @property
    def is_running(self) -> bool:
        return self._running
```

- [ ] **Step 3: Create __init__.py**

```python
"""Observer subsystem."""

from hermes_mac.observers.base import Observer
from hermes_mac.observers.events import ObserverEvent
from hermes_mac.observers.registry import ObserverRegistry

__all__ = ["Observer", "ObserverEvent", "ObserverRegistry"]
```

- [ ] **Step 4: Run test to verify imports**

```bash
cd /Users/yangnanqing/projects/pc个人助手 && python -c "from hermes_mac.observers import Observer, ObserverEvent; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/hermes_mac/observers/
git commit -m "feat: add observer base classes"
```

### Task 2: Create Observer Registry

**Files:**
- Create: `src/hermes_mac/observers/registry.py`

- [ ] **Step 1: Create registry.py**

```python
"""Observer registry for managing observers."""

from typing import Dict, List, Optional, Callable
from hermes_mac.observers.base import Observer
from hermes_mac.observers.events import ObserverEvent


class ObserverRegistry:
    """Registry for managing all observers."""
    
    def __init__(self):
        self._observers: Dict[str, Observer] = {}
        self._global_callbacks: List[Callable[[ObserverEvent], None]] = []
    
    def register(self, observer: Observer) -> None:
        """Register an observer."""
        if observer.name in self._observers:
            raise ValueError(f"Observer {observer.name} already registered")
        self._observers[observer.name] = observer
    
    def unregister(self, name: str) -> None:
        """Unregister an observer."""
        if name in self._observers:
            del self._observers[name]
    
    def get(self, name: str) -> Optional[Observer]:
        """Get an observer by name."""
        return self._observers.get(name)
    
    def list(self) -> List[Observer]:
        """List all registered observers."""
        return list(self._observers.values())
    
    def list_by_capability(self, capability: str) -> List[Observer]:
        """List observers that support a given capability."""
        return [o for o in self._observers.values() if capability in o.capabilities]
    
    def on_event(self, callback: Callable[[ObserverEvent], None]) -> None:
        """Register a global callback for all events."""
        self._global_callbacks.append(callback)
        # Also register on all existing observers
        for observer in self._observers.values():
            observer.on_event(callback)
    
    async def start_all(self) -> None:
        """Start all observers."""
        for observer in self._observers.values():
            await observer.start()
    
    async def stop_all(self) -> None:
        """Stop all observers."""
        for observer in self._observers.values():
            await observer.stop()
```

- [ ] **Step 2: Run test to verify registry**

```bash
cd /Users/yangnanqing/projects/pc个人助手 && python -c "
from hermes_mac.observers import ObserverRegistry, Observer, ObserverEvent
from hermes_mac.observers.base import Observer
class TestObserver(Observer):
    @property
    def capabilities(self):
        return ['test']
    async def start(self):
        pass
    async def stop(self):
        pass

registry = ObserverRegistry()
registry.register(TestObserver('test'))
print(f'Registered: {len(registry.list())}')
"
```

Expected: `Registered: 1`

- [ ] **Step 3: Commit**

```bash
git add src/hermes_mac/observers/registry.py
git commit -m "feat: add observer registry"
```

### Task 3: Implement SystemObserver

**Files:**
- Create: `src/hermes_mac/observers/system.py`

- [ ] **Step 1: Create system.py**

```python
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
        import subprocess
        
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
        
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
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
```

- [ ] **Step 2: Test SystemObserver import**

```bash
cd /Users/yangnanqing/projects/pc个人助手 && python -c "from hermes_mac.observers.system import SystemObserver; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/hermes_mac/observers/system.py
git commit -m "feat: add system observer"
```

### Task 4: Add observe command to CLI

**Files:**
- Modify: `src/hermes_mac/cli.py`

- [ ] **Step 1: Add observe command to cli.py**

```python
# Add these imports at the top
import asyncio
from hermes_mac.observers import ObserverRegistry
from hermes_mac.observers.system import SystemObserver
from hermes_mac.observers.events import ObserverEvent


# Add this command before if __name__ == "__main__":
@main.command()
@click.option("--interval", default=5, help="Polling interval in seconds")
def observe(interval):
    """Start observation mode."""
    console.print(f"[green]Starting observation (interval: {interval}s)...[/green]")
    
    registry = ObserverRegistry()
    system_observer = SystemObserver(interval=interval)
    
    # Register global event handler
    def on_event(event: ObserverEvent):
        console.print(f"[cyan]{event.observer}[/cyan]: {event.type} - {event.source.get('app', 'N/A')}")
    
    registry.on_event(on_event)
    registry.register(system_observer)
    
    # Run until interrupted
    try:
        asyncio.run(registry.start_all())
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping observation...[/yellow]")
        asyncio.run(registry.stop_all())
```

- [ ] **Step 2: Test the observe command**

```bash
hermes-mac observe --help
```

Expected: Help output shows observe command

- [ ] **Step 3: Commit**

```bash
git add src/hermes_mac/cli.py
git commit -m "feat: add observe command to CLI"
```

---

## Summary

This plan implements:
- Observer base classes and event definitions
- Observer registry for managing observers
- SystemObserver for window focus events via AppleScript
- CLI command to start observation

**Next plan should cover:** IDE Observers (VSCode, IntelliJ) implementation.