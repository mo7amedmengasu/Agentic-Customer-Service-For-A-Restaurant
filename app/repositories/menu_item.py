from typing import List, Optional
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.menu_item import MenuItem

class MenuItemRepository(BaseRepository[MenuItem]):
    def get_by_name(self, db: Session, *, name: str) -> Optional[MenuItem]:
        return db.query(self.model).filter(self.model.item_name.ilike(f"%{name}%")).first()
        
    def search_by_name(self, db: Session, *, name: str) -> List[MenuItem]:
        return db.query(self.model).filter(self.model.item_name.ilike(f"%{name}%")).all()

menu_item_repo = MenuItemRepository(MenuItem)
