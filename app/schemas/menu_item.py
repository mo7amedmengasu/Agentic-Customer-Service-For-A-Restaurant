from pydantic import BaseModel, ConfigDict
from typing import Optional
from decimal import Decimal

class MenuItemBase(BaseModel):
    item_name: str
    item_description: Optional[str] = None
    item_image: Optional[str] = None
    item_price: Decimal

class MenuItemCreate(MenuItemBase):
    pass

class MenuItemUpdate(BaseModel):
    item_name: Optional[str] = None
    item_description: Optional[str] = None
    item_image: Optional[str] = None
    item_price: Optional[Decimal] = None

class MenuItem(MenuItemBase):
    item_id: int
    model_config = ConfigDict(from_attributes=True)
