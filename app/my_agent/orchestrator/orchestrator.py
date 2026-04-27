from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.my_agent.agents.faq_agent import faq_agent
from app.my_agent.agents.order_agent import order_agent_graph
from app.my_agent.agents.support_agent import support_agent_graph
from app.my_agent.states.state import MainState
from app.repositories.chat_session_repository import chat_session_repository
from app.repositories.chat_message_repository import chat_message_repository

from .intent import classify_intent
from .memory import (
    extract_facts_from_message,
    load_user_facts,
    persist_extracted_facts,
    render_facts,
)


_FALLBACK_RESPONSE = (
    "Sorry — I couldn't produce a response. Please rephrase or try again."
)
_RECENT_MESSAGES_FOR_CONTEXT = 12


def _empty_state(session_id: str, customer_id: int) -> MainState:
    return {
        "user_message": "",
        "intent": None,
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
        "faq": None,
    }


def _serialize_state(state: Dict[str, Any]) -> str:
    safe: Dict[str, Any] = {}
    for k, v in state.items():
        if k == "faq":
            continue
        try:
            json.dumps(v)
            safe[k] = v
        except (TypeError, ValueError):
            safe[k] = None
    return json.dumps(safe)


def _deserialize_state(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _attach_facts_to_message(message: str, facts: Dict[str, str]) -> str:
    rendered = render_facts(facts)
    if not rendered:
        return message
    return f"[CONTEXT]\n{rendered}\n[/CONTEXT]\n\n{message}"


def _load_recent_messages(db: Session, session_id: str) -> list[dict]:
    rows = chat_message_repository.get_by_session(db, session_id=session_id)
    if len(rows) > _RECENT_MESSAGES_FOR_CONTEXT:
        rows = rows[-_RECENT_MESSAGES_FOR_CONTEXT:]
    return [{"role": r.role, "content": r.content} for r in rows]


def _run_agent(intent: str, state: MainState, db: Session) -> MainState:
    if intent == "faq":
        result = faq_agent(state["user_message"], db)
        merged = dict(state)
        merged.update(
            {
                "response": result.get("response"),
                "faq": result.get("faq"),
            }
        )
        return merged

    if intent == "order":
        return order_agent_graph.invoke(state)

    if intent == "support":
        return support_agent_graph.invoke(state)

    return state


def _try_run_agent(intent: str, state: MainState, db: Session, attempts: int = 2):
    last_error: Optional[Exception] = None
    for _ in range(attempts):
        try:
            return _run_agent(intent, state, db), None
        except Exception as e:
            last_error = e
    return None, last_error


def handle_user_message(
    db: Session,
    *,
    session_id: str,
    user_id: int,
    user_message: str,
) -> Dict[str, Any]:
    session = db.get(chat_session_repository.model, session_id)
    if session is None:
        raise ValueError("Session not found")

    chat_message_repository.append(
        db, session_id=session_id, role="user", content=user_message
    )

    facts = load_user_facts(db, user_id)
    intent = classify_intent(user_message)

    persisted = _deserialize_state(session.state_json)
    state: MainState = _empty_state(session_id, user_id)
    state.update(persisted)
    state["session_id"] = session_id
    state["customer_id"] = user_id
    state["intent"] = intent
    state["user_message"] = _attach_facts_to_message(user_message, facts)
    state["messages"] = _load_recent_messages(db, session_id)

    result_state, error = _try_run_agent(intent, state, db, attempts=2)

    if result_state is None:
        return {
            "response": (
                "Sorry — I had trouble processing that. "
                f"({type(error).__name__}). Please try again."
            ),
            "intent": intent,
        }

    response_text = (result_state.get("response") or "").strip()
    if not response_text:
        response_text = _FALLBACK_RESPONSE

    chat_message_repository.append(
        db, session_id=session_id, role="assistant", content=response_text
    )

    chat_session_repository.save_state(
        db,
        session_id=session_id,
        state_json=_serialize_state(result_state),
    )

    new_facts = extract_facts_from_message(user_message)
    if new_facts:
        persist_extracted_facts(db, user_id, new_facts)

    if not session.title:
        title = user_message.strip().splitlines()[0]
        if len(title) > 60:
            title = title[:57].rstrip() + "..."
        session.title = title or "New chat"
        db.add(session)
        db.commit()

    return {"response": response_text, "intent": intent}
