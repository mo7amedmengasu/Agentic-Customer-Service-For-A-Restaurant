from typing import List, Optional
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.delivery import Delivery

class DeliveryRepository(BaseRepository[Delivery]):
    def get_by_order(self, db: Session, *, order_id: int) -> Optional[Delivery]:
        return db.query(self.model).filter(self.model.order_id == order_id).first()
        
    def get_by_status(self, db: Session, *, status: str, skip: int = 0, limit: int = 100) -> List[Delivery]:
        return db.query(self.model).filter(
            self.model.delivery_status == status
        ).offset(skip).limit(limit).all()

delivery_repo = DeliveryRepository(Delivery)
