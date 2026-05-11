from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.my_agent.states.state import MainState
from app.my_agent.tools.support_agent_tools import (
	create_support_ticket,
	escalate_to_human,
	extract_complaint_from_message,
	get_order_context,
	get_ticket_status,
	validate_complaint,
)

_llm = ChatOpenAI(api_key=settings.OPENAI_API_KEY, model="gpt-4o-mini", temperature=0.3)

_SUPPORT_SYSTEM = """You are an empathetic customer support agent for a restaurant, chatting live with the customer.
Your job is to acknowledge the customer's issue with genuine care, explain what action is being taken,
and reassure them. Always:
- Respond conversationally — you are in a live chat, NOT writing an email.
- Do NOT use email conventions: no "Dear Customer", no "Warm regards", no sign-off, no "Sincerely", no "[Your Name]".
- Start your reply naturally, e.g. "Oh, I'm really sorry to hear that!" or "That's not okay at all — let me help you sort this out."
- Apologise sincerely and reference the specific problem the customer mentioned.
- Keep responses short and to the point (2–4 sentences max unless more detail is genuinely needed).
- Mention keywords that are relevant to the issue: refund, complaint, ticket, resolve, help, etc. where appropriate.
- Do NOT invent order details that were not provided to you."""


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


def _complaint_empathy() -> str:
	return "I understand this was frustrating, and I want to help you sort it out."


def support_reasoning_node(state: MainState) -> dict[str, Any]:
	user_message = state.get("user_message") or ""

	# Handle ticket status requests inline — no complaint extraction needed
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

	# For all other support requests always extract the complaint first
	return {"next_step": "extract_complaint"}


def _build_history_context(messages: list) -> str:
	lines = []
	for m in (messages or []):
		if hasattr(m, "type"):
			role = "Customer" if m.type == "human" else "Assistant"
			lines.append(f"{role}: {m.content}")
		elif isinstance(m, dict):
			role = "Customer" if m.get("role") == "user" else "Assistant"
			lines.append(f"{role}: {m.get('content', '')}")
	return "\n".join(lines[-10:])


def extract_complaint_node(state: MainState) -> dict[str, Any]:
	history_context = _build_history_context(state.get("messages", []))
	complaint = extract_complaint_from_message(
		state.get("user_message") or "",
		existing_complaint=state.get("extracted_complaint"),
		conversation_context=history_context,
	)
	return {
		"extracted_complaint": complaint,
		"tool_result": None,
		"next_step": "validate_complaint",
	}


def validate_complaint_node(state: MainState) -> dict[str, Any]:
	history_context = _build_history_context(state.get("messages", []))
	validation = validate_complaint(
		state.get("extracted_complaint"),
		user_message=state.get("user_message") or "",
		conversation_context=history_context,
	)
	complaint = validation["normalized_complaint"]
	missing_fields = validation["missing_fields"]
	needs_human = validation["needs_human"]

	if missing_fields:
		next_step = "ask_missing_info"
	elif needs_human:
		next_step = "escalate_to_human"
	elif _needs_order_context(complaint):
		next_step = "check_order_context"
	else:
		next_step = "create_ticket"

	return {
		"extracted_complaint": complaint,
		"missing_fields": missing_fields,
		"needs_human": needs_human,
		"tool_result": {"validation": validation},
		"next_step": next_step,
	}


def ask_missing_complaint_info_node(state: MainState) -> dict[str, Any]:
	missing_fields = state.get("missing_fields") or []
	complaint = _normalize_complaint(state.get("extracted_complaint"))
	user_message = state.get("user_message") or ""

	if "what happened" in missing_fields:
		if complaint.get("order_id") is not None:
			order_context = get_order_context(state.get("customer_id"), complaint.get("order_id"))
			if order_context.get("error") in {"order_not_found", "order_not_owned_by_customer"}:
				return {
					"response": "That order is not linked to your account, so I can't help with that complaint.",
					"tool_result": {**(state.get("tool_result") or {}), "order_context": order_context},
					"next_step": "final_response",
				}

	field_prompts = {
		"order_id": "the order ID this complaint is about (you can find it in your order history)",
		"complaint_type": "what type of issue this is (e.g. wrong item, late delivery, rude staff)",
		"description": "a brief description of what happened",
		"what happened": "a bit more detail about what happened",
	}
	missing_desc = " and ".join(
		field_prompts.get(f, f) for f in missing_fields
	) if missing_fields else "a few more details"

	prompt = [
		SystemMessage(content=_SUPPORT_SYSTEM),
		HumanMessage(content=(
			f"Customer message: \"{user_message}\"\n\n"
			f"Complaint extracted so far: {complaint}\n\n"
			f"We still need the following from the customer to proceed: {missing_desc}.\n\n"
			"Write a short, empathetic reply that: (1) sincerely acknowledges their complaint and "
			"references the specific issue they mentioned (wrong food, cold food, late delivery, etc.), "
			"(2) apologises for the inconvenience, and (3) politely asks for the missing information."
		)),
	]
	response = _llm.invoke(prompt)
	return {
		"response": response.content,
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
		return {
			"response": (
				f"{_complaint_empathy()} I've escalated your complaint to a human support agent "
				f"under ticket **#{ticket.get('ticket_id')}**. "
				"Someone from our team will reach out to you shortly. 😊"
			)
		}
	if tool_result.get("ticket"):
		ticket = tool_result["ticket"]
		return {
			"response": (
				f"{_complaint_empathy()} I've opened support ticket **#{ticket['ticket_id']}** for you. "
				"Your complaint is important to us and we'll do our best to resolve it as soon as possible. "
				f"You can reference ticket **#{ticket['ticket_id']}** if you need to follow up. 😊"
			)
		}
	if order_context.get("found"):
		return {"response": f"I checked order {order_context['order_id']}. It is currently {order_context['order_status']}" + (f" and the delivery status is {order_context['delivery_status']}." if order_context.get("delivery_status") else ".")}
	return {"response": "Please tell me what happened, and I’ll help you with it."}
