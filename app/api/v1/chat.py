"""
Chat endpoint — single entry point for the customer chat UI.

"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage

from app.my_agent.memory import create_session_id, build_config
from app.my_agent.workflow import get_graph

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest):

    # Get or create session
    session_id = request.session_id or create_session_id()

    graph = get_graph()
    result = graph.invoke(
        {"messages": [HumanMessage(content=request.message)]},
        config=build_config(session_id),
    )

    ai_message = result["messages"][-1]
    response_text = ai_message.content if hasattr(ai_message, "content") else str(ai_message)

    return ChatResponse(response=response_text, session_id=session_id)
