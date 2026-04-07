from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class OrderBase(BaseModel):
    customer_id: int
    order_type: str
    order_status: str
    order_date: datetime

class OrderCreate(OrderBase):
    pass

class OrderUpdate(BaseModel):
    order_type: Optional[str] = None
    order_status: Optional[str] = None
    order_date: Optional[datetime] = None

class Order(OrderBase):
    order_id: int
    model_config = ConfigDict(from_attributes=True)
