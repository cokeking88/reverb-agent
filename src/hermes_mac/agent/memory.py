"""Memory storage using SQLite."""

import json
import time
import uuid
from typing import Optional

from sqlalchemy import Column, String, Float, Text, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()


class Memory(Base):
    """Memory record."""
    __tablename__ = "memories"

    id = Column(String, primary_key=True)
    content = Column(Text, nullable=False)
    memory_type = Column(String, default="episodic")
    tags = Column(Text, default="")
    created_at = Column(Float, default=time.time)
    updated_at = Column(Float, default=time.time)


class Session(Base):
    """Session record for event storage."""
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    summary = Column(Text, default="")
    created_at = Column(Float, default=time.time)


class EventLog(Base):
    """Event log for a session."""
    __tablename__ = "event_log"

    id = Column(String, primary_key=True)
    session_id = Column(String)
    observer = Column(String)
    event_type = Column(String)
    timestamp = Column(Float)
    source = Column(Text)
    data = Column(Text)


class MemoryStore:
    """Memory storage manager."""

    def __init__(self, db_path: str):
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def add_memory(
        self, content: str, memory_type: str = "episodic", tags: list = None
    ) -> str:
        """Add a new memory."""
        memory_id = str(uuid.uuid4())
        memory = Memory(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            tags=",".join(tags or []),
            created_at=time.time(),
            updated_at=time.time(),
        )
        with self.Session() as session:
            session.add(memory)
            session.commit()
        return memory_id

    def get_memories(
        self, memory_type: Optional[str] = None, limit: int = 100
    ) -> list[Memory]:
        """Get memories."""
        with self.Session() as session:
            query = session.query(Memory)
            if memory_type:
                query = query.filter(Memory.memory_type == memory_type)
            return query.order_by(Memory.created_at.desc()).limit(limit).all()

    def add_event(
        self,
        session_id: str,
        observer: str,
        event_type: str,
        source: dict,
        data: dict,
    ) -> None:
        """Log an event."""
        event = EventLog(
            id=str(uuid.uuid4()),
            session_id=session_id,
            observer=observer,
            event_type=event_type,
            timestamp=time.time(),
            source=json.dumps(source),
            data=json.dumps(data),
        )
        with self.Session() as session:
            session.add(event)
            session.commit()

    def create_session(self) -> str:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        session = Session(id=session_id, created_at=time.time())
        with self.Session() as s:
            s.add(session)
            s.commit()
        return session_id