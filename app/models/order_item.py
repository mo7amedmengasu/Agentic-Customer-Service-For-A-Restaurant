from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    order_id = Column(Integer, ForeignKey("orders.order_id"), primary_key=True)
    item_id = Column(Integer, ForeignKey("menu_items.item_id"), primary_key=True)
    item_name = Column(String(255))
    item_price = Column(Numeric(10, 2))
    item_quantity = Column(Integer)

    # Relationships
    order = relationship("Order", back_populates="order_items")
    menu_item = relationship("MenuItem", back_populates="order_items")
