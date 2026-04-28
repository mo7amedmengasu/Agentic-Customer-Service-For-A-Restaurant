from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.user_memory import UserMemory


class UserMemoryRepository(BaseRepository[UserMemory]):
    def get_all_for_user(self, db: Session, *, user_id: int) -> List[UserMemory]:
        return db.query(self.model).filter(self.model.user_id == user_id).all()

    def get_facts_dict(self, db: Session, *, user_id: int) -> Dict[str, str]:
        return {row.key: row.value for row in self.get_all_for_user(db, user_id=user_id)}

    def get_one(
        self, db: Session, *, user_id: int, key: str
    ) -> Optional[UserMemory]:
        return (
            db.query(self.model)
            .filter(self.model.user_id == user_id, self.model.key == key)
            .first()
        )

    def upsert(
        self, db: Session, *, user_id: int, key: str, value: str
    ) -> UserMemory:
        existing = self.get_one(db, user_id=user_id, key=key)
        if existing:
            existing.value = value
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing
        return self.create(
            db,
            obj_in={"user_id": user_id, "key": key, "value": value},
        )


user_memory_repository = UserMemoryRepository(UserMemory)
