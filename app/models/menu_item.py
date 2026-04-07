from sqlalchemy import Column, Integer, String, Text, Numeric
from sqlalchemy.orm import relationship
from app.core.database import Base


class MenuItem(Base):
    __tablename__ = "menu_items"

    item_id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String(255))
    item_description = Column(Text)
    item_image = Column(String(255))
    item_price = Column(Numeric(10, 2))

    # Relationships
    order_items = relationship("OrderItem", back_populates="menu_item")
