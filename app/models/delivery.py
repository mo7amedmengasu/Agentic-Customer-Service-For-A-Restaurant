from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Delivery(Base):
    __tablename__ = "delivery"

    delivery_id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"))
    delivery_service = Column(String(255))
    delivery_status = Column(String(50))
    delivery_date = Column(DateTime)

    # Relationships
    order = relationship("Order", back_populates="delivery")
