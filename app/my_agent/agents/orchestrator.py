from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.my_agent.agents.intent_classifier import intent_classifier_graph
from app.my_agent.agents.menu_agent import menu_agent_graph
from app.my_agent.agents.order_agent import order_agent_graph
from app.my_agent.agents.support_agent import support_agent_graph
from app.my_agent.checkpointer import get_checkpointer
from app.my_agent.nodes.orchestrator_nodes import (
    fallback_response_node,
    faq_branch_node,
    reset_turn_node,
)
from app.my_agent.states.state import MainState


def _route_by_intent(state: MainState) -> str:
    intent = state.get("intent") or "faq"
    if intent in {"faq", "menu", "order", "support"}:
        return intent
    return "faq"


def build_orchestrator_graph(*, with_checkpointer: bool = True):
    graph = StateGraph(MainState)

    graph.add_node("reset_turn", reset_turn_node)
    graph.add_node("classify", intent_classifier_graph)
    graph.add_node("faq", faq_branch_node)
    graph.add_node("menu", menu_agent_graph)
    graph.add_node("order", order_agent_graph)
    graph.add_node("support", support_agent_graph)
    graph.add_node("finalize", fallback_response_node)

    graph.set_entry_point("reset_turn")
    graph.add_edge("reset_turn", "classify")

    graph.add_conditional_edges(
        "classify",
        _route_by_intent,
        {
            "faq": "faq",
            "menu": "menu",
            "order": "order",
            "support": "support",
        },
    )

    graph.add_edge("faq", "finalize")
    graph.add_edge("menu", "finalize")
    graph.add_edge("order", "finalize")
    graph.add_edge("support", "finalize")
    graph.add_edge("finalize", END)

    if with_checkpointer:
        return graph.compile(checkpointer=get_checkpointer())
    return graph.compile()


_orchestrator_graph = None


def get_orchestrator_graph():
    global _orchestrator_graph
    if _orchestrator_graph is None:
        _orchestrator_graph = build_orchestrator_graph(with_checkpointer=True)
    return _orchestrator_graph
