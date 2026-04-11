"""Memory storage using SQLite."""

import json
import time
import uuid
import threading
from typing import Optional, List

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
        self.engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        self._init_fts()

        self._event_buffer: List[EventLog] = []
        self._buffer_lock = threading.Lock()
        self._flush_threshold = 20

    def _init_fts(self):
        """Initialize FTS5 tables and triggers for full-text search."""
        from sqlalchemy import text
        with self.engine.connect() as conn:
            # Create FTS5 virtual table for events
            conn.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS event_log_fts
                USING fts5(id UNINDEXED, session_id UNINDEXED, observer, event_type, source, data, content='event_log', content_rowid='rowid')
            """))

            # Create triggers to keep event_log_fts in sync
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS event_log_ai AFTER INSERT ON event_log BEGIN
                  INSERT INTO event_log_fts(rowid, id, session_id, observer, event_type, source, data)
                  VALUES (new.rowid, new.id, new.session_id, new.observer, new.event_type, new.source, new.data);
                END;
            """))
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS event_log_ad AFTER DELETE ON event_log BEGIN
                  INSERT INTO event_log_fts(event_log_fts, rowid, id, session_id, observer, event_type, source, data)
                  VALUES('delete', old.rowid, old.id, old.session_id, old.observer, old.event_type, old.source, old.data);
                END;
            """))
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS event_log_au AFTER UPDATE ON event_log BEGIN
                  INSERT INTO event_log_fts(event_log_fts, rowid, id, session_id, observer, event_type, source, data)
                  VALUES('delete', old.rowid, old.id, old.session_id, old.observer, old.event_type, old.source, old.data);
                  INSERT INTO event_log_fts(rowid, id, session_id, observer, event_type, source, data)
                  VALUES (new.rowid, new.id, new.session_id, new.observer, new.event_type, new.source, new.data);
                END;
            """))

            # Create FTS5 virtual table for memories
            conn.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(id UNINDEXED, content, memory_type, tags, content='memories', content_rowid='rowid')
            """))

            # Create triggers to keep memories_fts in sync
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                  INSERT INTO memories_fts(rowid, id, content, memory_type, tags)
                  VALUES (new.rowid, new.id, new.content, new.memory_type, new.tags);
                END;
            """))
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                  INSERT INTO memories_fts(memories_fts, rowid, id, content, memory_type, tags)
                  VALUES('delete', old.rowid, old.id, old.content, old.memory_type, old.tags);
                END;
            """))
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                  INSERT INTO memories_fts(memories_fts, rowid, id, content, memory_type, tags)
                  VALUES('delete', old.rowid, old.id, old.content, old.memory_type, old.tags);
                  INSERT INTO memories_fts(rowid, id, content, memory_type, tags)
                  VALUES (new.rowid, new.id, new.content, new.memory_type, new.tags);
                END;
            """))
            # Backfill existing data if FTS tables are empty
            res = conn.execute(text("SELECT count(*) FROM memories_fts")).scalar()
            if res == 0:
                conn.execute(text("""
                    INSERT INTO memories_fts(rowid, id, content, memory_type, tags)
                    SELECT rowid, id, content, memory_type, tags FROM memories;
                """))

            res = conn.execute(text("SELECT count(*) FROM event_log_fts")).scalar()
            if res == 0:
                conn.execute(text("""
                    INSERT INTO event_log_fts(rowid, id, session_id, observer, event_type, source, data)
                    SELECT rowid, id, session_id, observer, event_type, source, data FROM event_log;
                """))
            conn.commit()

    def search_events_fts(self, query: str, limit: int = 50) -> List[dict]:
        """Search events using FTS5."""
        from sqlalchemy import text
        # Make sure query is safe for FTS5
        safe_query = query.replace('"', '""')
        sql = text(f"""
            SELECT e.id, e.session_id, e.observer, e.event_type, e.timestamp, e.source, e.data, bm25(event_log_fts) as rank
            FROM event_log_fts fts
            JOIN event_log e ON e.rowid = fts.rowid
            WHERE event_log_fts MATCH :query
            ORDER BY rank
            LIMIT :limit
        """)

        with self.engine.connect() as conn:
            result = conn.execute(sql, {"query": f'"{safe_query}"', "limit": limit})
            return [dict(row._mapping) for row in result]

    def search_memories_fts(self, query: str, limit: int = 20) -> List[dict]:
        """Search memories using FTS5."""
        from sqlalchemy import text
        # Make sure query is safe for FTS5
        safe_query = query.replace('"', '""')
        sql = text(f"""
            SELECT m.id, m.content, m.memory_type, m.tags, m.created_at, bm25(memories_fts) as rank
            FROM memories_fts fts
            JOIN memories m ON m.rowid = fts.rowid
            WHERE memories_fts MATCH :query
            ORDER BY rank
            LIMIT :limit
        """)

        with self.engine.connect() as conn:
            result = conn.execute(sql, {"query": f'"{safe_query}"', "limit": limit})
            return [dict(row._mapping) for row in result]

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

    def get_session_events(self, session_id: str, limit: int = 1000) -> List[dict]:
        """Get events for a specific session."""
        from sqlalchemy import text
        sql = text("""
            SELECT id, session_id, observer, event_type, timestamp, source, data
            FROM event_log
            WHERE session_id = :session_id
            ORDER BY timestamp ASC
            LIMIT :limit
        """)
        with self.engine.connect() as conn:
            result = conn.execute(sql, {"session_id": session_id, "limit": limit})
            return [dict(row._mapping) for row in result]

    def add_event(
        self,
        session_id: str,
        observer: str,
        event_type: str,
        source: dict,
        data: dict,
    ) -> None:
        """Log an event to buffer and flush if necessary."""
        event = EventLog(
            id=str(uuid.uuid4()),
            session_id=session_id,
            observer=observer,
            event_type=event_type,
            timestamp=time.time(),
            source=json.dumps(source),
            data=json.dumps(data),
        )

        should_flush = False
        with self._buffer_lock:
            self._event_buffer.append(event)
            if len(self._event_buffer) >= self._flush_threshold:
                should_flush = True

        if should_flush:
            self.flush_events()

    def flush_events(self) -> None:
        """Flush the event buffer to the database."""
        with self._buffer_lock:
            if not self._event_buffer:
                return
            events_to_flush = self._event_buffer.copy()
            self._event_buffer.clear()

        with self.Session() as session:
            try:
                session.add_all(events_to_flush)
                session.commit()
            except Exception:
                session.rollback()
                # On error, we could re-add to buffer, but for now we just drop them to avoid poison pills
                pass

    def create_session(self) -> str:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        session = Session(id=session_id, created_at=time.time())
        with self.Session() as s:
            s.add(session)
            s.commit()
        return session_id

    def close(self) -> None:
        """Cleanup resources and flush remaining buffer."""
        self.flush_events()
        self.engine.dispose()
