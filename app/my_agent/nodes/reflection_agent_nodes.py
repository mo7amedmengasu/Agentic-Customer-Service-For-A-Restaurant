from __future__ import annotations

from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.my_agent.states.state import MainState


MAX_REFLECTION_ATTEMPTS = 3


def _get_llm(temperature: float = 0.2) -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
        temperature=temperature,
    )


_REWRITE_PROMPT = """You are a response reviser for a restaurant assistant.
You receive the customer's question, the current draft answer, and a
critique. Rewrite the answer to address the critique while keeping all
factual claims (prices, IDs, totals, order numbers, ticket numbers,
confirmations) EXACTLY the same as in the draft. Do not invent new facts.
Keep the response concise and friendly."""


def generate_response_node(state: MainState) -> MainState:
    feedback = state.get("reflection_feedback")
    if not feedback:
        return state

    user_message = state.get("user_message") or ""
    draft = state.get("response") or ""

    llm = _get_llm(temperature=0.2)
    response = llm.invoke(
        [
            {"role": "system", "content": _REWRITE_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Customer message: {user_message}\n\n"
                    f"Current draft: {draft}\n\n"
                    f"Critique: {feedback}\n\n"
                    "Rewrite the answer."
                ),
            },
        ]
    )
    new_response = response.content if isinstance(response.content, str) else str(response.content)
    state["response"] = new_response.strip() or draft
    state["reflection_feedback"] = None
    return state


class ReviseVerdict(BaseModel):
    verdict: Literal["accept", "revise"]
    critique: str = Field(
        default="",
        description=(
            "If verdict is 'revise', a short, concrete critique describing what "
            "must change. Empty when verdict is 'accept'."
        ),
    )


_REVISE_PROMPT = """You are a strict reviewer of a restaurant assistant's
draft reply. Decide whether the draft is logical, helpful, and on-topic
for the customer's message.

Accept the draft when:
- It directly addresses what the customer asked.
- It contains no obvious factual contradictions or hallucinations.
- It does not promise things the assistant can't actually deliver.
- A confirmation prompt for an order or complaint is fine - leave it
  alone.

Revise only when:
- The reply is irrelevant, illogical, contradictory, or fails to address
  the customer.
- Crucial information is missing.

When revising, give one short critique sentence describing what must
change - do NOT rewrite the answer yourself. Output via the structured
tool call."""


def revise_response_node(state: MainState) -> MainState:
    attempts = state.get("reflection_attempts") or 0
    response_text = (state.get("response") or "").strip()
    user_message = state.get("user_message") or ""
    intent = state.get("intent")

    if intent == "faq":
        state["reflection_decision"] = "accept"
        state["reflection_feedback"] = None
        return state

    if not response_text or attempts >= MAX_REFLECTION_ATTEMPTS:
        state["reflection_decision"] = "accept"
        state["reflection_feedback"] = None
        return state

    llm = _get_llm(temperature=0).with_structured_output(ReviseVerdict)
    verdict: ReviseVerdict = llm.invoke(
        [
            {"role": "system", "content": _REVISE_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Customer message:\n{user_message}\n\n"
                    f"Draft answer:\n{response_text}"
                ),
            },
        ]
    )

    if verdict.verdict == "accept":
        state["reflection_decision"] = "accept"
        state["reflection_feedback"] = None
        return state

    state["reflection_decision"] = "revise"
    state["reflection_feedback"] = verdict.critique or "The reply needs improvement."
    state["reflection_attempts"] = attempts + 1
    return state


def route_after_revise(state: MainState) -> str:
    decision = state.get("reflection_decision") or "accept"
    return "revise" if decision == "revise" else "accept"
