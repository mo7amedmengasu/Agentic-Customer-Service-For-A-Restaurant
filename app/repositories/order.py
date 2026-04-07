from typing import List, Optional
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.order import Order

class OrderRepository(BaseRepository[Order]):
    def get_by_customer(self, db: Session, *, customer_id: int, skip: int = 0, limit: int = 100) -> List[Order]:
        return db.query(self.model).filter(
            self.model.customer_id == customer_id
        ).offset(skip).limit(limit).all()
        
    def get_by_status(self, db: Session, *, status: str, skip: int = 0, limit: int = 100) -> List[Order]:
        return db.query(self.model).filter(
            self.model.order_status == status
        ).offset(skip).limit(limit).all()

order_repo = OrderRepository(Order)
