from __future__ import annotations

from difflib import get_close_matches
from typing import List, Optional

from sqlalchemy import Tuple, func
from sqlalchemy.orm import Session

from app.models.menu_item import MenuItem
from app.repositories.base import BaseRepository
import numpy as np


class MenuRepository(BaseRepository[MenuItem]):
    @staticmethod
    def _normalize_name(item_name: str) -> str:
        return " ".join(item_name.strip().lower().split())

    def get_by_name(self, db: Session, *, name: str) -> Optional[MenuItem]:
        return db.query(self.model).filter(self.model.item_name.ilike(f"%{name}%")).first()

    def search_by_name(self, db: Session, *, name: str) -> List[MenuItem]:
        return db.query(self.model).filter(self.model.item_name.ilike(f"%{name}%")).all()
    
    def get_all_items(self, db: Session) -> List[MenuItem]:
        """Fetches all menu items from the database."""
        return db.query(self.model).all()

    def search_item_by_name(self, db: Session, *, item_name: str) -> Optional[MenuItem]:
        normalized_name = self._normalize_name(item_name)
        if not normalized_name:
            return None

        exact_match = (
            db.query(self.model)
            .filter(func.lower(self.model.item_name) == normalized_name.lower())
            .first()
        )
        if exact_match is not None:
            return exact_match

        partial_match = (
            db.query(self.model)
            .filter(func.lower(self.model.item_name).contains(normalized_name))
            .first()
        )
        if partial_match is not None:
            return partial_match

        menu_items = db.query(self.model).all()
        item_lookup = {self._normalize_name(item.item_name): item for item in menu_items}
        close_matches = get_close_matches(normalized_name, list(item_lookup.keys()), n=1, cutoff=0.75)
        if close_matches:
            return item_lookup[close_matches[0]]

        return None

    def get_items_by_names(self, db: Session, *, item_names: List[str]) -> List[MenuItem]:
        normalized_names = [self._normalize_name(name) for name in item_names if name and name.strip()]
        if not normalized_names:
            return []

        resolved_items: list[MenuItem] = []
        seen_item_ids: set[int] = set()
        for item_name in normalized_names:
            menu_item = self.search_item_by_name(db, item_name=item_name)
            if menu_item is None or menu_item.item_id in seen_item_ids:
                continue
            resolved_items.append(menu_item)
            seen_item_ids.add(menu_item.item_id)
        return resolved_items

    def get_item_by_id(self, db: Session, *, item_id: int) -> Optional[MenuItem]:
        return db.get(self.model, item_id)

    def check_item_availability(self, db: Session, *, item_id: int) -> bool:
        return self.get_item_by_id(db, item_id=item_id) is not None
    def search_items_by_keyword(self, db: Session, *, keyword: str) -> List[MenuItem]:
        normalized_keyword = self._normalize_name(keyword)

        if not normalized_keyword:
            return []

        matching_items = (
            db.query(self.model)
            .filter(
                func.lower(self.model.item_name).contains(normalized_keyword)
            )
            .all()
        )

        return matching_items
    def get_items_by_category(self, db: Session, *, category: str) -> List[MenuItem]:
   

        if not category or not category.strip():
            return []

        normalized_category = category.strip().lower()

        items = (
            db.query(self.model)
            .filter(func.lower(self.model.category) == normalized_category)
            .all()
        )

        return items
    def filter_by_max_price(self, db: Session, max_price: float) -> List[MenuItem]:
        return db.query(self.model).filter(self.model.item_price <= max_price).all()
        
    def find_top_semantic_matches(
        self, 
        user_embedding: List[float], 
        menu_items: List[MenuItem], 
        menu_embeddings: List[List[float]], 
        top_n: int = 4
        ) -> List[Tuple[float, MenuItem]]:
            """Calculates similarity and returns top matches."""
            scored_items = []
            user_vec = np.array(user_embedding)
        
            for i, item in enumerate(menu_items):
                item_vec = np.array(menu_embeddings[i])
                # Cosine similarity calculation
                score = np.dot(user_vec, item_vec) / (np.linalg.norm(user_vec) * np.linalg.norm(item_vec))
            
                if score > 0.35:
                    scored_items.append((score, item))
        
            scored_items.sort(key=lambda x: x[0], reverse=True)
            return scored_items[:top_n]    


menu_repository = MenuRepository(MenuItem)
menu_item_repo = menu_repository