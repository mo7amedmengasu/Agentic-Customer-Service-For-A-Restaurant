from typing import List

from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    def get_by_order(self, db: Session, *, order_id: int) -> List[Transaction]:
        return db.query(self.model).filter(self.model.order_id == order_id).all()

    def get_by_type(self, db: Session, *, tx_type: str, skip: int = 0, limit: int = 100) -> List[Transaction]:
        return db.query(self.model).filter(self.model.tx_type == tx_type).offset(skip).limit(limit).all()


transaction_repo = TransactionRepository(Transaction)