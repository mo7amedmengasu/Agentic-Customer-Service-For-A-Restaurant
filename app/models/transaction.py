from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    tx_id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"))
    tx_time = Column(DateTime)
    tx_type = Column(String(50))
    tx_amount = Column(Numeric(10, 2))
    tx_notes = Column(Text)

    # Relationships
    order = relationship("Order", back_populates="transactions")
