from __future__ import annotations

from app.core.database import SessionLocal
from app.my_agent.agents.faq_agent import build_faq_graph
from app.my_agent.states.state import MainState


_TRANSIENT_FIELDS = ("response", "intent", "tool_result", "faq")


def reset_turn_node(state: MainState) -> MainState:
    for key in _TRANSIENT_FIELDS:
        state[key] = None
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


def fallback_response_node(state: MainState) -> MainState:
    if not state.get("response"):
        state["response"] = (
            "Sorry, I couldn't produce a response. Could you rephrase?"
        )
    return state
