from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.repositories.menu_repository import menu_repository


def open_db() -> Session:
    return SessionLocal()


def _format_item(it) -> str:
    parts = [f"- {it.item_name} (ID {it.item_id}): ${it.item_price}"]
    description = getattr(it, "item_description", None)
    if description:
        parts.append(f"  · {description}")
    return "\n".join(parts)


def get_full_menu_text(db: Session, *, limit: int = 100) -> str:
    items = menu_repository.get_multi(db, skip=0, limit=limit)
    if not items:
        return "(menu is empty)"
    return "\n".join(_format_item(it) for it in items)


def search_menu_text(db: Session, query: str, *, limit: int = 20) -> str:
    matches = menu_repository.search_by_name(db, name=query)
    if not matches:
        return f"No menu items match '{query}'."
    return "\n".join(_format_item(it) for it in matches[:limit])
