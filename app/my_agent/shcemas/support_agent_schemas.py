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


class ComplaintValidationDecision(BaseModel):
    is_description_vague: bool = Field(
        description=(
            "True if the description does not explain what specifically went wrong. "
            "Examples of vague: 'I have a problem', 'I need to complain', 'I have an issue'. "
            "Examples of specific: 'delivery man was rude', 'wrong item delivered', 'my food was cold'."
        )
    )
    requires_order_id: bool = Field(
        description=(
            "True if an order ID is needed to investigate or process this complaint. "
            "Set True for: delivery issues (rude delivery person, late delivery, damaged food, wrong/missing item, refund). "
            "Any complaint involving a delivery person ALWAYS requires an order ID to identify which delivery it refers to. "
            "Set False ONLY for complaints with zero connection to a specific order: "
            "e.g. rude in-restaurant staff (dine-in), general website feedback, account/billing issues."
        )
    )
    needs_human: bool = Field(
        description=(
            "True ONLY if the user explicitly asked to speak to a human/manager/agent, "
            "or the situation is a safety emergency. "
            "Do NOT set True just because the complaint is serious (e.g. rude staff, wrong item) — "
            "those are handled normally via a support ticket."
        )
    )
    complaint_type: str | None = Field(
        default=None,
        description=(
            "Best-fit category: refund_request, late_delivery, wrong_item, missing_item, "
            "damaged_order, rude_service, order_status, human_support, general_support."
        )
    )
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        description=(
            "Priority level. Use 'urgent' if the user signals emergency or extreme distress. "
            "'high' for financial issues or explicit anger. 'medium' for most complaints. "
            "'low' for minor feedback."
        )
    )
    requested_action: str | None = Field(
        default=None,
        description="What the user wants: refund, replacement, status_check, investigation, human_support."
    )


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