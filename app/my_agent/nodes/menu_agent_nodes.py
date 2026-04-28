from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.my_agent.states.state import MainState
from app.my_agent.tools.menu_agent_tools import get_full_menu_text, open_db


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
        temperature=0.2,
    )


def fetch_menu_node(state: MainState) -> MainState:
    db = open_db()
    try:
        menu_text = get_full_menu_text(db)
    finally:
        db.close()
    state["tool_result"] = {"menu_text": menu_text}
    return state


_ANSWER_PROMPT = """You are a friendly menu assistant for a restaurant.
Use the menu data below as your single source of truth - never invent
items, prices, or descriptions.

Apply your culinary knowledge to map customer queries to actual items:
- "pasta" includes spaghetti, fettuccine, penne, linguine, carbonara,
  bolognese, lasagna, etc.
- "vegetarian" means items without meat or fish.
- "drinks" includes sodas, juice, water, coffee.

If the customer asks about a category and items match, list them. If
nothing in the menu fits, say so directly without inventing alternatives.
Keep replies concise.

Menu data:
{menu_text}"""


def answer_menu_question_node(state: MainState) -> MainState:
    user_message = state.get("user_message") or ""
    tool_result = state.get("tool_result") or {}
    menu_text = tool_result.get("menu_text") or "(menu unavailable)"

    llm = _get_llm()
    resp = llm.invoke(
        [
            {"role": "system", "content": _ANSWER_PROMPT.format(menu_text=menu_text)},
            {"role": "user", "content": user_message},
        ]
    )
    state["response"] = (
        resp.content if isinstance(resp.content, str) else str(resp.content)
    )
    return state
