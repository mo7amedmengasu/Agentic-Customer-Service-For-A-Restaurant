from typing import List
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.order_item import OrderItem

class OrderItemRepository(BaseRepository[OrderItem]):
    def get_by_order(self, db: Session, *, order_id: int) -> List[OrderItem]:
        return db.query(self.model).filter(self.model.order_id == order_id).all()
        
    def get_by_menu_item(self, db: Session, *, item_id: int) -> List[OrderItem]:
        return db.query(self.model).filter(self.model.item_id == item_id).all()

order_item_repo = OrderItemRepository(OrderItem)
