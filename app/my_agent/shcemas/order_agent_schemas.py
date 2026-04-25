from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExtractedItem(BaseModel):
    item_name: str = Field(..., description="The menu item name.")
    quantity: int | None = Field(default=None, description="Requested quantity for the item.")


class ExtractedOrderPayload(BaseModel):
    items: list[ExtractedItem] = Field(default_factory=list)
    order_type: Literal["pickup", "delivery"] | None = None
    delivery_address: str | None = None
    customer_notes: str | None = None


class OrderChange(BaseModel):
    action: Literal[
        "add",
        "remove",
        "replace",
        "change_quantity",
        "set_order_type",
        "set_delivery_address",
        "set_customer_notes",
    ]
    item_name: str | None = None
    new_item_name: str | None = None
    quantity: int | None = None
    order_type: Literal["pickup", "delivery"] | None = None
    delivery_address: str | None = None
    customer_notes: str | None = None


class OrderUpdatePayload(BaseModel):
    changes: list[OrderChange] = Field(default_factory=list)