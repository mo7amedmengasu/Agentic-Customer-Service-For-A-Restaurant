from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pathlib import Path

from langgraph.graph import END, StateGraph

from app.my_agent.agents.menu_agent import menu_agent_graph
from app.my_agent.agents.order_agent import order_agent_graph
from app.my_agent.agents.reflection_agent import reflection_agent_graph
from app.my_agent.agents.support_agent import support_agent_graph
from app.my_agent.checkpointer import get_checkpointer
from app.my_agent.nodes.memory_nodes import extract_facts_node
from app.my_agent.nodes.orchestrator_nodes import (
    faq_branch_node,
    finalize_node,
    orchestrator_node,
)
from app.my_agent.states.state import MainState


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.2, max_tokens=500)


def _route_by_intent(state: MainState) -> str:
    intent = state.get("intent") or "faq"
    if intent in {"faq", "menu", "order", "support"}:
        return intent
    return "faq"


def build_main_graph(*, with_checkpointer: bool = True):
    graph = StateGraph(MainState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("faq", faq_branch_node)
    graph.add_node("menu", menu_agent_graph)
    graph.add_node("order", order_agent_graph)
    graph.add_node("support", support_agent_graph)
    graph.add_node("extract_memory", extract_facts_node)
    graph.add_node("reflection", reflection_agent_graph)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        _route_by_intent,
        {
            "faq": "faq",
            "menu": "menu",
            "order": "order",
            "support": "support",
        },
    )

    graph.add_edge("faq", "extract_memory")
    graph.add_edge("menu", "extract_memory")
    graph.add_edge("order", "extract_memory")
    graph.add_edge("support", "extract_memory")
    graph.add_edge("extract_memory", "reflection")
    graph.add_edge("reflection", "finalize")
    graph.add_edge("finalize", END)

    if with_checkpointer:
        return graph.compile(checkpointer=get_checkpointer())
    return graph.compile()


_main_graph = None


def get_main_graph():
    global _main_graph
    if _main_graph is None:
        _main_graph = build_main_graph(with_checkpointer=True)
    return _main_graph
