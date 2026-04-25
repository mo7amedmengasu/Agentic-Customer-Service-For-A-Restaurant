from typing import Any, Optional, TypedDict

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
    next_step: str | None
    order_ready: bool | None
    order_confirmed: bool | None
    missing_fields: list[str] | None
    invalid_items: list[dict[str, Any]] | None
    requires_follow_up: bool | None
    needs_human: bool | None
    messages: list
    faq: Optional[FAQ]