from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.delivery import Delivery
from app.models.order import Order
from app.models.order_item import OrderItem
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def get_by_customer(self, db: Session, *, customer_id: int, skip: int = 0, limit: int = 100) -> list[Order]:
        return (
            db.query(self.model)
            .filter(self.model.customer_id == customer_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_status(self, db: Session, *, status: str, skip: int = 0, limit: int = 100) -> list[Order]:
        return (
            db.query(self.model)
            .filter(self.model.order_status == status)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_order(
        self,
        db: Session,
        *,
        customer_id: int,
        order_type: str,
        order_status: str = "pending",
        order_date: Optional[datetime] = None,
    ) -> Order:
        payload = {
            "customer_id": customer_id,
            "order_type": order_type,
            "order_status": order_status,
            "order_date": order_date or datetime.utcnow(),
        }
        return self.create(db, obj_in=payload)

    def create_order_items(self, db: Session, *, order_id: int, items: list[dict[str, Any]]) -> list[OrderItem]:
        created_items: list[OrderItem] = []
        for item in items:
            db_item = OrderItem(
                order_id=order_id,
                item_id=item["item_id"],
                item_name=item["item_name"],
                item_price=Decimal(str(item["unit_price"])),
                item_quantity=int(item["quantity"]),
            )
            db.add(db_item)
            created_items.append(db_item)
        db.commit()
        for db_item in created_items:
            db.refresh(db_item)
        return created_items

    def create_delivery(
        self,
        db: Session,
        *,
        order_id: int,
        delivery_service: str,
        delivery_status: str = "pending",
        delivery_date: Optional[datetime] = None,
    ) -> Delivery:
        db_delivery = Delivery(
            order_id=order_id,
            delivery_service=delivery_service,
            delivery_status=delivery_status,
            delivery_date=delivery_date or datetime.utcnow(),
        )
        db.add(db_delivery)
        db.commit()
        db.refresh(db_delivery)
        return db_delivery

    def get_order_by_id(self, db: Session, *, order_id: int) -> Optional[Order]:
        return (
            db.query(self.model)
            .options(
                joinedload(self.model.order_items),
                joinedload(self.model.delivery),
            )
            .filter(self.model.order_id == order_id)
            .first()
        )

    def update_order_status(self, db: Session, *, order_id: int, order_status: str) -> Optional[Order]:
        order = self.get(db, order_id)
        if order is None:
            return None
        order.order_status = order_status
        db.add(order)
        db.commit()
        db.refresh(order)
        return order


order_repository = OrderRepository(Order)
order_repo = order_repository