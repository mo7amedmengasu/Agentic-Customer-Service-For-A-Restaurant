from app.my_agent.nodes.faq_nodes import (
    retrieve_faq_node,
    generate_answer_node,
    personalize_node
)

from app.my_agent.states.state import MainState


def faq_agent(question: str, db):
    # 1. Initialize shared state
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

    # 2. Run pipeline (your "graph")
    state = retrieve_faq_node(state, db)
    state = generate_answer_node(state)
    state = personalize_node(state)

    # 3. Return final output
    return state