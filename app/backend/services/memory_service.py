from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.backend.config.settings import settings
from app.backend.services.cache_service import CacheService


Base = declarative_base()


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class MemoryService:
    def __init__(self, recent_messages_limit: int = 20):
        self.engine = create_engine(settings.postgres_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

        self.cache_service = CacheService()
        self.recent_messages_limit = recent_messages_limit

    def _cache_key(self, session_id: str) -> str:
        return f"conversation:{session_id}"

    def add_message(self, session_id: str, role: str, content: str) -> None:
        created_at = datetime.now(timezone.utc)

        session = self.SessionLocal()
        try:
            record = ConversationMessage(
                session_id=session_id,
                role=role,
                content=content,
                created_at=created_at
            )
            session.add(record)
            session.commit()
        finally:
            session.close()

        message = {
            "role": role,
            "content": content,
            "created_at": created_at.isoformat()
        }

        self.cache_service.push_json(
            self._cache_key(session_id),
            message,
            max_length=self.recent_messages_limit
        )

    def get_recent_messages(self, session_id: str) -> List[Dict[str, Any]]:
        cached = self.cache_service.get_list_json(self._cache_key(session_id))

        if cached:
            return cached

        return self.get_history(session_id, limit=self.recent_messages_limit)

    def get_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        session = self.SessionLocal()
        try:
            records = (
                session.query(ConversationMessage)
                .filter_by(session_id=session_id)
                .order_by(ConversationMessage.created_at.desc())
                .limit(limit)
                .all()
            )

            records = list(reversed(records))

            return [
                {
                    "role": record.role,
                    "content": record.content,
                    "created_at": record.created_at.isoformat()
                }
                for record in records
            ]
        finally:
            session.close()

    def clear_session(self, session_id: str) -> None:
        self.cache_service.delete(self._cache_key(session_id))

    def delete_session_history(self, session_id: str) -> None:
        session = self.SessionLocal()
        try:
            (
                session.query(ConversationMessage)
                .filter_by(session_id=session_id)
                .delete()
            )
            session.commit()
        finally:
            session.close()

        self.clear_session(session_id)
