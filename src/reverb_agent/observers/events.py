"""Observer event definitions."""

import uuid
import time
from dataclasses import dataclass, field
from typing import Optional, Any


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