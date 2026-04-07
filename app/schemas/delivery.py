from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class DeliveryBase(BaseModel):
    order_id: int
    delivery_service: Optional[str] = None
    delivery_status: Optional[str] = None
    delivery_date: Optional[datetime] = None

class DeliveryCreate(DeliveryBase):
    pass

class DeliveryUpdate(BaseModel):
    delivery_service: Optional[str] = None
    delivery_status: Optional[str] = None
    delivery_date: Optional[datetime] = None

class Delivery(DeliveryBase):
    delivery_id: int
    model_config = ConfigDict(from_attributes=True)
