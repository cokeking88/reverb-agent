"""Observer registry for managing observers."""

from typing import Dict, List, Optional, Callable
from hermes_mac.observers.base import Observer
from hermes_mac.observers.events import ObserverEvent


class ObserverRegistry:
    """Registry for managing all observers.
    
    Note: This class is not thread-safe. All operations should be
    performed from a single thread (typically the asyncio event loop).
    """
    
    def __init__(self):
        self._observers: Dict[str, Observer] = {}
        self._global_callbacks: List[Callable[[ObserverEvent], None]] = []
    
    def register(self, observer: Observer) -> None:
        """Register an observer."""
        if observer.name in self._observers:
            raise ValueError(f"Observer {observer.name} already registered")
        self._observers[observer.name] = observer
        for callback in self._global_callbacks:
            observer.on_event(callback)
    
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