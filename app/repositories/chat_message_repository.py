from typing import List
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.chat_message import ChatMessage


class ChatMessageRepository(BaseRepository[ChatMessage]):
    def get_by_session(
        self,
        db: Session,
        *,
        session_id: str,
        limit: int = 500,
    ) -> List[ChatMessage]:
        return (
            db.query(self.model)
            .filter(self.model.session_id == session_id)
            .order_by(self.model.created_at.asc())
            .limit(limit)
            .all()
        )

    def append(
        self,
        db: Session,
        *,
        session_id: str,
        role: str,
        content: str,
    ) -> ChatMessage:
        return self.create(
            db,
            obj_in={"session_id": session_id, "role": role, "content": content},
        )


chat_message_repository = ChatMessageRepository(ChatMessage)
