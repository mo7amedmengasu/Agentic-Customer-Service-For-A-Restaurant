from app.my_agent.nodes.faq_nodes import (
    retrieve_faq_node,
    generate_answer_node,
    personalize_node
)

from app.my_agent.states.state import MainState
from langgraph.graph import StateGraph, END


def build_faq_graph(db):
    graph = StateGraph(MainState)

    # Add nodes
    graph.add_node(
        "retrieve",
        lambda state: retrieve_faq_node(state, db)
    )
    graph.add_node(
        "generate",
        generate_answer_node
    )
    graph.add_node(
        "personalize",
        personalize_node
    )

    # Define flow
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "personalize")
    graph.add_edge("personalize", END)

    return graph.compile()


def faq_agent(question: str, db):
    state: MainState = {
        "user_message": question,
        "intent": None,
        "response": None,
        "session_id": None,
        "customer_id": None,
        "order_id": None,
        "extracted_order": None,
        "extracted_complaint": None,
        "tool_result": None,
        "messages": [],
        "faq": None
    }

    print("fresh state",state)

    faq_graph = build_faq_graph(db)

    result = faq_graph.invoke(state)

    return result