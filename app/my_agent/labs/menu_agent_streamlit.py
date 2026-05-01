from __future__ import annotations

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
from app.models.menu_item import MenuItem
from app.my_agent.agents.menu_agent import menu_agent


def build_chat_state(session_id: str = "menu-streamlit-lab") -> dict[str, Any]:
    return {
        "user_message": "",
        "intent": "menu",
        "response": None,
        "session_id": session_id,
        "customer_id": None,
        "tool_result": None,
        "next_step": None,
        "messages": [],
        "reflection_satisfied": None,
        "iteration_count": 0,
        "max_iterations": 3,
    }


def get_menu_item_count() -> int:
    init_db()
    db = SessionLocal()
    try:
        return db.query(MenuItem).count()
    finally:
        db.close()


def run_menu_turn(
    state: dict[str, Any],
    user_message: str,
) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:

    init_db()
    db = SessionLocal()

    try:
        result = menu_agent(user_message, db)

        trace = [
            (
                "agent_execution",
                {
                    "tool_result": result.get("tool_result"),
                    "reflection_satisfied": result.get("reflection_satisfied"),
                    "iteration_count": result.get("iteration_count"),
                    "response": result["messages"][-1].content if result.get("messages") else None,
                },
            )
        ]

        return result, trace

    finally:
        db.close()


def initialize_session_state() -> None:
    if "menu_agent_state" not in st.session_state:
        st.session_state.menu_agent_state = build_chat_state()

    if "menu_agent_trace" not in st.session_state:
        st.session_state.menu_agent_trace = []

    if "menu_agent_chat_log" not in st.session_state:
        st.session_state.menu_agent_chat_log = []


def reset_chat() -> None:
    st.session_state.menu_agent_state = build_chat_state()
    st.session_state.menu_agent_trace = []
    st.session_state.menu_agent_chat_log = []


def main() -> None:
    st.set_page_config(
        page_title="Menu Agent Tester",
        layout="wide"
    )

    initialize_session_state()

    st.title("Menu Agent Tester")
    st.caption(
        "Test the LangGraph-powered Menu Agent and inspect tool usage, reflection, and final responses."
    )

    with st.sidebar:
        st.subheader("Controls")

        show_trace = st.checkbox(
            "Show execution trace",
            value=False
        )

        if st.button(
            "Reset Conversation",
            use_container_width=True
        ):
            reset_chat()
            st.rerun()

        st.metric(
            "Menu items in database",
            get_menu_item_count()
        )

        st.markdown("Current State")

        state_snapshot = deepcopy(
            st.session_state.menu_agent_state
        )

        st.json(state_snapshot)

        if st.session_state.menu_agent_trace:
            st.markdown("Last Execution Trace")
            st.json([
                {
                    "step": step_name,
                    "result": step_result
                }
                for step_name, step_result
                in st.session_state.menu_agent_trace
            ])

    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("Chat")

        for message in st.session_state.menu_agent_chat_log:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        prompt = st.chat_input(
            "Ask about menu items..."
        )

        if prompt:
            st.session_state.menu_agent_chat_log.append(
                {
                    "role": "user",
                    "content": prompt
                }
            )

            try:
                next_state, trace = run_menu_turn(
                    st.session_state.menu_agent_state,
                    prompt
                )

            except Exception as exc:
                next_state = deepcopy(
                    st.session_state.menu_agent_state
                )

                next_state["response"] = (
                    f"Menu agent failed: "
                    f"{type(exc).__name__}: {exc}"
                )

                trace = [
                    (
                        "error",
                        {
                            "error": type(exc).__name__,
                            "details": str(exc)
                        }
                    )
                ]

            st.session_state.menu_agent_state = next_state
            st.session_state.menu_agent_trace = trace

            final_response = (
                next_state["messages"][-1].content
                if next_state.get("messages")
                else next_state.get("response") or ""
            )

            st.session_state.menu_agent_chat_log.append(
                {
                    "role": "assistant",
                    "content": final_response
                }
            )

            st.rerun()

    with right_col:
        st.subheader("Inspector")

        st.write("Tool Result")
        st.json(
            st.session_state.menu_agent_state.get("tool_result") or {}
        )

        st.write("Reflection Status")
        st.json({
            "reflection_satisfied":
                st.session_state.menu_agent_state.get(
                    "reflection_satisfied"
                ),
            "iteration_count":
                st.session_state.menu_agent_state.get(
                    "iteration_count"
                ),
        })

        if show_trace and st.session_state.menu_agent_trace:
            st.write("Execution Trace")

            for step_name, step_result in st.session_state.menu_agent_trace:
                with st.expander(
                    step_name,
                    expanded=False
                ):
                    st.json(step_result)


if __name__ == "__main__":
    main()