from pydantic import BaseModel, ConfigDict
from typing import Optional
from decimal import Decimal

class OrderItemBase(BaseModel):
    order_id: int
    item_id: int
    item_name: str
    item_price: Decimal
    item_quantity: int

class OrderItemCreate(OrderItemBase):
    pass

class OrderItemUpdate(BaseModel):
    item_name: Optional[str] = None
    item_price: Optional[Decimal] = None
    item_quantity: Optional[int] = None

class OrderItem(OrderItemBase):
    model_config = ConfigDict(from_attributes=True)
