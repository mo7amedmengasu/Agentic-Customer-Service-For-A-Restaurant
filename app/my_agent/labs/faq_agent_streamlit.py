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

from app.core.database import SessionLocal, init_db
from app.models.faq import FAQ


def load_faq_modules() -> tuple[Any, Any]:
    for module_name in [
        "app.my_agent.tools.faq_tools",
        "app.my_agent.nodes.faq_nodes",
        "app.my_agent.agents.faq_agent",
    ]:
        sys.modules.pop(module_name, None)

    faq_nodes_module = importlib.import_module("app.my_agent.nodes.faq_nodes")
    faq_agent_module = importlib.import_module("app.my_agent.agents.faq_agent")
    return faq_nodes_module, faq_agent_module


def build_chat_state(session_id: str = "faq-streamlit-lab") -> dict[str, Any]:
    return {
        "user_message": "",
        "intent": "faq",
        "response": None,
        "session_id": session_id,
        "customer_id": None,
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
        "faq": None,
    }


def serialize_faq(faq: FAQ | None) -> dict[str, Any] | None:
    if faq is None:
        return None

    return {
        "id": faq.id,
        "question": faq.question,
        "answer": faq.answer,
    }


def get_faq_count() -> int:
    init_db()
    db = SessionLocal()
    try:
        return db.query(FAQ).count()
    finally:
        db.close()


def run_faq_turn(state: dict[str, Any], user_message: str) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    faq_nodes_module, _ = load_faq_modules()

    retrieve_faq_node = faq_nodes_module.retrieve_faq_node
    generate_answer_node = faq_nodes_module.generate_answer_node
    personalize_node = faq_nodes_module.personalize_node

    working_state = deepcopy(state)
    working_state["user_message"] = user_message
    working_state["response"] = None
    working_state.setdefault("messages", [])
    working_state["messages"].append({"role": "user", "content": user_message})

    trace: list[tuple[str, dict[str, Any]]] = []

    init_db()
    db = SessionLocal()
    try:
        retrieve_result = retrieve_faq_node(working_state, db)
        working_state.update(retrieve_result)
        trace.append(
            (
                "retrieve",
                {
                    "faq": serialize_faq(working_state.get("faq")),
                    "tool_result": deepcopy(working_state.get("tool_result")),
                },
            )
        )

        generate_result = generate_answer_node(working_state)
        working_state.update(generate_result)
        trace.append(
            (
                "generate",
                {
                    "response": working_state.get("response"),
                    "faq": serialize_faq(working_state.get("faq")),
                },
            )
        )

        personalize_result = personalize_node(working_state)
        working_state.update(personalize_result)
        trace.append(
            (
                "personalize",
                {
                    "response": working_state.get("response"),
                },
            )
        )
    finally:
        db.close()

    working_state["messages"].append({"role": "assistant", "content": working_state.get("response") or ""})
    return working_state, trace


def initialize_session_state() -> None:
    if "faq_agent_state" not in st.session_state:
        st.session_state.faq_agent_state = build_chat_state()
    if "faq_agent_trace" not in st.session_state:
        st.session_state.faq_agent_trace = []
    if "faq_agent_chat_log" not in st.session_state:
        st.session_state.faq_agent_chat_log = []


def reset_chat() -> None:
    st.session_state.faq_agent_state = build_chat_state()
    st.session_state.faq_agent_trace = []
    st.session_state.faq_agent_chat_log = []


def main() -> None:
    st.set_page_config(page_title="FAQ Agent Tester", layout="wide")
    initialize_session_state()

    st.title("FAQ Agent Tester")
    st.caption("Use this Streamlit UI to chat with the FAQ agent and inspect FAQ retrieval, answer generation, and personalization.")

    with st.sidebar:
        st.subheader("Controls")
        show_trace = st.checkbox("Show node trace", value=False)
        if st.button("Reset Conversation", use_container_width=True):
            reset_chat()
            st.rerun()

        st.metric("FAQ entries", get_faq_count())

        st.markdown("Current state")
        state_snapshot = deepcopy(st.session_state.faq_agent_state)
        state_snapshot["faq"] = serialize_faq(state_snapshot.get("faq"))
        st.json(state_snapshot)

        if st.session_state.faq_agent_trace:
            st.markdown("Last trace")
            st.json([
                {"step": step_name, "result": step_result}
                for step_name, step_result in st.session_state.faq_agent_trace
            ])

    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("Chat")
        for message in st.session_state.faq_agent_chat_log:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        prompt = st.chat_input("Type your message to the FAQ agent")
        if prompt:
            st.session_state.faq_agent_chat_log.append({"role": "user", "content": prompt})
            try:
                next_state, trace = run_faq_turn(st.session_state.faq_agent_state, prompt)
            except Exception as exc:
                next_state = deepcopy(st.session_state.faq_agent_state)
                next_state["response"] = f"FAQ agent failed: {type(exc).__name__}: {exc}"
                trace = [("error", {"error": type(exc).__name__, "details": str(exc)})]

            st.session_state.faq_agent_state = next_state
            st.session_state.faq_agent_trace = trace
            st.session_state.faq_agent_chat_log.append(
                {"role": "assistant", "content": next_state.get("response") or ""}
            )
            st.rerun()

    with right_col:
        st.subheader("Inspector")
        st.write("Matched FAQ")
        st.json(serialize_faq(st.session_state.faq_agent_state.get("faq")) or {})

        st.write("Tool result")
        st.json(st.session_state.faq_agent_state.get("tool_result") or {})

        if show_trace and st.session_state.faq_agent_trace:
            st.write("Trace")
            for step_name, step_result in st.session_state.faq_agent_trace:
                with st.expander(step_name, expanded=False):
                    st.json(step_result)


if __name__ == "__main__":
    main()