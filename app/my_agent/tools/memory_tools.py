from __future__ import annotations

from typing import Dict

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.core.database import SessionLocal
from app.repositories.user_memory_repository import user_memory_repository


def load_facts(user_id: int) -> Dict[str, str]:
    db = SessionLocal()
    try:
        return user_memory_repository.get_facts_dict(db, user_id=user_id)
    finally:
        db.close()


def save_fact(user_id: int, key: str, value: str) -> None:
    db = SessionLocal()
    try:
        user_memory_repository.upsert(db, user_id=user_id, key=key, value=value)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def render_facts(facts: Dict[str, str]) -> str:
    if not facts:
        return ""
    lines = ", ".join(f"{k}={v}" for k, v in facts.items())
    return f"Customer profile (long-term memory): {lines}."


@tool(
    "remember_user_fact",
    description=(
        "Save a stable fact about the customer that should be remembered "
        "across all future sessions. Use lowercase snake_case keys. "
        "Examples: dietary_restriction=vegetarian, allergy=peanuts, "
        "favorite_dish=margherita_pizza, delivery_address=123 Main St."
    ),
)
def remember_user_fact_tool(
    key: str, value: str, config: RunnableConfig
) -> str:
    user_id = (config.get("configurable") or {}).get("user_id")
    if not user_id:
        return "Cannot save fact: no authenticated user."
    try:
        save_fact(int(user_id), key, value)
        return f"Saved {key}={value!r}."
    except Exception as e:
        return f"Failed to save fact: {e}"
