from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class UserMemory(Base):
    __tablename__ = "user_memories"

    memory_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), index=True, nullable=False)
    key = Column(String(64), nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    user = relationship("User", back_populates="memories")

    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_user_memory_user_id_key"),
    )
