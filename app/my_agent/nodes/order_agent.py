from __future__ import annotations

from typing import Any, Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.my_agent.shcemas.order_agent_schemas import ExtractedOrderPayload
from app.my_agent.states.state import MainState
from app.my_agent.tools.order_agent_tools import (
	calculate_order_total,
	check_missing_order_fields,
	create_delivery_if_needed,
	create_order,
	create_order_items,
	update_extracted_order,
	validate_order_items,
)


ALLOWED_NEXT_STEPS = {
	"extract_order",
	"validate_order",
	"ask_missing_info",
	"calculate_summary",
	"ask_confirmation",
	"modify_order",
	"place_order",
	"final_response",
}


def _get_llm() -> ChatOpenAI:
	return ChatOpenAI(model="gpt-4o-mini", temperature=0)


class ReasoningDecision(BaseModel):
	next_step: Literal[
		"extract_order",
		"validate_order",
		"ask_missing_info",
		"calculate_summary",
		"ask_confirmation",
		"modify_order",
		"place_order",
		"final_response",
	]
	response: str | None = Field(default=None)


def _normalize_order(extracted_order: dict[str, Any] | None) -> dict[str, Any]:
	payload = dict(extracted_order or {})
	payload.setdefault("items", [])
	return payload


def _summarize_order(extracted_order: dict[str, Any] | None) -> str:
	order = _normalize_order(extracted_order)
	items = order.get("items") or []
	if not items:
		return "You do not have any items in your order yet."

	item_summaries = []
	for item in items:
		item_name = item.get("item_name", "item")
		quantity = item.get("quantity")
		if quantity is None:
			item_summaries.append(item_name)
		else:
			item_summaries.append(f"{quantity}x {item_name}")

	response = f"Your current order is {', '.join(item_summaries)}"
	if order.get("order_type") in {"pickup", "delivery"}:
		response += f" for {order['order_type']}"
	if order.get("delivery_address"):
		response += f" to {order['delivery_address']}"
	response += "."
	return response


def _describe_order_changes(previous_order: dict[str, Any] | None, updated_order: dict[str, Any] | None) -> str | None:
	previous = _normalize_order(previous_order)
	updated = _normalize_order(updated_order)

	change_messages: list[str] = []

	if previous.get("order_type") != updated.get("order_type") and updated.get("order_type"):
		change_messages.append(f"I updated your order type to {updated['order_type']}")

	if previous.get("delivery_address") != updated.get("delivery_address") and updated.get("delivery_address"):
		change_messages.append(f"I updated your delivery address to {updated['delivery_address']}")

	previous_items = {item.get("item_name", "").lower(): int(item.get("quantity") or 0) for item in previous.get("items", [])}
	updated_items = {item.get("item_name", "").lower(): int(item.get("quantity") or 0) for item in updated.get("items", [])}

	item_messages: list[str] = []
	for item_name, updated_quantity in updated_items.items():
		previous_quantity = previous_items.get(item_name)
		label = next((item.get("item_name", item_name) for item in updated.get("items", []) if item.get("item_name", "").lower() == item_name), item_name)
		if previous_quantity is None:
			item_messages.append(f"added {updated_quantity}x {label}")
		elif previous_quantity != updated_quantity:
			item_messages.append(f"changed {label} to {updated_quantity}")

	for item_name in previous_items:
		if item_name not in updated_items:
			label = next((item.get("item_name", item_name) for item in previous.get("items", []) if item.get("item_name", "").lower() == item_name), item_name)
			item_messages.append(f"removed {label}")

	if item_messages:
		change_messages.append(f"I updated your order: {', '.join(item_messages)}")

	if not change_messages:
		return None
	return ". ".join(change_messages) + "."


def _is_order_status_question(user_message: str) -> bool:
	lowered = user_message.lower()
	question_patterns = (
		"what is my current order",
		"what is my order",
		"what did i order",
		"what is in my order",
		"show my order",
		"show current order",
		"current order",
		"order summary",
	)
	return any(pattern in lowered for pattern in question_patterns)


