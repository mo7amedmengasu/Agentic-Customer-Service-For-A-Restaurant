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
load_dotenv(Path(__file__).resolve().parent / ".env")


def load_support_modules() -> tuple[Any, Any]:
    for module_name in [
        "app.my_agent.tools.support_agent_tools",
        "app.my_agent.nodes.support_agent_nodes",
        "app.my_agent.agents.support_agent",
    ]:
        sys.modules.pop(module_name, None)

    support_nodes_module = importlib.import_module("app.my_agent.nodes.support_agent_nodes")
    support_agent_module = importlib.import_module("app.my_agent.agents.support_agent")
    return support_nodes_module, support_agent_module


def build_chat_state(customer_id: int = 1, session_id: str = "support-streamlit-lab") -> dict[str, Any]:
    return {
        "user_message": "",
        "intent": "support",
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


def run_support_turn(
    state: dict[str, Any],
    user_message: str,
    persist_tickets: bool,
) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    support_nodes_module, support_agent_module = load_support_modules()

    route_support_agent = support_agent_module.route_support_agent
    support_reasoning_node = support_nodes_module.support_reasoning_node
    extract_complaint_node = support_nodes_module.extract_complaint_node
    validate_complaint_node = support_nodes_module.validate_complaint_node
    ask_missing_complaint_info_node = support_nodes_module.ask_missing_complaint_info_node
    check_order_context_node = support_nodes_module.check_order_context_node
    create_ticket_node = support_nodes_module.create_ticket_node
    escalate_to_human_node = support_nodes_module.escalate_to_human_node
    support_response_node = support_nodes_module.support_response_node

    working_state = deepcopy(state)
    working_state["user_message"] = user_message
    working_state["response"] = None
    working_state["next_step"] = None
    working_state.setdefault("messages", [])
    working_state["messages"].append({"role": "user", "content": user_message})

    trace: list[tuple[str, dict[str, Any]]] = []

    reasoning_result = support_reasoning_node(working_state)
    working_state.update(reasoning_result)
    trace.append(("support_reasoning", deepcopy(reasoning_result)))

    current_step = route_support_agent(working_state)

    while current_step not in {None, "final_response"}:
        if current_step == "extract_complaint":
            result = extract_complaint_node(working_state)
        elif current_step == "validate_complaint":
            result = validate_complaint_node(working_state)
        elif current_step == "ask_missing_info":
            result = ask_missing_complaint_info_node(working_state)
        elif current_step == "check_order_context":
            result = check_order_context_node(working_state)
        elif current_step == "create_ticket":
            if not persist_tickets:
                result = {
                    "response": "Ticket creation skipped. Enable 'Persist tickets to database' if you want to create a real support ticket.",
                    "tool_result": {"skipped": True, "step": "create_ticket"},
                    "next_step": "final_response",
                }
            else:
                try:
                    result = create_ticket_node(working_state)
                except Exception as exc:
                    result = {
                        "response": "Ticket creation failed.",
                        "tool_result": {
                            "error": type(exc).__name__,
                            "details": str(exc),
                        },
                        "next_step": "final_response",
                    }
        elif current_step == "escalate_to_human":
            if not persist_tickets:
                result = {
                    "response": "Escalation skipped. Enable 'Persist tickets to database' if you want to create and escalate a real support ticket.",
                    "tool_result": {"skipped": True, "step": "escalate_to_human"},
                    "next_step": "final_response",
                }
            else:
                try:
                    result = escalate_to_human_node(working_state)
                except Exception as exc:
                    result = {
                        "response": "Escalation failed.",
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
        current_step = route_support_agent(working_state)

    final_result = support_response_node(working_state)
    working_state.update(final_result)
    trace.append(("final_response", deepcopy(final_result)))
    working_state["messages"].append({"role": "assistant", "content": working_state.get("response") or ""})

    return working_state, trace


def initialize_session_state() -> None:
    if "support_agent_state" not in st.session_state:
        st.session_state.support_agent_state = build_chat_state()
    if "support_agent_trace" not in st.session_state:
        st.session_state.support_agent_trace = []
    if "support_agent_chat_log" not in st.session_state:
        st.session_state.support_agent_chat_log = []
    if "support_agent_selected_customer_id" not in st.session_state:
        st.session_state.support_agent_selected_customer_id = st.session_state.support_agent_state.get("customer_id", 1)


def reset_chat(customer_id: int) -> None:
    st.session_state.support_agent_state = build_chat_state(customer_id=customer_id)
    st.session_state.support_agent_trace = []
    st.session_state.support_agent_chat_log = []


def sync_customer_id(customer_id: int) -> None:
    current_customer_id = st.session_state.support_agent_state.get("customer_id")
    if current_customer_id == customer_id:
        return

    reset_chat(customer_id)


def main() -> None:
    st.set_page_config(page_title="Support Agent Tester", layout="wide")
    initialize_session_state()

    st.title("Support Agent Tester")
    st.caption("Use this Streamlit UI to chat with the support agent and inspect complaint routing, order context checks, ticket creation, and escalation.")

    with st.sidebar:
        st.subheader("Controls")
        customer_id = st.number_input(
            "Customer ID",
            min_value=1,
            step=1,
            key="support_agent_selected_customer_id",
        )
        sync_customer_id(customer_id)
        persist_tickets = st.checkbox("Persist tickets to database", value=False)
        show_trace = st.checkbox("Show node trace", value=False)
        if st.button("Reset Conversation", use_container_width=True):
            reset_chat(customer_id)
            st.rerun()

        st.markdown("Current state")
        st.json(st.session_state.support_agent_state)

        if st.session_state.support_agent_trace:
            st.markdown("Last trace")
            st.json([
                {"step": step_name, "result": step_result}
                for step_name, step_result in st.session_state.support_agent_trace
            ])

    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("Chat")
        for message in st.session_state.support_agent_chat_log:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        prompt = st.chat_input("Type your message to the support agent")
        if prompt:
            st.session_state.support_agent_chat_log.append({"role": "user", "content": prompt})
            next_state, trace = run_support_turn(
                st.session_state.support_agent_state,
                prompt,
                persist_tickets=persist_tickets,
            )
            st.session_state.support_agent_state = next_state
            st.session_state.support_agent_trace = trace
            st.session_state.support_agent_chat_log.append(
                {"role": "assistant", "content": next_state.get("response") or ""}
            )
            st.rerun()

    with right_col:
        st.subheader("Inspector")
        st.write("Extracted complaint")
        st.json(st.session_state.support_agent_state.get("extracted_complaint") or {})

        st.write("Tool result")
        st.json(st.session_state.support_agent_state.get("tool_result") or {})

        if show_trace and st.session_state.support_agent_trace:
            st.write("Trace")
            for step_name, step_result in st.session_state.support_agent_trace:
                with st.expander(step_name, expanded=False):
                    st.json(step_result)


if __name__ == "__main__":
    main()