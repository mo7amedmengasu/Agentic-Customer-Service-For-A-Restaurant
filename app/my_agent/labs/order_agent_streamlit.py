from __future__ import annotations

import importlib
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")


CONFIRM_WORDS = {"yes", "confirm", "confirmed", "go ahead", "place it", "place the order", "do it"}


def load_order_modules() -> tuple[Any, Any]:
    for module_name in [
        "app.my_agent.tools.order_agent_tools",
        "app.my_agent.nodes.order_agent",
        "app.my_agent.agents.order_agent",
    ]:
        sys.modules.pop(module_name, None)

    order_nodes_module = importlib.import_module("app.my_agent.nodes.order_agent")
    order_agent_module = importlib.import_module("app.my_agent.agents.order_agent")
    return order_nodes_module, order_agent_module


def build_chat_state(customer_id: int = 1, session_id: str = "streamlit-lab") -> dict[str, Any]:
    return {
        "user_message": "",
        "intent": "order",
        "response": None,
        "session_id": session_id,
        "customer_id": customer_id,
        "order_id": None,
        "extracted_order": None,
        "extracted_complaint": None,
        "tool_result": None,
        "next_step": None,
        "order_ready": None,
        "order_confirmed": None,
        "missing_fields": None,
        "invalid_items": None,
        "requires_follow_up": None,
        "needs_human": None,
        "messages": [],
    }


def is_confirmation_message(user_message: str) -> bool:
    lowered = user_message.strip().lower()
    return any(word in lowered for word in CONFIRM_WORDS)


def run_order_turn(state: dict[str, Any], user_message: str, persist_order: bool) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    order_nodes_module, order_agent_module = load_order_modules()

    route_order_agent = order_agent_module.route_order_agent
    order_reasoning_node = order_nodes_module.order_reasoning_node
    extract_order_node = order_nodes_module.extract_order_node
    validate_order_node = order_nodes_module.validate_order_node
    ask_missing_info_node = order_nodes_module.ask_missing_info_node
    calculate_summary_node = order_nodes_module.calculate_summary_node
    ask_confirmation_node = order_nodes_module.ask_confirmation_node
    modify_order_node = order_nodes_module.modify_order_node
    place_order_node = order_nodes_module.place_order_node
    final_response_node = order_nodes_module.final_response_node

    working_state = deepcopy(state)
    working_state["user_message"] = user_message
    working_state["response"] = None
    working_state["next_step"] = None
    working_state["order_confirmed"] = is_confirmation_message(user_message)
    working_state.setdefault("messages", [])
    working_state["messages"].append({"role": "user", "content": user_message})

    trace: list[tuple[str, dict[str, Any]]] = []

    reasoning_result = order_reasoning_node(working_state)
    working_state.update(reasoning_result)
    trace.append(("order_reasoning", deepcopy(reasoning_result)))

    current_step = route_order_agent(working_state)

    while current_step not in {None, "final_response"}:
        if current_step == "extract_order":
            result = extract_order_node(working_state)
        elif current_step == "validate_order":
            result = validate_order_node(working_state)
        elif current_step == "ask_missing_info":
            result = ask_missing_info_node(working_state)
        elif current_step == "calculate_summary":
            result = calculate_summary_node(working_state)
        elif current_step == "ask_confirmation":
            result = ask_confirmation_node(working_state)
        elif current_step == "modify_order":
            result = modify_order_node(working_state)
        elif current_step == "place_order":
            if not persist_order:
                result = {
                    "response": "Place-order step skipped. Enable 'Persist order to database' if you want to write to the database.",
                    "next_step": "final_response",
                }
            else:
                try:
                    result = place_order_node(working_state)
                except Exception as exc:
                    result = {
                        "response": "Place-order step failed.",
                        "tool_result": {
                            "error": type(exc).__name__,
                            "details": str(exc),
                        },
                        "next_step": "final_response",
                    }
        else:
            result = {
                "response": f"Unhandled step: {current_step}",
                "next_step": "final_response",
            }

        working_state.update(result)
        trace.append((current_step, deepcopy(result)))
        current_step = route_order_agent(working_state)

    final_result = final_response_node(working_state)
    working_state.update(final_result)
    trace.append(("final_response", deepcopy(final_result)))
    working_state["messages"].append({"role": "assistant", "content": working_state["response"]})

    return working_state, trace


def initialize_session_state() -> None:
    if "order_agent_state" not in st.session_state:
        st.session_state.order_agent_state = build_chat_state()
    if "order_agent_trace" not in st.session_state:
        st.session_state.order_agent_trace = []
    if "order_agent_chat_log" not in st.session_state:
        st.session_state.order_agent_chat_log = []
    if "order_agent_selected_customer_id" not in st.session_state:
        st.session_state.order_agent_selected_customer_id = st.session_state.order_agent_state.get("customer_id", 1)


def reset_chat(customer_id: int) -> None:
    st.session_state.order_agent_state = build_chat_state(customer_id=customer_id)
    st.session_state.order_agent_trace = []
    st.session_state.order_agent_chat_log = []


def sync_customer_id(customer_id: int) -> None:
    current_customer_id = st.session_state.order_agent_state.get("customer_id")
    if current_customer_id == customer_id:
        return

    reset_chat(customer_id)


def main() -> None:
    st.set_page_config(page_title="Order Agent Tester", layout="wide")
    initialize_session_state()

    st.title("Order Agent Tester")
    st.caption("Use this Streamlit UI to chat with the order agent and inspect state transitions.")

    with st.sidebar:
        st.subheader("Controls")
        customer_id = st.number_input(
            "Customer ID",
            min_value=1,
            step=1,
            key="order_agent_selected_customer_id",
        )
        sync_customer_id(customer_id)
        persist_order = st.checkbox("Persist order to database", value=False)
        show_trace = st.checkbox("Show node trace", value=False)
        if st.button("Reset Conversation", use_container_width=True):
            reset_chat(customer_id)
            st.rerun()

        st.markdown("Current state")
        st.json(st.session_state.order_agent_state)

        if st.session_state.order_agent_trace:
            st.markdown("Last trace")
            st.json([
                {"step": step_name, "result": step_result}
                for step_name, step_result in st.session_state.order_agent_trace
            ])

    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("Chat")
        for message in st.session_state.order_agent_chat_log:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        prompt = st.chat_input("Type your message to the order agent")
        if prompt:
            st.session_state.order_agent_chat_log.append({"role": "user", "content": prompt})
            next_state, trace = run_order_turn(
                st.session_state.order_agent_state,
                prompt,
                persist_order=persist_order,
            )
            st.session_state.order_agent_state = next_state
            st.session_state.order_agent_trace = trace
            st.session_state.order_agent_chat_log.append(
                {"role": "assistant", "content": next_state.get("response") or ""}
            )
            st.rerun()

    with right_col:
        st.subheader("Inspector")
        st.write("Order summary")
        st.json(st.session_state.order_agent_state.get("extracted_order") or {})

        st.write("Tool result")
        st.json(st.session_state.order_agent_state.get("tool_result") or {})

        if show_trace and st.session_state.order_agent_trace:
            st.write("Trace")
            for step_name, step_result in st.session_state.order_agent_trace:
                with st.expander(step_name, expanded=False):
                    st.json(step_result)


if __name__ == "__main__":
    main()