def _coerce_next_step(state: MainState, proposed_step: str | None) -> str:
	user_message = (state.get("user_message") or "").strip().lower()
	extracted_order = _normalize_order(state.get("extracted_order"))
	has_items = bool(extracted_order.get("items"))
	has_order_type = extracted_order.get("order_type") in {"pickup", "delivery"}
	missing_fields = set(state.get("missing_fields") or [])

	if user_message:
		if has_items and _is_order_status_question(user_message):
			return "final_response"
		if not has_items and not has_order_type:
			return "extract_order"
		if has_items and ("order_type" in missing_fields or not has_order_type) and user_message in {"pickup", "delivery"}:
			return "modify_order"
		if has_items and "delivery_address" in missing_fields and extracted_order.get("order_type") == "delivery":
			return "modify_order"
		if has_items and any(token in user_message for token in ("pickup", "delivery", "remove", "replace", "change", "add", "instead")):
			return "modify_order"

	if proposed_step in ALLOWED_NEXT_STEPS:
		return proposed_step
	return "final_response"


def _fallback_reasoning(state: MainState) -> dict[str, Any]:
	user_message = (state.get("user_message") or "").lower()
	extracted_order = _normalize_order(state.get("extracted_order"))

	if not extracted_order.get("items"):
		return {"next_step": "extract_order"}
	if any(token in user_message for token in ("remove", "replace", "change", "add", "instead", "pickup", "delivery")):
		return {"next_step": "modify_order"}
	if state.get("order_ready") is False:
		return {"next_step": "ask_missing_info"}
	if state.get("order_ready") and not state.get("tool_result", {}).get("total_amount"):
		return {"next_step": "calculate_summary"}
	if any(token in user_message for token in ("yes", "confirm", "go ahead", "place it", "place the order")):
		return {"next_step": "place_order"}
	if state.get("tool_result", {}).get("total_amount"):
		return {"next_step": "ask_confirmation"}
	return {"next_step": "validate_order"}


def order_reasoning_node(state: MainState) -> dict[str, Any]:
	user_message = state.get("user_message") or ""
	extracted_order = _normalize_order(state.get("extracted_order"))
	if extracted_order.get("items") and _is_order_status_question(user_message):
		response = _summarize_order(extracted_order)
		missing_fields = state.get("missing_fields") or []
		if missing_fields:
			response += f" I still need your {', '.join(missing_fields)} to continue."
		return {"next_step": "final_response", "response": response}

	prompt = (
		"You are the order orchestration decision maker for a restaurant ordering workflow. "
		"Pick exactly one next_step from the allowed values based on the state. "
		"Only provide a direct response when the workflow should end or the user only needs an immediate question.\n\n"
		f"Allowed next steps: {sorted(ALLOWED_NEXT_STEPS)}\n"
		f"User message: {state.get('user_message')}\n"
		f"Messages: {state.get('messages')}\n"
		f"Extracted order: {state.get('extracted_order')}\n"
		f"Tool result: {state.get('tool_result')}\n"
		f"Order ready: {state.get('order_ready')}\n"
		f"Order confirmed: {state.get('order_confirmed')}"
	)

	try:
		decision = _get_llm().with_structured_output(ReasoningDecision).invoke(prompt)
		result = decision.model_dump(exclude_none=True)
	except Exception:
		result = _fallback_reasoning(state)

	result["next_step"] = _coerce_next_step(state, result.get("next_step"))
	return result


def extract_order_node(state: MainState) -> dict[str, Any]:
	prompt = (
		"Extract restaurant order details from the user message. "
		"Return items, quantity per item, order type, delivery address, and customer notes.\n\n"
		f"User message: {state.get('user_message')}"
	)

	try:
		extracted = _get_llm().with_structured_output(ExtractedOrderPayload).invoke(prompt)
		extracted_order = extracted.model_dump(exclude_none=True)
	except Exception:
		extracted_order = {
			"items": [],
			"order_type": None,
			"delivery_address": None,
			"customer_notes": None,
		}

	return {
		"extracted_order": extracted_order,
		"tool_result": None,
		"next_step": "validate_order",
	}


