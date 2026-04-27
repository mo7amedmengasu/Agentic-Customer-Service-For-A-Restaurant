from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    user_type = Column(String(20))
    user_name = Column(String(255))
    user_email = Column(String(255), unique=True, index=True)
    user_tel = Column(String(20))
    user_password = Column(String(255))

    # Relationships
    orders = relationship("Order", back_populates="customer")
    complaints = relationship("Complaint", back_populates="customer")
    chat_sessions = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    memories = relationship(
        "UserMemory",
        back_populates="user",
        cascade="all, delete-orphan",
    )
