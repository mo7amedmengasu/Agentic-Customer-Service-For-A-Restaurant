from typing import List

from sqlalchemy.orm import Session

from app.models.complaint import Complaint
from app.repositories.base import BaseRepository


class ComplaintRepository(BaseRepository[Complaint]):
    def get_by_order(self, db: Session, *, order_id: int) -> List[Complaint]:
        return db.query(self.model).filter(self.model.order_id == order_id).all()

    def get_open_complaints(self, db: Session) -> List[Complaint]:
        return db.query(self.model).filter(self.model.complaint_status == "open").all()


complaint_repo = ComplaintRepository(Complaint)