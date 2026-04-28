from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.my_agent.nodes.menu_agent_nodes import (
    answer_menu_question_node,
    fetch_menu_node,
)
from app.my_agent.states.state import MainState


def build_menu_agent_graph():
    graph = StateGraph(MainState)
    graph.add_node("fetch_menu", fetch_menu_node)
    graph.add_node("answer", answer_menu_question_node)

    graph.set_entry_point("fetch_menu")
    graph.add_edge("fetch_menu", "answer")
    graph.add_edge("answer", END)

    return graph.compile()


menu_agent_graph = build_menu_agent_graph()
