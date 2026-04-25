from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExtractedComplaintPayload(BaseModel):
    complaint_type: str | None = Field(default=None, description="Complaint category like refund_request, late_delivery, wrong_item, damaged_order, missing_item, rude_service, or human_support.")
    description: str | None = Field(default=None, description="Short factual summary of the complaint.")
    order_id: int | None = Field(default=None, description="Referenced order identifier if the user provided one.")
    priority: Literal["low", "medium", "high", "urgent"] | None = Field(default=None)
    requested_action: str | None = Field(default=None, description="What the user wants, such as refund, replacement, status_check, investigation, or human_support.")
    needs_human: bool | None = Field(default=None, description="Whether the issue should be escalated to a human agent.")


class SupportReasoningDecision(BaseModel):
    next_step: Literal[
        "extract_complaint",
        "validate_complaint",
        "ask_missing_info",
        "check_order_context",
        "create_ticket",
        "escalate_to_human",
        "final_response",
    ]
    response: str | None = Field(default=None)