def validate_order_node(state: MainState) -> dict[str, Any]:
	extracted_order = _normalize_order(state.get("extracted_order"))
	validation_result = validate_order_items(extracted_order.get("items", []))
	missing_result = check_missing_order_fields(extracted_order)
	invalid_items = validation_result["invalid_items"] + validation_result["unavailable_items"]
	order_ready = missing_result["is_complete"] and not invalid_items

	return {
		"order_ready": order_ready,
		"missing_fields": missing_result["missing_fields"],
		"invalid_items": invalid_items,
		"tool_result": {
			**validation_result,
			**missing_result,
		},
		"next_step": "calculate_summary" if order_ready else "ask_missing_info",
	}


def ask_missing_info_node(state: MainState) -> dict[str, Any]:
	missing_fields = state.get("missing_fields") or []
	invalid_items = state.get("invalid_items") or []
	extracted_order = _normalize_order(state.get("extracted_order"))

	if invalid_items:
		invalid_names = ", ".join(item.get("item_name", "unknown item") for item in invalid_items)
		response = f"I couldn't validate these items: {invalid_names}. Please update them so I can continue the order."
	elif missing_fields:
		joined_fields = ", ".join(missing_fields)
		if extracted_order.get("items"):
			response = f"{_summarize_order(extracted_order)} I still need your {joined_fields} to continue your order."
		else:
			response = f"I still need your {joined_fields} to continue your order."
	else:
		response = "I need a few more order details before I can continue."

	return {"response": response, "next_step": "final_response"}


def calculate_summary_node(state: MainState) -> dict[str, Any]:
	summary = calculate_order_total(_normalize_order(state.get("extracted_order")))
	return {
		"tool_result": summary,
		"next_step": "ask_confirmation",
	}


def ask_confirmation_node(state: MainState) -> dict[str, Any]:
	summary = state.get("tool_result") or {}
	item_summaries = [f"{item['quantity']}x {item['item_name']}" for item in summary.get("items", [])]
	items_text = ", ".join(item_summaries) if item_summaries else "your order"
	total_amount = summary.get("total_amount", 0)
	response = f"Please confirm: {items_text}. Total: {total_amount} EGP. Should I place the order?"
	existing_response = state.get("response")
	if existing_response:
		response = f"{existing_response} {response}"
	return {"response": response, "next_step": "final_response"}


def modify_order_node(state: MainState) -> dict[str, Any]:
	previous_order = _normalize_order(state.get("extracted_order"))
	updated_order = update_extracted_order(
		previous_order,
		state.get("user_message") or "",
	)
	change_summary = _describe_order_changes(previous_order, updated_order)
	return {
		"extracted_order": updated_order,
		"response": change_summary,
		"tool_result": None,
		"next_step": "validate_order",
	}


def place_order_node(state: MainState) -> dict[str, Any]:
	customer_id = state.get("customer_id")
	extracted_order = _normalize_order(state.get("extracted_order"))
	summary = state.get("tool_result") or {}
	if not summary.get("items"):
		summary = calculate_order_total(extracted_order)

	if customer_id is None:
		return {
			"response": "I need your customer account before I can place this order.",
			"tool_result": {"error": "missing_customer_id"},
			"next_step": "final_response",
		}

	order_result = create_order(customer_id, extracted_order, summary.get("total_amount", 0))
	create_order_items_result = create_order_items(order_result["order_id"], summary.get("items", []))
	delivery_result = create_delivery_if_needed(order_result["order_id"], extracted_order)

	return {
		"order_id": order_result["order_id"],
		"response": f"Your order has been placed successfully. Your order ID is {order_result['order_id']}.",
		"tool_result": {
			"order": order_result,
			"order_items": create_order_items_result,
			"delivery": delivery_result,
		},
		"next_step": "final_response",
	}


def final_response_node(state: MainState) -> dict[str, Any]:
	return {"response": state.get("response", "How can I help with your order?")}
