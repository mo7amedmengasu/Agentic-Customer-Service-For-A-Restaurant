import json
from typing import Dict, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.user_memory_repository import user_memory_repository


def load_user_facts(db: Session, user_id: int) -> Dict[str, str]:
    return user_memory_repository.get_facts_dict(db, user_id=user_id)


def render_facts(facts: Dict[str, str]) -> str:
    if not facts:
        return ""
    lines = "\n".join(f"  - {k}: {v}" for k, v in facts.items())
    return f"Long-term facts known about this customer:\n{lines}"


_EXTRACTION_PROMPT = """You extract durable customer facts from a single
customer message.

Return a JSON array of zero or more {"key": ..., "value": ...} objects.

Rules:
- Only extract STABLE personal traits: dietary_restriction, allergy,
  favorite_dish, favorite_cuisine, delivery_address, name, phone.
- Use lowercase snake_case keys.
- Skip transient mentions ("I'd like a pizza today" is NOT a favorite).
- If nothing qualifies, return [].
- Output ONLY the JSON array. No prose, no markdown fences.

Examples:
  Customer: "I'm vegetarian and allergic to peanuts."
  Output: [{"key": "dietary_restriction", "value": "vegetarian"}, {"key": "allergy", "value": "peanuts"}]

  Customer: "I want a margherita pizza tonight."
  Output: []"""


def extract_facts_from_message(message: str) -> List[Dict[str, str]]:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
        max_tokens=200,
    )
    try:
        response = llm.invoke([
            SystemMessage(content=_EXTRACTION_PROMPT),
            HumanMessage(content=message),
        ])
    except Exception:
        return []

    text = (response.content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    out: List[Dict[str, str]] = []
    for item in parsed:
        if (
            isinstance(item, dict)
            and isinstance(item.get("key"), str)
            and isinstance(item.get("value"), str)
            and item["key"].strip()
            and item["value"].strip()
        ):
            out.append({"key": item["key"].strip().lower(), "value": item["value"].strip()})
    return out


def persist_extracted_facts(
    db: Session, user_id: int, facts: List[Dict[str, str]]
) -> None:
    for f in facts:
        try:
            user_memory_repository.upsert(
                db, user_id=user_id, key=f["key"], value=f["value"]
            )
        except Exception:
            db.rollback()
