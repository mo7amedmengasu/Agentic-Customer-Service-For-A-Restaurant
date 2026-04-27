from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)


class ChatSessionUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)


class ChatSession(BaseModel):
    session_id: str
    user_id: int
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)


class SendMessageResponse(BaseModel):
    response: str
    session_id: str
    intent: Optional[str] = None
