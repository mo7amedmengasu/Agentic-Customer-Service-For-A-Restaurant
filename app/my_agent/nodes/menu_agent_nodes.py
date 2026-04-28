from __future__ import annotations

from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.my_agent.states.state import MainState
from app.my_agent.tools.menu_agent_tools import (
    get_full_menu_text,
    open_db,
    search_menu_text,
)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o-mini", temperature=0.2)


class MenuPlan(BaseModel):
    action: Literal["full_menu", "search", "answer_directly"]
    query: str | None = Field(
        default=None,
        description="Search keyword if action == 'search'.",
    )


_PLAN_PROMPT = """You decide what menu data to fetch to answer the customer.

- "full_menu": fetch the entire menu (use when the customer wants to browse
  or asks broadly).
- "search": pick this when the customer mentions a specific dish, cuisine,
  or keyword. Provide the keyword in `query`.
- "answer_directly": no menu lookup needed (e.g. greeting or generic
  question that doesn't require menu data).

Return only the structured tool call."""


def plan_menu_lookup_node(state: MainState) -> MainState:
    user_message = (state.get("user_message") or "").strip()
    if not user_message:
        state["tool_result"] = {"menu_text": ""}
        return state

    llm = _get_llm().with_structured_output(MenuPlan)
    plan: MenuPlan = llm.invoke(
        [
            {"role": "system", "content": _PLAN_PROMPT},
            {"role": "user", "content": user_message},
        ]
    )

    db = open_db()
    try:
        if plan.action == "full_menu":
            menu_text = get_full_menu_text(db)
        elif plan.action == "search" and plan.query:
            menu_text = search_menu_text(db, plan.query)
        else:
            menu_text = ""
    finally:
        db.close()

    state["tool_result"] = {"menu_text": menu_text, "menu_action": plan.action}
    return state


_ANSWER_PROMPT = """You are a friendly menu assistant for a restaurant.
Use the menu data below as your single source of truth - never invent
items, prices, or descriptions. Keep replies concise and helpful.

If the customer asked for recommendations, factor in any preferences
visible in the conversation.

Menu data:
{menu_text}"""


def answer_menu_question_node(state: MainState) -> MainState:
    user_message = state.get("user_message") or ""
    tool_result = state.get("tool_result") or {}
    menu_text = tool_result.get("menu_text") or "(no menu data fetched)"

    llm = _get_llm()
    resp = llm.invoke(
        [
            {"role": "system", "content": _ANSWER_PROMPT.format(menu_text=menu_text)},
            {"role": "user", "content": user_message},
        ]
    )
    state["response"] = resp.content if isinstance(resp.content, str) else str(resp.content)
    return state
