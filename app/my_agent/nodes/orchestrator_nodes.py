from __future__ import annotations

from typing import Literal

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import SessionLocal
from app.my_agent.agents.faq_agent import build_faq_graph
from app.my_agent.states.state import MainState
from app.my_agent.tools.memory_tools import load_facts, render_facts


_VALID_INTENTS = {"faq", "menu", "order", "support"}
_TRANSIENT_FIELDS = ("response", "intent", "tool_result", "faq")


class IntentDecision(BaseModel):
    intent: Literal["faq", "menu", "order", "support"]


_ROUTER_PROMPT = """You are the central router for a restaurant
customer-service assistant. Read the customer's latest message in light of
the conversation context and pick exactly ONE route:

- "faq": general restaurant info (hours, location, reservations, parking,
  payment, dress code) and small talk that's not transactional.
- "menu": anything about the menu - dishes, ingredients, prices,
  recommendations, dietary fit. The customer is browsing, not yet
  committing.
- "order": placing a new order, modifying or confirming one, checking
  status / history. Short confirmations like "yes" / "place it" while an
  order is pending also belong here.
- "support": complaints, delivery problems, refunds, escalations,
  anything where the customer is reporting an issue.

Output via the structured tool call only."""


def _classify_intent(user_message: str, state: MainState) -> str:
    extracted_order = state.get("extracted_order") or {}
    hints: list[str] = []
    if extracted_order.get("items"):
        hints.append("There is an in-progress order awaiting follow-up.")
    if state.get("extracted_complaint"):
        hints.append("There is an in-progress complaint.")
    context = " ".join(hints) if hints else "No active flow."

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
    ).with_structured_output(IntentDecision)

    decision: IntentDecision = llm.invoke(
        [
            {"role": "system", "content": _ROUTER_PROMPT},
            {"role": "system", "content": f"Conversation context: {context}"},
            {"role": "user", "content": user_message},
        ]
    )
    intent = decision.intent if decision.intent in _VALID_INTENTS else "faq"
    return intent


def orchestrator_node(state: MainState, config: RunnableConfig) -> MainState:
    for key in _TRANSIENT_FIELDS:
        state[key] = None

    user_id = (
        state.get("customer_id")
        or (config.get("configurable") or {}).get("user_id")
    )
    if user_id:
        facts = load_facts(int(user_id))
        rendered = render_facts(facts)
        if rendered:
            user_message = state.get("user_message") or ""
            state["user_message"] = f"[{rendered}]\n\n{user_message}"

    user_message = (state.get("user_message") or "").strip()
    if not user_message:
        state["intent"] = "faq"
        return state

    state["intent"] = _classify_intent(user_message, state)
    return state


def faq_branch_node(state: MainState) -> MainState:
    db = SessionLocal()
    try:
        graph = build_faq_graph(db)
        result = graph.invoke(state)
    finally:
        db.close()

    state["response"] = result.get("response")
    state["faq"] = None
    return state


def finalize_node(state: MainState) -> MainState:
    if not state.get("response"):
        state["response"] = (
            "Sorry, I couldn't produce a response. Could you rephrase?"
        )
    return state
