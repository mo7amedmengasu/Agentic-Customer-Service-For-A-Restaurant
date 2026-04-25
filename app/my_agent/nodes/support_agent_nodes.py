from __future__ import annotations

import re
from typing import Any, Literal

from langchain_openai import ChatOpenAI

from pydantic import BaseModel, Field

from app.my_agent.shcemas.support_agent_schemas import ExtractedComplaintPayload, SupportReasoningDecision
from app.my_agent.states.state import MainState
from app.my_agent.tools.support_agent_tools import (
	create_support_ticket,
	escalate_to_human,
	extract_complaint_from_message,
	get_order_context,
	get_ticket_status,
	validate_complaint,
)


ALLOWED_NEXT_STEPS = {
	"extract_complaint",
	"validate_complaint",
	"ask_missing_info",
	"check_order_context",
	"create_ticket",
	"escalate_to_human",
	"final_response",
}


def _get_llm() -> ChatOpenAI:
	return ChatOpenAI(model="gpt-4o-mini", temperature=0)


def _normalize_complaint(extracted_complaint: dict[str, Any] | None) -> dict[str, Any]:
	payload = dict(extracted_complaint or {})
	payload.setdefault("complaint_type", None)
	payload.setdefault("description", None)
	payload.setdefault("order_id", None)
	payload.setdefault("priority", None)
	payload.setdefault("requested_action", None)
	payload.setdefault("needs_human", None)
	return payload


def _is_ticket_status_request(user_message: str) -> bool:
	lowered = user_message.lower()
	return "ticket" in lowered and any(token in lowered for token in ("status", "update", "progress"))


def _extract_ticket_id(user_message: str) -> int | None:
	match = re.search(r"ticket\s*#?\s*(\d+)", user_message, re.IGNORECASE)
	if match is None:
		return None
	return int(match.group(1))


def _needs_order_context(complaint: dict[str, Any]) -> bool:
	return complaint.get("order_id") is not None and (
		complaint.get("requested_action") in {"refund", "replacement", "status_check"}
		or complaint.get("complaint_type") in {"refund_request", "late_delivery", "wrong_item", "missing_item", "damaged_order", "order_status"}
	)


def _coerce_next_step(state: MainState, proposed_step: str | None) -> str:
	complaint = _normalize_complaint(state.get("extracted_complaint"))
	tool_result = state.get("tool_result") or {}
	missing_fields = state.get("missing_fields") or []
	order_context = tool_result.get("order_context") or {}

	if missing_fields:
		return "ask_missing_info"
	if order_context.get("error") in {"order_not_found", "order_not_owned_by_customer"}:
		return "final_response"
	if complaint.get("needs_human"):
		return "escalate_to_human"
	if tool_result.get("ticket") or tool_result.get("status") == "open":
		return "final_response"
	if _needs_order_context(complaint) and "order_context" not in tool_result:
		return "check_order_context"
	if tool_result.get("order_context", {}).get("found") and complaint.get("requested_action") == "status_check":
		return "final_response"
	if complaint.get("complaint_type") and complaint.get("description"):
		return proposed_step if proposed_step in ALLOWED_NEXT_STEPS else "create_ticket"
	return proposed_step if proposed_step in ALLOWED_NEXT_STEPS else "extract_complaint"


def _fallback_reasoning(state: MainState) -> dict[str, Any]:
	complaint = _normalize_complaint(state.get("extracted_complaint"))
	tool_result = state.get("tool_result") or {}
	order_context = tool_result.get("order_context") or {}

	if _is_ticket_status_request(state.get("user_message") or ""):
		return {"next_step": "final_response"}
	if not complaint.get("complaint_type") and not complaint.get("description"):
		return {"next_step": "extract_complaint"}
	if state.get("missing_fields"):
		return {"next_step": "ask_missing_info"}
	if order_context.get("error") in {"order_not_found", "order_not_owned_by_customer"}:
		return {"next_step": "final_response"}
	if complaint.get("needs_human"):
		return {"next_step": "escalate_to_human"}
	if _needs_order_context(complaint) and "order_context" not in tool_result:
		return {"next_step": "check_order_context"}
	if tool_result.get("order_context", {}).get("found") and complaint.get("requested_action") == "status_check":
		return {"next_step": "final_response"}
	return {"next_step": "create_ticket"}


