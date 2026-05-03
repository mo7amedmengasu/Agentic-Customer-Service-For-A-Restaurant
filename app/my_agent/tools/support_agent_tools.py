from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from langchain_openai import ChatOpenAI

from app.core.database import SessionLocal, init_db
from app.my_agent.shcemas.support_agent_schemas import ComplaintValidationDecision, ExtractedComplaintPayload
from app.repositories.complaint_repository import complaint_repo
from app.repositories.order_repository import order_repository
from app.repositories.support_ticket_repository import support_ticket_repository


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


def _extract_order_id_from_text(user_message: str) -> int | None:
	normalized = user_message.strip()
	patterns = [
		r"(?:order(?:\s+id)?\s*#?\s*)(\d+)",
		r"(?:it is|it's|id is|order is)\s*#?\s*(\d+)",
		r"^#?\s*(\d+)\s*$",
	]
	for pattern in patterns:
		match = re.search(pattern, normalized, re.IGNORECASE)
		if match is not None:
			return int(match.group(1))
	return None


def _serialize_ticket(ticket: Any) -> dict[str, Any]:
	return {
		"ticket_id": ticket.ticket_id,
		"customer_id": ticket.customer_id,
		"order_id": ticket.order_id,
		"complaint_type": ticket.complaint_type,
		"description": ticket.description,
		"priority": ticket.priority,
		"status": ticket.status,
		"requested_action": ticket.requested_action,
		"created_at": None if ticket.created_at is None else ticket.created_at.isoformat(),
		"updated_at": None if ticket.updated_at is None else ticket.updated_at.isoformat(),
	}


def _serialize_complaint(complaint: Any) -> dict[str, Any]:
	return {
		"complaint_id": complaint.complaint_id,
		"customer_id": complaint.customer_id,
		"order_id": complaint.order_id,
		"complaint_type": complaint.complaint_type,
		"description": complaint.description,
		"priority": complaint.priority,
		"complaint_status": complaint.complaint_status,
		"created_at": None if complaint.created_at is None else complaint.created_at.isoformat(),
	}


def extract_complaint_from_message(user_message: str, existing_complaint: dict[str, Any] | None = None, conversation_context: str = "") -> dict[str, Any]:
	base_complaint = _normalize_complaint(existing_complaint)
	history_section = (
		f"\nConversation history (for context):\n{conversation_context}\n"
		if conversation_context.strip()
		else ""
	)
	prompt = (
		"You are extracting a restaurant support complaint from a customer message.\n"
		"Use the conversation history to resolve any references to previous messages.\n"
		"Return: complaint_type, a concise description of what went wrong, order_id (if stated), "
		"priority, requested_action, and whether the customer needs a human agent.\n\n"
		f"{history_section}"
		f"Existing complaint context: {base_complaint}\n"
		f"Customer message: {user_message}"
	)

	try:
		payload = _get_llm().with_structured_output(ExtractedComplaintPayload).invoke(prompt)
		extracted = payload.model_dump(exclude_none=True)
	except Exception:
		extracted = {}

	# Reliable regex fallback for order ID only — everything else is LLM territory
	if extracted.get("order_id") is None:
		extracted["order_id"] = _extract_order_id_from_text(user_message)

	# Use user message as description only when LLM returned nothing at all
	if not extracted.get("description"):
		extracted["description"] = user_message.strip() or None

	merged = _normalize_complaint({**base_complaint, **{k: v for k, v in extracted.items() if v is not None}})
	return merged


def validate_complaint(
	extracted_complaint: dict[str, Any] | None,
	user_message: str = "",
	conversation_context: str = "",
) -> dict[str, Any]:
	complaint = _normalize_complaint(extracted_complaint)

	history_section = (
		f"\nConversation history (for context):\n{conversation_context}\n"
		if conversation_context.strip()
		else ""
	)
	prompt = (
		"You are validating a restaurant support complaint before creating a ticket.\n\n"
		"Rules:\n"
		"- requires_order_id = True for ANY complaint involving a delivery person, a specific order, "
		"or a delivery incident (rude delivery person, late delivery, damaged/wrong/missing item, refund request).\n"
		"  Reason: we need the order ID to identify which delivery or order is being complained about.\n"
		"- requires_order_id = False ONLY if the complaint has zero connection to any specific order "
		"(e.g. rude dine-in waiter with no order reference, website bug, account issue).\n"
		"- needs_human = True only if the customer explicitly asks for a human/manager, or the situation is a safety emergency.\n"
		"- is_description_vague = True if the message gives no specific detail (e.g. 'I have a problem', 'I need help').\n"
		"- Fill in complaint_type, priority, and requested_action if not already set.\n\n"
		f"{history_section}"
		f"Extracted complaint so far: {complaint}\n"
		f"Customer message: {user_message}"
	)

	try:
		decision: ComplaintValidationDecision = (
			_get_llm().with_structured_output(ComplaintValidationDecision).invoke(prompt)
		)
		# Fill in inferred fields only where not already set by extraction
		if not complaint.get("complaint_type") and decision.complaint_type:
			complaint["complaint_type"] = decision.complaint_type
		if not complaint.get("priority"):
			complaint["priority"] = decision.priority
		if not complaint.get("requested_action") and decision.requested_action:
			complaint["requested_action"] = decision.requested_action
		complaint["needs_human"] = decision.needs_human

		missing_fields: list[str] = []
		if decision.is_description_vague:
			missing_fields.append("what happened")
		if decision.requires_order_id and complaint.get("order_id") is None:
			missing_fields.append("order_id")
	except Exception:
		# Hard fallback — require description if nothing useful was captured
		missing_fields = []
		if not (complaint.get("description") or "").strip():
			missing_fields.append("what happened")
		if complaint.get("priority") not in {"low", "medium", "high", "urgent"}:
			complaint["priority"] = "medium"
		complaint.setdefault("needs_human", False)

	return {
		"is_complete": not missing_fields,
		"missing_fields": missing_fields,
		"normalized_complaint": complaint,
		"needs_human": complaint.get("needs_human", False),
	}


