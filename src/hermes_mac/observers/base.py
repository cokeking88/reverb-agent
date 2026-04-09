"""Base observer class."""

from abc import ABC, abstractmethod
from typing import List, Callable
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
    
    def remove_callback(self, callback: Callable[[ObserverEvent], None]) -> None:
        """Remove a registered callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
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