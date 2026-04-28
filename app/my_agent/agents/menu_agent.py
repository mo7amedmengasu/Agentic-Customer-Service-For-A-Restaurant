from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.my_agent.nodes.menu_agent_nodes import (
    answer_menu_question_node,
    plan_menu_lookup_node,
)
from app.my_agent.states.state import MainState


def build_menu_agent_graph():
    graph = StateGraph(MainState)
    graph.add_node("plan_lookup", plan_menu_lookup_node)
    graph.add_node("answer", answer_menu_question_node)

    graph.set_entry_point("plan_lookup")
    graph.add_edge("plan_lookup", "answer")
    graph.add_edge("answer", END)

    return graph.compile()


menu_agent_graph = build_menu_agent_graph()
