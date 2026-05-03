"""
full_agent_streamlit.py
=======================
Streamlit chat interface for the full multi-agent restaurant assistant.

The orchestrator classifies each message and routes it to the correct
sub-agent (menu, order, FAQ, or support).  Conversation history is kept
in st.session_state so the LLM always has full context.

Run from the project root:
    streamlit run app/my_agent/labs/full_agent_streamlit.py
Or from the labs/ directory:
    streamlit run full_agent_streamlit.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

# ── Path setup ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Bella Tavola — AI Assistant",
    page_icon="🍽️",
    layout="centered",
)

# ── Custom CSS (restaurant theme) ─────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Global ── */
    html, body, [class*="css"] { font-family: 'Lato', sans-serif; }
    .stApp { background-color: #FFF8F0; }

    /* ── Header ── */
    .header-box {
        background: linear-gradient(135deg, #6B1A1A 0%, #8B2020 100%);
        color: #C9A84C;
        padding: 1.2rem 1.6rem;
        border-radius: 12px;
        margin-bottom: 1.2rem;
        text-align: center;
    }
    .header-box h1 { margin: 0; font-size: 1.9rem; letter-spacing: 1px; }
    .header-box p  { margin: 0.3rem 0 0; color: #e8d5a3; font-size: 0.9rem; }

    /* ── Intent badge ── */
    .intent-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 99px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 0.4rem;
    }
    .badge-menu    { background: #e8f5e9; color: #2e7d32; }
    .badge-order   { background: #fff3e0; color: #e65100; }
    .badge-faq     { background: #e3f2fd; color: #1565c0; }
    .badge-support { background: #fce4ec; color: #880e4f; }
    .badge-unclear { background: #f3e5f5; color: #4a148c; }
    .badge-none    { background: #eeeeee; color: #616161; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] { background-color: #6B1A1A; }
    [data-testid="stSidebar"] * { color: #FFF8F0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="header-box">
        <h1>🍽️ Bella Tavola</h1>
        <p>Your intelligent restaurant assistant — menu, orders, FAQ & support</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Build / cache the orchestrator graph ──────────────────────────────────────
@st.cache_resource(show_spinner="Loading assistant…")
def init_graph():
    from app.my_agent.workflow import build_main_graph
    return build_main_graph()

graph = init_graph()

# ── Session state defaults ────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []          # list[dict] for UI display

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"streamlit-{uuid.uuid4().hex[:8]}"

if "last_intent" not in st.session_state:
    st.session_state.last_intent = None

if "agent_state" not in st.session_state:
    # Persistent cross-turn state (order fields, complaint fields, etc.)
    st.session_state.agent_state: dict[str, Any] = {}

# ── Sidebar: session info & controls ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🍷 Session Info")
    st.markdown(f"**Thread:** `{st.session_state.thread_id}`")

    intent = st.session_state.last_intent or "—"
    badge_class = f"badge-{intent}" if intent in ("menu", "order", "faq", "support", "unclear") else "badge-none"
    st.markdown(
        f"**Last intent:** <span class='intent-badge {badge_class}'>{intent}</span>",
        unsafe_allow_html=True,
    )

    st.divider()
    st.markdown("### Quick prompts")
    quick_prompts = {
        "📋 Show menu":        "What's on the menu?",
        "🍕 Order pizza":      "I'd like to order a Margherita pizza please",
        "🕐 Opening hours":    "What are your opening hours?",
        "😟 Report issue":     "I have a complaint about my last order",
        "💰 Prices":           "How much does the pasta cost?",
        "📦 Order status":     "What's the status of my order?",
    }
    for label, text in quick_prompts.items():
        if st.button(label, use_container_width=True):
            st.session_state["_quick_prompt"] = text

    st.divider()
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.last_intent = None
        st.session_state.agent_state = {}
        st.session_state.thread_id = f"streamlit-{uuid.uuid4().hex[:8]}"
        st.rerun()

# ── Chat history display ──────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("intent"):
            ic = f"badge-{msg['intent']}"
            st.markdown(
                f"<span class='intent-badge {ic}'>{msg['intent']}</span>",
                unsafe_allow_html=True,
            )
        st.markdown(msg["content"])

# ── Handle quick-prompt injection ────────────────────────────────────────────
prompt = st.chat_input("Ask about the menu, place an order, or get help…")
if "_quick_prompt" in st.session_state:
    prompt = st.session_state.pop("_quick_prompt")

# ── Process message ───────────────────────────────────────────────────────────
if prompt:
    # Show user message immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build LangChain message history for the graph
    history_objects = []
    for m in st.session_state.messages[:-1]:   # exclude the message we just added
        if m["role"] == "user":
            history_objects.append(HumanMessage(content=m["content"]))
        else:
            history_objects.append(AIMessage(content=m["content"]))
    history_objects.append(HumanMessage(content=prompt))

    # Merge persistent cross-turn state with fresh turn fields
    initial_input: dict[str, Any] = {
        **st.session_state.agent_state,
        "messages":              history_objects,
        "user_message":          prompt,
        "intent":                None,
        "response":              None,
        "iteration_count":       0,
        "max_iterations":        3,
        "clarification_attempts": 0,
    }

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                final_state = graph.invoke(initial_input)
            except Exception as exc:
                err_msg = str(exc)
                if "Connection error" in err_msg or "APIConnectionError" in err_msg:
                    friendly = "I couldn't reach the AI service right now. Please check your internet connection and try again."
                elif "AuthenticationError" in err_msg or "invalid_api_key" in err_msg:
                    friendly = "There's an issue with the API key. Please check the configuration."
                elif "RateLimitError" in err_msg:
                    friendly = "The AI service is currently rate-limited. Please wait a moment and try again."
                else:
                    friendly = "Something went wrong on my end. Please try again."
                st.error(friendly)
                st.session_state.messages.append({"role": "assistant", "content": friendly, "intent": "unclear"})
                st.stop()

        response = final_state.get("response") or "I'm sorry, I couldn't process that."
        intent   = final_state.get("intent") or "unclear"

        # Badge above response
        badge_class = f"badge-{intent}"
        st.markdown(
            f"<span class='intent-badge {badge_class}'>{intent}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(response)

        # ── Debug expander ────────────────────────────────────────────────
        with st.expander("🔍 Agent trace", expanded=False):
            col1, col2 = st.columns(2)
            col1.metric("Intent", intent)
            col2.metric("Iterations", final_state.get("iteration_count", 0))

            if final_state.get("extracted_order"):
                st.markdown("**Extracted order:**")
                st.json(final_state["extracted_order"])

            if final_state.get("extracted_complaint"):
                st.markdown("**Extracted complaint:**")
                st.json(final_state["extracted_complaint"])

            if final_state.get("missing_fields"):
                st.warning(f"Missing fields: {final_state['missing_fields']}")

            if final_state.get("needs_human"):
                st.error("⚠️ Escalated to human support")

            st.markdown("**Full state keys:**")
            safe_state = {
                k: v for k, v in final_state.items()
                if k not in ("messages", "faq") and v is not None
            }
            st.json(safe_state)

    # Persist cross-turn state fields (order progress, complaint, etc.)
    PERSISTENT_FIELDS = (
        "extracted_order", "order_id", "order_confirmed",
        "extracted_complaint", "needs_human",
        "customer_id", "session_id",
    )
    for field in PERSISTENT_FIELDS:
        if final_state.get(field) is not None:
            st.session_state.agent_state[field] = final_state[field]

    st.session_state.last_intent = intent
    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "intent": intent,
    })
