from __future__ import annotations

import time
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIStatusError
from pydantic import BaseModel, Field

from app.my_agent.states.state import MainState


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


# ─────────────────────────────────────────────
# Pydantic schema for structured LLM output
# ─────────────────────────────────────────────
class IntentDecision(BaseModel):
    intent: Literal["menu", "order", "support", "faq", "unclear", "off_topic"] = Field(
        description=(
            "The classified intent of the user message. "
            "'menu' for menu/food/price questions, "
            "'order' for placing or managing orders, "
            "'support' for complaints/refunds/problems, "
            "'faq' for general restaurant questions (hours, location, policies), "
            "'off_topic' for messages completely unrelated to the restaurant (weather, sports, jokes, coding, etc.), "
            "'unclear' when the intent cannot be determined."
        )
    )
    clarifying_question: str | None = Field(
        default=None,
        description="A short friendly question to ask the user when intent is 'unclear'.",
    )


# ─────────────────────────────────────────────
# Helper: build conversation context string
# ─────────────────────────────────────────────
def _build_history_summary(messages: list) -> str:
    if not messages:
        return "(no prior conversation)"
    lines = []
    for m in messages:
        if hasattr(m, "type"):
            role = "Customer" if m.type == "human" else "Assistant"
            lines.append(f"{role}: {m.content}")
        elif isinstance(m, dict):
            role = "Customer" if m.get("role") == "user" else "Assistant"
            lines.append(f"{role}: {m.get('content', '')}")
    return "\n".join(lines[-10:])  # keep last 10 messages for context


# ─────────────────────────────────────────────
# Node: Classify Intent
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# Gratitude / dismissal short-circuit
# ─────────────────────────────────────────────
_GRATITUDE_TOKENS = (
    "thank", "thanks", "thx", "ty",
    "bye", "goodbye", "see you", "later",
    "no all", "all good", "all set", "that's all", "thats all",
    "no thank", "no thanks", "got it", "great",
    "awesome", "perfect", "excellent",
)

def _is_gratitude(user_message: str) -> bool:
    msg = user_message.lower().strip()
    return any(token in msg for token in _GRATITUDE_TOKENS)


def _generate_gratitude_reply(user_message: str, messages: list) -> str:
    history = _build_history_summary(messages)
    system_prompt = (
        "You are a friendly restaurant customer service assistant. "
        "The customer has sent a closing/thank-you message. "
        "Reply warmly and briefly (1-2 sentences). "
        "Use the conversation history to match the tone — "
        "if the customer just had a complaint resolved, be empathetic and reassuring, not cheerful about food. "
        "If it was a casual inquiry, be warm and light. Never suggest enjoying a meal after a complaint. "
        "Do not ask any follow-up questions."
    )
    prompt = f"Conversation history:\n{history}\n\nCustomer's message: \"{user_message}\""
    try:
        reply = _get_llm().invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
        )
        return reply.content.strip()
    except Exception:
        return "You're welcome! Let me know if there's anything else I can help with. 😊"


def classify_intent_node(state: MainState) -> MainState:
    """
    Classifies the user's intent as one of: menu, order, support, faq, unclear.
    If intent is 'unclear' and we've already asked twice, default to 'faq' (general assistant).
    Sets state['intent'] and state['response'] (the clarifying question) if unclear.
    """
    # Short-circuit: gratitude/dismissal → generate context-aware reply
    user_msg = state.get("user_message", "")
    if _is_gratitude(user_msg):
        state["intent"] = "gratitude"
        state["response"] = _generate_gratitude_reply(user_msg, state.get("messages", []))
        return state

    attempts = state.get("clarification_attempts", 0)

    # Safety valve: stop asking after 2 clarification rounds
    if attempts >= 2:
        state["intent"] = "faq"
        return state

    history = _build_history_summary(state.get("messages", []))

    system_prompt = """You are an intent classifier for a restaurant customer service AI.

Classify the customer's latest message into exactly one of these intents:
- "menu"      → questions about menu items, prices, ingredients, availability, recommendations, allergens
- "order"     → placing a new order, modifying or cancelling an order, checking order status
- "support"   → complaints, problems with food or delivery, refund requests, bad experience reports
- "faq"       → general questions: restaurant hours, location, parking, reservation policies, payment methods
- "off_topic" → the message has NOTHING to do with the restaurant or food service (e.g. weather, sports, jokes, programming, math, general knowledge)
- "unclear"   → truly ambiguous; could relate to the restaurant but cannot be mapped to any category above

Be lenient: if the message leans toward a restaurant category, classify it there rather than "unclear".
Use "off_topic" only when the message is clearly unrelated to food/restaurants.
Only use "unclear" when there is genuinely no signal about what the user wants.
When "unclear", provide a short, warm clarifying_question to help determine intent."""

    user_prompt = f"""Conversation history:
{history}

Customer's latest message: "{user_msg}"

Classify the intent."""

    llm = _get_llm()
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            decision: IntentDecision = llm.with_structured_output(IntentDecision).invoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
            )
            break
        except (APIConnectionError, APIStatusError) as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s, 2s back-off
    else:
        raise last_exc  # re-raise after all retries exhausted

    state["intent"] = decision.intent

    if decision.intent == "off_topic":
        state["response"] = (
            "I'm here to help with everything related to our restaurant — "
            "menu, orders, delivery, and general questions. "
            "I'm not able to help with topics outside of that. "
            "Is there anything I can assist you with today? 🍽️"
        )

    if decision.intent == "unclear":
        state["response"] = (
            decision.clarifying_question
            or "I'd love to help! Could you tell me a bit more about what you're looking for? "
               "For example, are you interested in our menu, placing an order, or do you have a question or concern?"
        )

    return state


# ─────────────────────────────────────────────
# Node: Clarify (increment counter, response already set)
# ─────────────────────────────────────────────
def clarify_intent_node(state: MainState) -> MainState:
    """
    Increments the clarification attempt counter.
    The clarifying question is already in state['response'] from classify_intent_node.
    """
    state["clarification_attempts"] = state.get("clarification_attempts", 0) + 1
    return state


# ─────────────────────────────────────────────
# Router function (reads state → returns routing key)
# ─────────────────────────────────────────────
def route_after_classify(state: MainState) -> str:
    """
    Called as a conditional edge after classify_intent_node.
    Returns the routing key for the graph.
    """
    intent = state.get("intent", "unclear")
    if intent == "unclear":
        return "clarify"
    return intent  # "menu" | "order" | "support" | "faq" | "gratitude"
