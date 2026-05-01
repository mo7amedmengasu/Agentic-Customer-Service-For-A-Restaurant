from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.my_agent.nodes.reflection_agent_nodes import (
    generate_response_node,
    revise_response_node,
    route_after_revise,
)
from app.my_agent.states.state import MainState


def build_reflection_agent_graph():
    graph = StateGraph(MainState)
    graph.add_node("generate", generate_response_node)
    graph.add_node("revise", revise_response_node)

    graph.set_entry_point("generate")
    graph.add_edge("generate", "revise")
    graph.add_conditional_edges(
        "revise",
        route_after_revise,
        {"revise": "generate", "accept": END},
    )

    return graph.compile()


reflection_agent_graph = build_reflection_agent_graph()
