from __future__ import annotations

from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.my_agent.states.state import MainState


_VALID_INTENTS = {"faq", "menu", "order", "support"}


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


class IntentDecision(BaseModel):
    intent: Literal["faq", "menu", "order", "support"]


_SYSTEM_PROMPT = """You are an intent router for a restaurant customer-service
assistant. Read the customer's latest message in light of the conversation
context and choose exactly one route:

- "faq": General restaurant info (hours, location, reservations, parking,
  payment, dress code) and small talk that is not transactional.
- "menu": Anything about the menu itself - what items exist, ingredients,
  prices, recommendations, dietary fit, comparisons. The user is exploring,
  not yet committing to an order.
- "order": The user wants to place a new order, modify or confirm an
  existing order, or check the status / history of their orders. Short
  confirmations like "yes", "place it", "go ahead" while an order is
  pending also belong here.
- "support": Complaints, delivery problems, refunds, escalations to a
  human, anything where the customer is reporting an issue.

Output the route only via the structured tool call."""


def _build_context(state: MainState) -> str:
    parts: list[str] = []
    extracted_order = state.get("extracted_order") or {}
    if extracted_order.get("items"):
        parts.append("There is an in-progress order awaiting follow-up.")
    if state.get("extracted_complaint"):
        parts.append("There is an in-progress complaint awaiting follow-up.")
    if state.get("order_id"):
        parts.append(f"Recent order_id known: {state['order_id']}.")
    if not parts:
        return "No active flow."
    return " ".join(parts)


def classify_intent_node(state: MainState) -> MainState:
    user_message = (state.get("user_message") or "").strip()
    if not user_message:
        state["intent"] = "faq"
        return state

    llm = _get_llm().with_structured_output(IntentDecision)
    decision: IntentDecision = llm.invoke(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "system",
                "content": f"Conversation context: {_build_context(state)}",
            },
            {"role": "user", "content": user_message},
        ]
    )

    intent = decision.intent if decision.intent in _VALID_INTENTS else "faq"
    state["intent"] = intent
    return state
