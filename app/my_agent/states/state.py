from typing import Optional, TypedDict

from app.models.faq import FAQ

class MainState(TypedDict):
    user_message: str
    intent: str | None
    response: str | None
    session_id: str | None
    customer_id: int | None
    order_id: int | None
    extracted_order: dict | None
    extracted_complaint: dict | None
    tool_result: dict | None
    messages: list
    faq: Optional[FAQ]