def get_order_context(customer_id: int | None, order_id: int | None) -> dict[str, Any]:
	if order_id is None:
		return {"found": False, "error": "missing_order_id"}

	db = SessionLocal()
	try:
		order = order_repository.get_order_by_id(db, order_id=order_id)
		if order is None:
			return {"found": False, "error": "order_not_found", "order_id": order_id}
		if customer_id is not None and order.customer_id != customer_id:
			return {"found": False, "error": "order_not_owned_by_customer", "order_id": order_id}

		return {
			"found": True,
			"order_id": order.order_id,
			"customer_id": order.customer_id,
			"order_type": order.order_type,
			"order_status": order.order_status,
			"delivery_status": None if order.delivery is None else order.delivery.delivery_status,
			"delivery_service": None if order.delivery is None else order.delivery.delivery_service,
			"items": [
				{
					"item_id": item.item_id,
					"item_name": item.item_name,
					"quantity": item.item_quantity,
				}
				for item in order.order_items
			],
		}
	finally:
		db.close()


def create_support_ticket(customer_id: int, complaint: dict[str, Any], status: str = "open") -> dict[str, Any]:
	init_db()
	normalized = _normalize_complaint(complaint)
	db = SessionLocal()
	try:
		description = normalized.get("description") or "Support request"
		complaint_type = normalized.get("complaint_type") or "general_support"
		priority = normalized.get("priority") or "medium"
		created_at = datetime.utcnow()

		db_complaint = complaint_repo.create(
			db,
			obj_in={
				"customer_id": customer_id,
				"order_id": normalized.get("order_id"),
				"complaint_type": complaint_type,
				"description": description,
				"priority": priority,
				"complaint_status": status,
				"created_at": created_at,
			},
		)

		ticket = support_ticket_repository.create(
			db,
			obj_in={
				"customer_id": customer_id,
				"order_id": normalized.get("order_id"),
				"complaint_type": complaint_type,
				"description": description,
				"priority": priority,
				"status": status,
				"requested_action": normalized.get("requested_action"),
				"created_at": created_at,
				"updated_at": created_at,
			},
		)
		return {
			"ticket": _serialize_ticket(ticket),
			"complaint": _serialize_complaint(db_complaint),
		}
	finally:
		db.close()


def escalate_to_human(customer_id: int, complaint: dict[str, Any], ticket_id: int | None = None) -> dict[str, Any]:
	init_db()
	db = SessionLocal()
	try:
		ticket = None if ticket_id is None else support_ticket_repository.update_status(db, ticket_id=ticket_id, status="escalated")
		if ticket is None:
			ticket_payload = create_support_ticket(customer_id, complaint, status="escalated")
			return {
				**ticket_payload,
				"escalated": True,
				"queue": "human_support",
			}

		return {
			"ticket": _serialize_ticket(ticket),
			"escalated": True,
			"queue": "human_support",
		}
	finally:
		db.close()


def get_ticket_status(ticket_id: int | None = None, customer_id: int | None = None) -> dict[str, Any] | None:
	init_db()
	db = SessionLocal()
	try:
		ticket = None
		if ticket_id is not None:
			ticket = support_ticket_repository.get(db, ticket_id)
		elif customer_id is not None:
			ticket = support_ticket_repository.get_latest_by_customer(db, customer_id=customer_id)

		if ticket is None:
			return {"found": False, "error": "ticket_not_found", "ticket_id": ticket_id}
		if customer_id is not None and ticket.customer_id != customer_id:
			return {"found": False, "error": "ticket_not_owned_by_customer", "ticket_id": ticket.ticket_id}
		return {"found": True, **_serialize_ticket(ticket)}
	finally:
		db.close()
