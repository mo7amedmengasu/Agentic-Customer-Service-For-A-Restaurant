from app.my_agent.tools.faq_tools import find_best_faq, generate_answer
from app.my_agent.states.state import MainState
from app.core.database import SessionLocal




def retrieve_faq_node(state: MainState, db=None):
    if db is not None:
        faq, score = find_best_faq(state["user_message"], db)
    else:
        with SessionLocal() as session:
            faq, score = find_best_faq(state["user_message"], session)
    state["faq"] = faq
    state["tool_result"] = {"score": score}

    return state


def _build_history_context(messages: list) -> str:
    lines = []
    for m in (messages or []):
        if hasattr(m, "type"):
            role = "Customer" if m.type == "human" else "Assistant"
            lines.append(f"{role}: {m.content}")
        elif isinstance(m, dict):
            role = "Customer" if m.get("role") == "user" else "Assistant"
            lines.append(f"{role}: {m.get('content', '')}")
    return "\n".join(lines[-10:])  # last 10 messages


def generate_answer_node(state: MainState):

    if not state["faq"]:
        state["response"] = "Sorry, I couldn't find an answer in the FAQ."
        return state

    history_context = _build_history_context(state.get("messages", []))
    state["response"] = generate_answer(
        question=state["user_message"],
        faq_answer=state["faq"].answer,
        conversation_context=history_context,
    )

    return state




def personalize_node(state: MainState):
    if state["response"]:
        state["response"] += " 😊"

    print("state at the end of graph", state)
    return state