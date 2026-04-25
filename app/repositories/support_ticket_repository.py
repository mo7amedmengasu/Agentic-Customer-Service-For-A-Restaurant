from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.support_ticket import SupportTicket
from app.repositories.base import BaseRepository


class SupportTicketRepository(BaseRepository[SupportTicket]):
    def get_by_order(self, db: Session, *, order_id: int) -> list[SupportTicket]:
        return db.query(self.model).filter(self.model.order_id == order_id).all()

    def get_by_status(self, db: Session, *, status: str) -> list[SupportTicket]:
        return db.query(self.model).filter(self.model.status == status).all()

    def get_latest_by_customer(self, db: Session, *, customer_id: int) -> Optional[SupportTicket]:
        return (
            db.query(self.model)
            .filter(self.model.customer_id == customer_id)
            .order_by(self.model.created_at.desc(), self.model.ticket_id.desc())
            .first()
        )

    def update_status(self, db: Session, *, ticket_id: int, status: str) -> Optional[SupportTicket]:
        ticket = self.get(db, ticket_id)
        if ticket is None:
            return None
        ticket.status = status
        ticket.updated_at = datetime.utcnow()
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket


support_ticket_repository = SupportTicketRepository(SupportTicket)