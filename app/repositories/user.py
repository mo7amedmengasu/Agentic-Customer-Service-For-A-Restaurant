from typing import Optional
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.user import User

class UserRepository(BaseRepository[User]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        return db.query(self.model).filter(self.model.user_email == email).first()
        
    def get_by_phone(self, db: Session, *, phone: str) -> Optional[User]:
        return db.query(self.model).filter(self.model.user_tel == phone).first()

user_repo = UserRepository(User)
