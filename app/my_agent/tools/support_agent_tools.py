from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from langchain_openai import ChatOpenAI

from app.core.database import SessionLocal, init_db
from app.my_agent.shcemas.support_agent_schemas import ExtractedComplaintPayload
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


def _infer_complaint_type(user_message: str) -> str | None:
	lowered = user_message.lower()
	if any(token in lowered for token in ("refund", "money back", "chargeback")):
		return "refund_request"
	if any(token in lowered for token in ("late", "delayed", "still not here")):
		return "late_delivery"
	if any(token in lowered for token in ("wrong item", "incorrect item", "not what i ordered")):
		return "wrong_item"
	if any(token in lowered for token in ("missing item", "missing", "left out")):
		return "missing_item"
	if any(token in lowered for token in ("damaged", "cold", "spoiled", "bad quality")):
		return "damaged_order"
	if any(token in lowered for token in ("human", "manager", "agent", "person")):
		return "human_support"
	if any(token in lowered for token in ("where is my order", "order status", "delivery status")):
		return "order_status"
	if any(token in lowered for token in ("complaint", "problem", "issue", "help")):
		return "general_support"
	return None


def _infer_requested_action(user_message: str) -> str | None:
	lowered = user_message.lower()
	if any(token in lowered for token in ("refund", "money back")):
		return "refund"
	if any(token in lowered for token in ("replace", "replacement", "send another")):
		return "replacement"
	if any(token in lowered for token in ("where is my order", "order status", "delivery status", "track")):
		return "status_check"
	if any(token in lowered for token in ("human", "manager", "agent", "person")):
		return "human_support"
	if any(token in lowered for token in ("help", "support", "complaint")):
		return "investigation"
	return None


def _infer_priority(user_message: str, requested_action: str | None) -> str:
	lowered = user_message.lower()
	if any(token in lowered for token in ("urgent", "asap", "immediately", "right now")):
		return "urgent"
	if requested_action in {"refund", "human_support"}:
		return "high"
	if any(token in lowered for token in ("angry", "terrible", "awful", "unacceptable")):
		return "high"
	return "medium"


def _has_human_support_request(user_message: str) -> bool:
	lowered = user_message.lower()
	return any(token in lowered for token in ("human", "manager", "agent", "person", "someone real"))


def _is_vague_description(description: str | None) -> bool:
	if description is None:
		return True
	normalized = " ".join(description.lower().split())
	if normalized in {
		"i have a problem",
		"i have an issue",
		"i need help",
		"help me",
		"there is a problem",
		"there is an issue",
		"support",
		"complaint",
	}:
		return True

	generic_problem_tokens = ("problem", "issue", "help", "support")
	specific_issue_tokens = ("cold", "late", "delay", "wrong", "missing", "damaged", "refund", "status", "spoiled", "bad quality")
	if any(token in normalized for token in generic_problem_tokens) and not any(token in normalized for token in specific_issue_tokens):
		return True

	return normalized in {
		"i have a problem",
		"i have an issue",
		"i need help",
		"help me",
		"there is a problem",
		"there is an issue",
		"support",
		"complaint",
	}


def _should_escalate_to_human(complaint: dict[str, Any]) -> bool:
	requested_action = complaint.get("requested_action")
	priority = complaint.get("priority")
	complaint_type = complaint.get("complaint_type")

	if requested_action == "human_support":
		return True
	if priority == "urgent":
		return True
	return complaint_type == "human_support"


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


def extract_complaint_from_message(user_message: str, existing_complaint: dict[str, Any] | None = None) -> dict[str, Any]:
	base_complaint = _normalize_complaint(existing_complaint)
	prompt = (
		"Extract a structured restaurant support complaint from the user message. "
		"Return complaint_type, description, order_id when stated, priority, requested_action, and whether the user needs a human.\n\n"
		f"Existing complaint context: {base_complaint}\n"
		f"User message: {user_message}"
	)

	try:
		payload = _get_llm().with_structured_output(ExtractedComplaintPayload).invoke(prompt)
		extracted = payload.model_dump(exclude_none=True)
	except Exception:
		extracted = {}

	if not extracted.get("complaint_type"):
		extracted["complaint_type"] = _infer_complaint_type(user_message)
	if not extracted.get("requested_action"):
		extracted["requested_action"] = _infer_requested_action(user_message)
	if extracted.get("order_id") is None:
		extracted["order_id"] = _extract_order_id_from_text(user_message)
	if not _has_human_support_request(user_message):
		if extracted.get("complaint_type") == "human_support":
			extracted["complaint_type"] = _infer_complaint_type(user_message)
		if extracted.get("requested_action") == "human_support":
			extracted["requested_action"] = _infer_requested_action(user_message)
		extracted["needs_human"] = False
	if not extracted.get("description"):
		extracted["description"] = user_message.strip() or None
	if not extracted.get("priority"):
		extracted["priority"] = _infer_priority(user_message, extracted.get("requested_action"))
	if extracted.get("needs_human") is None:
		extracted["needs_human"] = _has_human_support_request(user_message)

	merged = _normalize_complaint({**base_complaint, **{key: value for key, value in extracted.items() if value is not None}})
	return merged


def validate_complaint(extracted_complaint: dict[str, Any] | None) -> dict[str, Any]:
	complaint = _normalize_complaint(extracted_complaint)
	missing_fields: list[str] = []

	if not (complaint.get("complaint_type") or "").strip():
		missing_fields.append("complaint_type")
	if not (complaint.get("description") or "").strip():
		missing_fields.append("description")
	elif _is_vague_description(complaint.get("description")):
		missing_fields.append("what happened")

	requires_order_reference = complaint.get("requested_action") in {"refund", "replacement", "status_check"} or complaint.get("complaint_type") in {
		"refund_request",
		"late_delivery",
		"wrong_item",
		"missing_item",
		"damaged_order",
		"order_status",
	}
	if requires_order_reference and complaint.get("order_id") is None:
		missing_fields.append("order_id")

	if complaint.get("priority") not in {"low", "medium", "high", "urgent"}:
		complaint["priority"] = "medium"

	complaint["needs_human"] = _should_escalate_to_human(complaint)

	return {
		"is_complete": not missing_fields,
		"missing_fields": missing_fields,
		"normalized_complaint": complaint,
		"needs_human": complaint["needs_human"],
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