def _complaint_empathy() -> str:
	return "I understand this was frustrating, and I want to help you sort it out."


def _is_missing_info_follow_up(state: MainState) -> bool:
	missing_fields = state.get("missing_fields") or []
	if not missing_fields:
		return False
	messages = state.get("messages") or []
	return any(message.get("role") == "assistant" for message in messages)


def support_reasoning_node(state: MainState) -> dict[str, Any]:
	user_message = state.get("user_message") or ""
	if _is_ticket_status_request(user_message):
		ticket = get_ticket_status(ticket_id=_extract_ticket_id(user_message), customer_id=state.get("customer_id"))
		if ticket is None or ticket.get("error") == "ticket_not_found":
			return {
				"next_step": "final_response",
				"response": "I couldn't find that support ticket. Please check the ticket ID and try again.",
			}
		if ticket.get("error") == "ticket_not_owned_by_customer":
			return {
				"next_step": "final_response",
				"response": f"Ticket {ticket['ticket_id']} is not linked to your account, so I can't share details for that complaint.",
			}
		return {
			"tool_result": {"ticket": ticket},
			"next_step": "final_response",
			"response": f"Ticket {ticket['ticket_id']} is currently {ticket['status']} with priority {ticket['priority']}.",
		}

	if _is_missing_info_follow_up(state):
		return {
			"next_step": "extract_complaint",
			"response": None,
		}

	prompt = (
		"You are the support orchestration decision maker for a restaurant customer support workflow. "
		"Pick exactly one next_step from the allowed values based on the state. "
		"You must not invent order status, ticket IDs, refund status, or delivery status. Only rely on tool output for those details. "
		"Keep the tone calm and reassuring when you provide a direct response.\n\n"
		f"Allowed next steps: {sorted(ALLOWED_NEXT_STEPS)}\n"
		f"User message: {state.get('user_message')}\n"
		f"Messages: {state.get('messages')}\n"
		f"Extracted complaint: {state.get('extracted_complaint')}\n"
		f"Tool result: {state.get('tool_result')}\n"
		f"Missing fields: {state.get('missing_fields')}\n"
		f"Needs human: {state.get('needs_human')}"
	)

	try:
		decision = _get_llm().with_structured_output(SupportReasoningDecision).invoke(prompt)
		result = decision.model_dump(exclude_none=True)
	except Exception:
		result = _fallback_reasoning(state)

	result["next_step"] = _coerce_next_step(state, result.get("next_step"))
	tool_result = state.get("tool_result") or {}
	complaint = _normalize_complaint(state.get("extracted_complaint"))
	if result["next_step"] == "final_response" and not result.get("response"):
		order_context = tool_result.get("order_context")
		if order_context and order_context.get("found") and complaint.get("requested_action") == "status_check":
			order_status = order_context.get("order_status")
			delivery_status = order_context.get("delivery_status")
			delivery_text = f" Delivery status: {delivery_status}." if delivery_status else ""
			result["response"] = f"Order {order_context['order_id']} is currently {order_status}.{delivery_text}"
		elif tool_result.get("ticket"):
			ticket = tool_result["ticket"]
			result["response"] = f"I've logged your issue as ticket {ticket['ticket_id']}. Its current status is {ticket['status']}."
	return result


def extract_complaint_node(state: MainState) -> dict[str, Any]:
	complaint = extract_complaint_from_message(
		state.get("user_message") or "",
		existing_complaint=state.get("extracted_complaint"),
	)
	return {
		"extracted_complaint": complaint,
		"tool_result": None,
		"next_step": "validate_complaint",
	}


def validate_complaint_node(state: MainState) -> dict[str, Any]:
	validation = validate_complaint(state.get("extracted_complaint"))
	return {
		"extracted_complaint": validation["normalized_complaint"],
		"missing_fields": validation["missing_fields"],
		"needs_human": validation["needs_human"],
		"tool_result": {"validation": validation},
		"next_step": "ask_missing_info" if validation["missing_fields"] else "check_order_context",
	}


