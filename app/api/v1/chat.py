from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.user import User
from app.repositories.chat_session_repository import ChatSessionRepository
from app.my_agent.workflow import build_main_graph
from langchain_core.messages import HumanMessage, AIMessage

router = APIRouter()
chat_repo = ChatSessionRepository()

# One global graph instance; threads are separated by session_id
_graph = None

# In-memory store for persistent agent state between turns within a session
# Key: session_id (int) → dict of persistent state fields
_session_agent_state: Dict[int, dict] = {}

PERSISTENT_FIELDS = (
    "extracted_order", "order_id", "order_confirmed",
    "order_awaiting_confirmation",
    "extracted_complaint", "needs_human",
    "customer_id",
)


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_main_graph()
    return _graph


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SessionOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class SendMessageIn(BaseModel):
    content: str


class CreateSessionIn(BaseModel):
    title: str = "New Chat"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=List[SessionOut])
def list_sessions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return chat_repo.get_sessions_for_user(db, user_id=current_user.user_id)


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    body: CreateSessionIn,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return chat_repo.create_session(db, user_id=current_user.user_id, title=body.title)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    deleted = chat_repo.delete_session(db, session_id=session_id, user_id=current_user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    # Clear cached agent state for this session
    _session_agent_state.pop(session_id, None)


@router.get("/sessions/{session_id}/messages", response_model=List[MessageOut])
def get_messages(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    session = chat_repo.get_session(db, session_id=session_id, user_id=current_user.user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return chat_repo.get_messages(db, session_id=session_id)


@router.post("/sessions/{session_id}/messages", response_model=MessageOut)
def send_message(
    session_id: int,
    body: SendMessageIn,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    session = chat_repo.get_session(db, session_id=session_id, user_id=current_user.user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Save user message
    chat_repo.add_message(db, session_id=session_id, role="user", content=body.content)

    # Auto-title the session from first message
    if session.title == "New Chat":
        short_title = body.content[:50]
        chat_repo.update_session_title(db, session_id=session_id, title=short_title)

    # Build LangChain message history from DB (all messages including the one just saved)
    db_messages = chat_repo.get_messages(db, session_id=session_id)
    history_objects = []
    for m in db_messages:
        if m.role == "user":
            history_objects.append(HumanMessage(content=m.content))
        else:
            history_objects.append(AIMessage(content=m.content))

    # Merge persistent cross-turn state with fresh turn fields (mirrors Streamlit logic)
    persisted = _session_agent_state.get(session_id, {})
    initial_input = {
        **persisted,
        "messages": history_objects,
        "user_message": body.content,
        "customer_id": current_user.user_id,
        "intent": None,
        "response": None,
        "iteration_count": 0,
        "max_iterations": 3,
        "clarification_attempts": 0,
    }

    # Invoke the agent graph
    graph = get_graph()
    try:
        final_state = graph.invoke(initial_input)
    except Exception as exc:
        err_msg = str(exc)
        if "Connection error" in err_msg or "APIConnectionError" in err_msg:
            ai_response = "I couldn't reach the AI service right now. Please check your internet connection and try again."
        elif "AuthenticationError" in err_msg or "invalid_api_key" in err_msg:
            ai_response = "There's an issue with the API key. Please check the server configuration."
        elif "RateLimitError" in err_msg:
            ai_response = "The AI service is currently rate-limited. Please wait a moment and try again."
        else:
            ai_response = "Something went wrong on my end. Please try again."
        saved = chat_repo.add_message(db, session_id=session_id, role="assistant", content=ai_response)
        return saved

    ai_response = final_state.get("response") or "I'm sorry, I couldn't process that."

    # Persist cross-turn state fields for next request
    updated_state = _session_agent_state.get(session_id, {})
    for field in PERSISTENT_FIELDS:
        if final_state.get(field) is not None:
            updated_state[field] = final_state[field]
    _session_agent_state[session_id] = updated_state

    # Save assistant message and return it
    saved = chat_repo.add_message(db, session_id=session_id, role="assistant", content=ai_response)
    return saved
