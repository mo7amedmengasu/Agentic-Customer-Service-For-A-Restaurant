import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.core.database import get_db
from app.models.user import User
from app.repositories.chat_session_repository import chat_session_repository
from app.repositories.chat_message_repository import chat_message_repository
from app.my_agent.orchestrator import handle_user_message


router = APIRouter()


def _ensure_session_owned(db: Session, session_id: str, user_id: int):
    sess = chat_session_repository.get_for_user(
        db, session_id=session_id, user_id=user_id
    )
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return sess


@router.post(
    "/sessions",
    response_model=schemas.ChatSession,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    body: schemas.ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    now = datetime.now(timezone.utc)
    return chat_session_repository.create(
        db,
        obj_in={
            "session_id": str(uuid.uuid4()),
            "user_id": current_user.user_id,
            "title": body.title,
            "created_at": now,
            "updated_at": now,
        },
    )


@router.get("/sessions", response_model=List[schemas.ChatSession])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    skip = max(skip, 0)
    limit = max(1, min(limit, 100))
    return chat_session_repository.get_by_user(
        db, user_id=current_user.user_id, skip=skip, limit=limit
    )


@router.patch("/sessions/{session_id}", response_model=schemas.ChatSession)
def rename_session(
    session_id: str,
    body: schemas.ChatSessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    session = _ensure_session_owned(db, session_id, current_user.user_id)
    if body.title is not None:
        session.title = body.title
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    _ensure_session_owned(db, session_id, current_user.user_id)
    chat_session_repository.remove(db, id=session_id)
    return None


@router.get(
    "/sessions/{session_id}/messages",
    response_model=List[schemas.ChatMessage],
)
def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    _ensure_session_owned(db, session_id, current_user.user_id)
    rows = chat_message_repository.get_by_session(db, session_id=session_id)
    return rows


@router.post(
    "/sessions/{session_id}/messages",
    response_model=schemas.SendMessageResponse,
)
def send_message(
    session_id: str,
    body: schemas.SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    _ensure_session_owned(db, session_id, current_user.user_id)
    result = handle_user_message(
        db,
        session_id=session_id,
        user_id=current_user.user_id,
        user_message=body.message,
    )
    return schemas.SendMessageResponse(
        response=result["response"],
        session_id=session_id,
        intent=result.get("intent"),
    )
