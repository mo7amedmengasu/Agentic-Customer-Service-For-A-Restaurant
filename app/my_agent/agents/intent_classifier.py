from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.my_agent.nodes.intent_classifier_nodes import classify_intent_node
from app.my_agent.states.state import MainState


def build_intent_classifier_graph():
    graph = StateGraph(MainState)
    graph.add_node("classify", classify_intent_node)
    graph.set_entry_point("classify")
    graph.add_edge("classify", END)
    return graph.compile()


intent_classifier_graph = build_intent_classifier_graph()
