from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.repositories.menu_repository import menu_repository


def open_db() -> Session:
    return SessionLocal()


def get_full_menu_text(db: Session, *, limit: int = 100) -> str:
    items = menu_repository.get_multi(db, skip=0, limit=limit)
    if not items:
        return "(menu is empty)"
    lines: list[str] = []
    for it in items:
        category = getattr(it, "item_category", None)
        category_str = f" [{category}]" if category else ""
        lines.append(
            f"- {it.item_name}{category_str} (ID {it.item_id}): ${it.item_price}"
        )
    return "\n".join(lines)


def search_menu_text(db: Session, query: str, *, limit: int = 20) -> str:
    matches = menu_repository.search_by_name(db, name=query)
    if not matches:
        return f"No menu items match '{query}'."
    lines: list[str] = []
    for it in matches[:limit]:
        category = getattr(it, "item_category", None)
        category_str = f" [{category}]" if category else ""
        lines.append(
            f"- {it.item_name}{category_str} (ID {it.item_id}): ${it.item_price}"
        )
    return "\n".join(lines)
