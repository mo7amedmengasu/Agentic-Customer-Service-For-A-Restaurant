from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.chat_session import ChatSession


class ChatSessionRepository(BaseRepository[ChatSession]):
    def get_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ChatSession]:
        return (
            db.query(self.model)
            .filter(self.model.user_id == user_id)
            .order_by(self.model.updated_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_for_user(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: int,
    ) -> Optional[ChatSession]:
        return (
            db.query(self.model)
            .filter(
                self.model.session_id == session_id,
                self.model.user_id == user_id,
            )
            .first()
        )

    def touch(self, db: Session, *, session_id: str) -> None:
        obj = db.get(self.model, session_id)
        if obj:
            obj.updated_at = datetime.now(timezone.utc)
            db.add(obj)
            db.commit()

    def save_state(self, db: Session, *, session_id: str, state_json: str) -> None:
        obj = db.get(self.model, session_id)
        if obj:
            obj.state_json = state_json
            obj.updated_at = datetime.now(timezone.utc)
            db.add(obj)
            db.commit()


chat_session_repository = ChatSessionRepository(ChatSession)
