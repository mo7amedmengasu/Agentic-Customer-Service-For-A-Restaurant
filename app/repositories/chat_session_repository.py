from typing import List
from sqlalchemy.orm import Session
from app.models.chat_session import ChatSession, ChatMessage


class ChatSessionRepository:
    def get_sessions_for_user(self, db: Session, *, user_id: int) -> List[ChatSession]:
        return (
            db.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )

    def create_session(self, db: Session, *, user_id: int, title: str = "New Chat") -> ChatSession:
        session = ChatSession(user_id=user_id, title=title)
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def get_session(self, db: Session, *, session_id: int, user_id: int):
        return (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )

    def delete_session(self, db: Session, *, session_id: int, user_id: int) -> bool:
        session = self.get_session(db, session_id=session_id, user_id=user_id)
        if not session:
            return False
        db.delete(session)
        db.commit()
        return True

    def update_session_title(self, db: Session, *, session_id: int, title: str) -> ChatSession:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.title = title
            db.commit()
            db.refresh(session)
        return session

    def add_message(self, db: Session, *, session_id: int, role: str, content: str) -> ChatMessage:
        msg = ChatMessage(session_id=session_id, role=role, content=content)
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    def get_messages(self, db: Session, *, session_id: int) -> List[ChatMessage]:
        return (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
            .all()
        )
