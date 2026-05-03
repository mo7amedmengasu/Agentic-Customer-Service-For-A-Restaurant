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


# Steps the LLM reasoning node is allowed to choose.
# validate_order, calculate_summary, and ask_confirmation are
# handled by deterministic graph edges — the LLM must NOT choose them.
ALLOWED_NEXT_STEPS = {
	"extract_order",
	"modify_order",
	"place_order",
	"final_response",
}


def _get_llm() -> ChatOpenAI:
	return ChatOpenAI(model="gpt-4o-mini", temperature=0)


def _build_history_context(messages: list) -> str:
	"""Return the last 10 turns as a plain-text string for LLM context."""
	lines = []
	for m in (messages or []):
		if hasattr(m, "type"):
			role = "Customer" if m.type == "human" else "Assistant"
			lines.append(f"{role}: {m.content}")
		elif isinstance(m, dict):
			role = "Customer" if m.get("role") == "user" else "Assistant"
			lines.append(f"{role}: {m.get('content', '')}")
	return "\n".join(lines[-10:])


class ReasoningDecision(BaseModel):
	next_step: Literal[
		"extract_order",
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


_GRATITUDE_TOKENS = (
	"thank you", "thanks", "thank u", "thx", "appreciate",
	"you're great", "great help", "that's all", "that is all",
	"no all", "all good", "all is good", "i'm good", "im good",
	"nothing else", "no thanks", "no thank you", "have a good", "goodbye", "bye",
)

_GRATITUDE_REPLIES = [
	"You're welcome! 😊 It was a pleasure helping you. Enjoy your meal and feel free to come back anytime!",
	"Glad I could help! 🍽️ Have a wonderful time and enjoy your meal!",
	"Anytime! If you ever need anything else — menu, orders, or anything — just ask. Enjoy! 😊",
]

_gratitude_reply_index = 0


def _is_gratitude_or_dismissal(user_message: str) -> bool:
	lowered = user_message.lower().strip()
	return any(token in lowered for token in _GRATITUDE_TOKENS)


def _get_gratitude_reply() -> str:
	global _gratitude_reply_index
	reply = _GRATITUDE_REPLIES[_gratitude_reply_index % len(_GRATITUDE_REPLIES)]
	_gratitude_reply_index += 1
	return reply


def _is_awaiting_confirmation(state: MainState) -> bool:
	"""Return True if the confirmation prompt has already been shown to the user.

	Checks the in-memory flag first (fast path), then falls back to inspecting
	the last AI message in the conversation history so the check survives
	server restarts that clear the in-memory session state.
	"""
	if state.get("order_awaiting_confirmation"):
		return True
	# Fallback: look at the last assistant message in the LangChain history
	messages = state.get("messages") or []
	for msg in reversed(messages):
		if getattr(msg, "type", None) == "ai":
			content = (getattr(msg, "content", None) or "").lower()
			return "shall i place it" in content or "please confirm your order" in content
	return False


def _coerce_next_step(state: MainState, proposed_step: str | None) -> str:
	user_message = (state.get("user_message") or "").strip().lower()
	extracted_order = _normalize_order(state.get("extracted_order"))
	has_items = bool(extracted_order.get("items"))
	awaiting_confirmation = _is_awaiting_confirmation(state)

	# Order status question — handle regardless of whether items exist
	if _is_order_status_question(user_message):
		return "final_response"

	# Gratitude / dismissal — never modify the order for these
	if _is_gratitude_or_dismissal(user_message):
		return "final_response"

	# Hard rule: no items yet → always extract first
	if not has_items:
		return "extract_order"

	if user_message:
		# User is providing/changing delivery/order details
		if any(token in user_message for token in ("pickup", "delivery", "remove", "replace", "change", "add", "instead")):
			return "modify_order"
		# User is confirming — ONLY allowed after confirmation was shown
		if any(token in user_message for token in ("yes", "confirm", "go ahead", "place it", "place the order", "do it", "ok", "sure", "yep", "yeah")):
			if awaiting_confirmation:
				return "place_order"
			# Confirmation tokens but no confirmation shown yet — treat as a new order attempt
			return "extract_order" if not has_items else "final_response"

	# Never allow place_order unless user explicitly confirmed after seeing the summary
	if proposed_step == "place_order" and not awaiting_confirmation:
		return "modify_order" if extracted_order.get("items") else "extract_order"

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
	if any(token in user_message for token in ("yes", "confirm", "go ahead", "place it", "place the order", "do it")):
		return {"next_step": "place_order"}
	return {"next_step": "final_response"}


def order_reasoning_node(state: MainState) -> dict[str, Any]:
	user_message = state.get("user_message") or ""
	extracted_order = _normalize_order(state.get("extracted_order"))
	# Handle order status questions regardless of whether the cart is empty
	if _is_order_status_question(user_message):
		response = _summarize_order(extracted_order)
		missing_fields = state.get("missing_fields") or []
		if missing_fields and extracted_order.get("items"):
			response += f" I still need your {', '.join(missing_fields)} to continue."
		return {"next_step": "final_response", "response": response}

	# Short-circuit gratitude / dismissal — no LLM call needed
	if _is_gratitude_or_dismissal(user_message):
		return {"next_step": "final_response", "response": _get_gratitude_reply()}

	prompt = (
		"You are the order orchestration decision maker for a restaurant ordering workflow. "
		"Pick exactly one next_step from the allowed values based on the user's intent. "
		"Validation, price calculation, and confirmation are handled automatically — do NOT choose them.\n\n"
		"Rules:\n"
		"- No items in order yet → extract_order\n"
		"- User wants to change/update the order (add, remove, change order_type, provide address) → modify_order\n"
		"- User explicitly confirms the order (yes, confirm, place it, go ahead) → place_order\n"
		"- Any other situation (greeting, status question, unclear) → final_response\n\n"
		f"Allowed next steps: {sorted(ALLOWED_NEXT_STEPS)}\n"
		f"Conversation history:\n{_build_history_context(state.get('messages', []))}\n\n"
		f"User message: {state.get('user_message')}\n"
		f"Extracted order: {state.get('extracted_order')}\n"
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
	history = _build_history_context(state.get("messages", []))
	prompt = (
		"Extract restaurant order details from the conversation below. "
		"Use the conversation history to resolve references like 'that', 'it', 'those', or previously mentioned items. "
		"Return items, quantity per item, order type, delivery address, and customer notes.\n\n"
		f"Conversation history:\n{history}\n\n"
		f"Latest user message: {state.get('user_message')}"
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
		"order_awaiting_confirmation": False,
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


_FIELD_LABELS = {
	"items": "what you'd like to order",
	"order_type": "how you'd like to receive it — delivery or pickup",
	"delivery_address": "your delivery address",
	"customer_notes": "any special notes",
}

_MISSING_PROMPTS = {
	"items": "What would you like to order? Feel free to tell me the items and quantities! 😊",
	"order_type": "Would you like that for **delivery** or **pickup**?",
	"delivery_address": "Great choice! What's the delivery address? 🏠",
}


def ask_missing_info_node(state: MainState) -> dict[str, Any]:
	missing_fields = state.get("missing_fields") or []
	invalid_items = state.get("invalid_items") or []
	extracted_order = _normalize_order(state.get("extracted_order"))

	if invalid_items:
		invalid_names = ", ".join(item.get("item_name", "unknown item") for item in invalid_items)
		response = (
			f"Hmm, I couldn't find **{invalid_names}** on our menu. "
			"Could you double-check the name? You can ask me for a full menu overview anytime! 🍽️"
		)
	elif missing_fields:
		# Use a tailored prompt for the first missing field
		first_field = missing_fields[0]
		if first_field in _MISSING_PROMPTS:
			specific_prompt = _MISSING_PROMPTS[first_field]
		else:
			label = _FIELD_LABELS.get(first_field, first_field.replace("_", " "))
			specific_prompt = f"Could you also share {label}?"

		if extracted_order.get("items"):
			order_summary = _summarize_order(extracted_order)
			response = f"{order_summary}\n\n{specific_prompt}"
		else:
			response = specific_prompt
	else:
		response = "Almost there! Could you share a couple more details so I can complete your order? 😊"

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
	response = f"Please confirm your order:\n\n{items_text}\n\n**Total: {total_amount} EGP**\n\nShall I place it?"
	existing_response = state.get("response")
	if existing_response:
		response = f"{existing_response}\n\n{response}"
	return {"response": response, "order_awaiting_confirmation": True, "next_step": "final_response"}


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
		"order_awaiting_confirmation": False,
		"response": f"Your order has been placed successfully! 🎉 Your order ID is **{order_result['order_id']}**.",
		"tool_result": {
			"order": order_result,
			"order_items": create_order_items_result,
			"delivery": delivery_result,
		},
		"next_step": "final_response",
	}


def final_response_node(state: MainState) -> dict[str, Any]:
	return {"response": state.get("response") or "How can I help with your order?"}
