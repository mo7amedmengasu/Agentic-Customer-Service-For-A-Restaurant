from app.my_agent.tools.faq_tools import find_best_faq, generate_answer
from app.my_agent.states.state import MainState




def retrieve_faq_node(state: MainState, db):
    faq, score = find_best_faq(state["user_message"], db)
    state["faq"] = faq
    state["tool_result"] = {"score": score}

    return state


def generate_answer_node(state: MainState):

    if not state["faq"]:
        state["response"] = "Sorry, I couldn't find an answer in the FAQ."
        return state

    state["response"] = generate_answer(
        question=state["user_message"],
        faq_answer=state["faq"].answer
    )

    return state




def personalize_node(state: MainState):
    if state["response"]:
        state["response"] += " 😊"

    print("state at the end of graph", state)
    return state