def ask_missing_complaint_info_node(state: MainState) -> dict[str, Any]:
	missing_fields = state.get("missing_fields") or []
	complaint = _normalize_complaint(state.get("extracted_complaint"))
	if "what happened" in missing_fields:
		if complaint.get("order_id") is not None:
			order_context = get_order_context(state.get("customer_id"), complaint.get("order_id"))
			if order_context.get("error") in {"order_not_found", "order_not_owned_by_customer"}:
				return {
					"response": "That order is not linked to your account, so I can't help with that complaint.",
					"tool_result": {**(state.get("tool_result") or {}), "order_context": order_context},
					"next_step": "final_response",
				}
			return {
				"response": f"I have order {complaint['order_id']}. Please tell me what happened with it.",
				"tool_result": {**(state.get("tool_result") or {}), "order_context": order_context},
				"next_step": "final_response",
			}
		return {
			"response": "I can help with that. Please tell me what happened, and include the order ID if the issue is tied to a specific order.",
			"next_step": "final_response",
		}
	joined = ", ".join(missing_fields) if missing_fields else "a few complaint details"
	return {
		"response": f"I can help, but I still need {joined} before I can move this forward.",
		"next_step": "final_response",
	}


def check_order_context_node(state: MainState) -> dict[str, Any]:
	complaint = _normalize_complaint(state.get("extracted_complaint"))
	if not _needs_order_context(complaint):
		return {
			"tool_result": {**(state.get("tool_result") or {}), "order_context": {"skipped": True}},
			"next_step": "create_ticket",
		}

	order_context = get_order_context(state.get("customer_id"), complaint.get("order_id"))
	next_step = "final_response" if order_context.get("error") or complaint.get("requested_action") == "status_check" else "create_ticket"
	return {
		"tool_result": {**(state.get("tool_result") or {}), "order_context": order_context},
		"next_step": next_step,
	}


def create_ticket_node(state: MainState) -> dict[str, Any]:
	customer_id = state.get("customer_id")
	if customer_id is None:
		return {
			"response": "I need your customer account before I can create a support ticket.",
			"tool_result": {"error": "missing_customer_id"},
			"next_step": "final_response",
		}

	created_records = create_support_ticket(customer_id, state.get("extracted_complaint") or {})
	return {
		"tool_result": {**(state.get("tool_result") or {}), **created_records},
		"next_step": "final_response",
	}


def escalate_to_human_node(state: MainState) -> dict[str, Any]:
	customer_id = state.get("customer_id")
	if customer_id is None:
		return {
			"response": "I need your customer account before I can escalate this to a human agent.",
			"tool_result": {"error": "missing_customer_id"},
			"next_step": "final_response",
		}

	existing_ticket = (state.get("tool_result") or {}).get("ticket") or {}
	escalation = escalate_to_human(customer_id, state.get("extracted_complaint") or {}, ticket_id=existing_ticket.get("ticket_id"))
	return {
		"needs_human": True,
		"tool_result": {**(state.get("tool_result") or {}), **escalation},
		"next_step": "final_response",
	}


def support_response_node(state: MainState) -> dict[str, Any]:
	if state.get("response"):
		return {"response": state["response"]}

	tool_result = state.get("tool_result") or {}
	order_context = tool_result.get("order_context") or {}
	if order_context.get("error") in {"order_not_found", "order_not_owned_by_customer"}:
		return {"response": "That order is not linked to your account, so I can't share details for that complaint."}
	if tool_result.get("escalated"):
		ticket = tool_result.get("ticket") or {}
		return {"response": f"{_complaint_empathy()} I've escalated this to a human support agent under ticket {ticket.get('ticket_id')}. They will review it as {ticket.get('status')} priority {ticket.get('priority')}."}
	if tool_result.get("ticket"):
		ticket = tool_result["ticket"]
		return {"response": f"{_complaint_empathy()} I created support ticket {ticket['ticket_id']} for you. Its status is {ticket['status']} and priority is {ticket['priority']}."}
	if order_context.get("found"):
		return {"response": f"I checked order {order_context['order_id']}. It is currently {order_context['order_status']}" + (f" and the delivery status is {order_context['delivery_status']}." if order_context.get("delivery_status") else ".")}
	return {"response": "Please tell me what happened, and I’ll help you with it."}
