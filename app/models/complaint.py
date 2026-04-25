from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Complaint(Base):
    __tablename__ = "complaints"

    complaint_id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=True)
    complaint_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(50), nullable=False, default="medium")
    complaint_status = Column(String(50), nullable=False, default="open")
    created_at = Column(DateTime, nullable=True)

    customer = relationship("User", back_populates="complaints")
    order = relationship("Order", back_populates="complaints")