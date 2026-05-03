from __future__ import annotations

"""
Orchestrator Agent
==================
Routes user messages to the correct sub-agent (menu, order, FAQ, support)
after classifying intent.  If intent is unclear it asks the user a
clarifying question and tries again on the next turn.

Graph flow
----------
    START
      │
      ▼
 classify_intent ──┬──► menu_agent    ──► END
                   ├──► order_agent   ──► END
                   ├──► faq_agent     ──► END
                   ├──► support_agent ──► END
                   └──► clarify       ──► END   (returns Q to user)
"""

from langgraph.graph import END, StateGraph

from app.my_agent.nodes.intent_classifier_nodes import (
    clarify_intent_node,
    classify_intent_node,
    route_after_classify,
)
from app.my_agent.states.state import MainState


# ─────────────────────────────────────────────
# Sub-agent wrapper nodes
# ─────────────────────────────────────────────

def _run_menu_agent_node(state: MainState) -> MainState:
    """Invoke the menu sub-agent graph and propagate its response."""
    from app.my_agent.agents.menu_agent import build_menu_graph

    graph = build_menu_graph(db=None)
    # Carry session thread if available so MemorySaver continuity is preserved
    config = {}
    if state.get("session_id"):
        config = {"configurable": {"thread_id": str(state["session_id"])}}
    result = graph.invoke(state, config=config)
    state["response"] = result.get("response") or state.get("response")
    return state


def _run_order_agent_node(state: MainState) -> MainState:
    """Invoke the order sub-agent graph and propagate its response."""
    from app.my_agent.agents.order_agent import build_order_agent_graph

    graph = build_order_agent_graph()
    result = graph.invoke(state)
    state["response"] = result.get("response") or state.get("response")
    # Carry order-related state back
    for field in ("extracted_order", "order_id", "order_confirmed", "next_step"):
        if result.get(field) is not None:
            state[field] = result[field]
    return state


def _run_faq_agent_node(state: MainState) -> MainState:
    """Invoke the FAQ sub-agent graph and propagate its response."""
    from app.my_agent.agents.faq_agent import build_faq_graph

    graph = build_faq_graph(db=None)
    result = graph.invoke(state)
    state["response"] = result.get("response") or state.get("response")
    return state


def _run_support_agent_node(state: MainState) -> MainState:
    """Invoke the support sub-agent graph and propagate its response."""
    from app.my_agent.agents.support_agent import build_support_agent_graph

    graph = build_support_agent_graph()
    result = graph.invoke(state)
    state["response"] = result.get("response") or state.get("response")
    for field in ("extracted_complaint", "needs_human"):
        if result.get(field) is not None:
            state[field] = result[field]
    return state


# ─────────────────────────────────────────────
# Graph builder
# ─────────────────────────────────────────────

def build_orchestrator_graph():
    """
    Build and compile the master orchestrator graph.

    The graph is stateless across invocations (no checkpointer) because
    conversation history is managed externally via the `messages` field
    in MainState, which the chat API reconstructs from the database on
    every turn.
    """
    graph = StateGraph(MainState)

    # ── Nodes ──────────────────────────────────
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("clarify", clarify_intent_node)
    graph.add_node("menu_agent", _run_menu_agent_node)
    graph.add_node("order_agent", _run_order_agent_node)
    graph.add_node("faq_agent", _run_faq_agent_node)
    graph.add_node("support_agent", _run_support_agent_node)

    # ── Entry ───────────────────────────────────
    graph.set_entry_point("classify_intent")

    # ── Routing after classification ────────────
    graph.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {
            "menu":      "menu_agent",
            "order":     "order_agent",
            "faq":       "faq_agent",
            "support":   "support_agent",
            "clarify":   "clarify",
            "gratitude": END,  # canned reply already in state["response"]
            "off_topic": END,  # polite redirect already in state["response"]
        },
    )

    # ── Terminal edges ──────────────────────────
    graph.add_edge("clarify",       END)
    graph.add_edge("menu_agent",    END)
    graph.add_edge("order_agent",   END)
    graph.add_edge("faq_agent",     END)
    graph.add_edge("support_agent", END)

    return graph.compile()
