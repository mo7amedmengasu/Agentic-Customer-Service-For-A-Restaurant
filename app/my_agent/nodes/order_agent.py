from __future__ import annotations

import re
from typing import Any, Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.my_agent.shcemas.order_agent_schemas import ExtractedOrderPayload
from app.my_agent.states.state import MainState
from app.my_agent.tools.order_agent_tools import (
	calculate_order_total,
	cancel_order,
	check_missing_order_fields,
	create_delivery_if_needed,
	create_order,
	create_order_items,
	update_extracted_order,
	update_placed_order,
	validate_order_items,
)


# Steps the LLM reasoning node is allowed to choose.
# validate_order, calculate_summary, and ask_confirmation are
# handled by deterministic graph edges — the LLM must NOT choose them.
ALLOWED_NEXT_STEPS = {
	"extract_order",
	"modify_order",
	"place_order",
	"cancel_order",
	"update_placed_order",
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
		"cancel_order",
		"update_placed_order",
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
	if order.get("order_type") in {"pickup", "delivery", "dine_in"}:
		display_type = {"dine_in": "dine-in"}.get(order["order_type"], order["order_type"])
		response += f" for {display_type}"
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


_UPDATE_PLACED_TOKENS = {
	"change", "update", "modify", "modification", "switch", "convert", "adjust", "fix", "correction",
	"add", "remove", "delete",
	"pickup", "pick up", "delivery", "dine-in", "dine in", "eat in",
}

# Regex to detect an explicit order ID in the user message
# Matches: "order #19", "order 19", "#19", "order id is 19", "id is 19", "its id is 19"
_EXPLICIT_ORDER_ID_RE = re.compile(
	r"(?:order\s*#?\s*|#\s*)(\d+)"
	r"|order\s+id\s*(?:is|:|=)?\s*(\d+)"
	r"|(?<!\w)id\s+(?:is\s+)?(\d+)",
	re.IGNORECASE,
)


def _extract_order_id_from_message(user_message: str) -> int | None:
	"""Return an order ID mentioned explicitly in the user message, or None."""
	match = _EXPLICIT_ORDER_ID_RE.search(user_message or "")
	if match:
		return int(next(g for g in match.groups() if g is not None))
	return None


def _wants_to_update_placed_order(state: MainState) -> bool:
	"""Return True when the user wants to modify an already-placed order.

	Two ways to enter this flow:
	1. User explicitly names an order ID + modification intent in the same message
	   (e.g. "add 2 burgers to order #22" or "change order 22 to pickup").
	2. User is continuing a previously identified modification flow:
	   modification_target_id is set in state AND user expresses modification intent.
	   This handles multi-turn conversations like:
	     [turn 1] "modify order 22" → system asks what to change, sets modification_target_id=22
	     [turn 2] "add 1 orange juice" → no order ID in message but modification_target_id=22
	"""
	extracted_order = _normalize_order(state.get("extracted_order"))
	if extracted_order.get("items"):
		# Cart still has items — in-progress modification, not a placed order update.
		return False
	user_msg = state.get("user_message") or ""
	has_modification_intent = any(token in user_msg.lower() for token in _UPDATE_PLACED_TOKENS)
	# Case 2: already in modification flow from previous turn
	if state.get("modification_target_id") and has_modification_intent:
		return True
	# Case 1: fresh request with explicit order ID in message
	has_explicit_id = _extract_order_id_from_message(user_msg) is not None
	return has_modification_intent and has_explicit_id


def _coerce_next_step(state: MainState, proposed_step: str | None) -> str:
	"""Hard structural safety rails — only overrides when the proposed step is structurally impossible."""
	extracted_order = _normalize_order(state.get("extracted_order"))
	has_items = bool(extracted_order.get("items"))
	awaiting_confirmation = _is_awaiting_confirmation(state)
	user_msg = state.get("user_message") or ""
	user_msg_lower = user_msg.lower()

	# Compute last AI message once for all context-aware coercions
	_messages = state.get("messages") or []
	last_ai = next(
		(m.content for m in reversed(_messages) if getattr(m, "type", None) == "ai"),
		"",
	)
	last_ai_lower = last_ai.lower()

	# Hard override: if user is clearly trying to modify a placed order, always
	# route to update_placed_order — regardless of what the LLM proposed.
	if _wants_to_update_placed_order(state):
		return "update_placed_order"

	# Context-aware cancel coercion: last AI asked for cancel order ID → user replied with a number.
	if re.search(r"\b\d+\b", user_msg):
		if last_ai and "cancel" in last_ai_lower and any(phrase in last_ai_lower for phrase in (
			"share the order id", "provide the order id", "order id", "order number",
		)):
			return "cancel_order"

	# Context-aware update coercion: last AI asked for modification order ID / what to change
	# → user replied with a number or a modification request → route to update_placed_order.
	_is_update_ask = last_ai and any(phrase in last_ai_lower for phrase in (
		"what would you like to change on order",
		"could you share the order id",
		"i'd be happy to update your order",
		"update your order",
	)) and "cancel" not in last_ai_lower
	if _is_update_ask:
		if re.search(r"\b\d+\b", user_msg) or any(token in user_msg_lower for token in _UPDATE_PLACED_TOKENS):
			return "update_placed_order"

	# update_placed_order only makes sense when cart is empty AND an order is identifiable.
	# If the cart still has items, the user is modifying the in-progress order → modify_order.
	if proposed_step == "update_placed_order":
		if has_items:
			return "modify_order"
		has_id = (
			state.get("modification_target_id")
			or state.get("order_id")
			or _extract_order_id_from_message(user_msg)
		)
		if not has_id:
			return "final_response"

	# cancel_order and update_placed_order operate on DB records — they don't need
	# items in the in-memory cart.  Everything else requires items first.
	no_cart_allowed = {"extract_order", "final_response", "cancel_order", "update_placed_order"}
	if not has_items and proposed_step not in no_cart_allowed:
		return "extract_order"

	# Never place the order unless the confirmation prompt was already shown.
	if proposed_step == "place_order" and not awaiting_confirmation:
		return "modify_order" if has_items else "extract_order"

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
	extracted_order = _normalize_order(state.get("extracted_order"))
	awaiting_confirmation = _is_awaiting_confirmation(state)
	missing_fields = state.get("missing_fields") or []
	order_id = state.get("order_id")
	modification_target_id = state.get("modification_target_id")
	order_summary = _summarize_order(extracted_order)
	history = _build_history_context(state.get("messages", []))

	prompt = f"""You are the decision-maker for a restaurant ordering assistant.

Based on the conversation, decide:
1. **next_step** — the next action in the ordering workflow
2. **response** — what to say to the customer (REQUIRED whenever next_step is "final_response")

## Allowed next_step values
- `extract_order` — ONLY when the user is actively placing a brand-new order (message contains food item names / quantities, e.g. "I want 2 burgers and a pizza")
- `modify_order` — update the **in-progress cart** (add/remove items, change order type before placing)
- `place_order` — submit the confirmed order (ONLY if the user explicitly confirmed AND awaiting_confirmation is True)
- `cancel_order` — cancel an already-placed order (order_id known)
- `update_placed_order` — modify an **already-placed DB order** (change its order type OR add items)
- `final_response` — reply directly to the user for EVERYTHING ELSE

## Decision rules — apply in order, stop at first match
1. User explicitly names food items they want to order AND cart is empty → `extract_order`
2. User wants to change/add/remove items or set delivery details AND cart has items → `modify_order`
3. User says "yes"/"confirm"/"go ahead"/"place it" AND awaiting_confirmation is True → `place_order`
4. User wants to cancel an order AND has provided a number that could be the order ID:
   - Explicit form: 'cancel order #19', 'cancel order 19', 'order id is 21'
   - **Bare number as follow-up**: if the previous assistant message asked for an order ID for cancellation and the user now replies with just a number (e.g. '21'), treat that number as the order ID → `cancel_order`
5. User mentions cancellation but has NOT provided any number → `final_response`; ask them to share the order ID (e.g. 'cancel order #21')
6. User wants to change/modify/add-to an **already-placed order**:
   - If **Modification Target Order ID** is set (user previously identified the order this session), any modification intent (e.g. 'add 2 burgers', 'change to pickup') → `update_placed_order`
   - If no target is set, the message must contain an explicit order ID (e.g. 'add to order #22', 'change order 19 to pickup') → `update_placed_order`
   - Supports: changing order type AND adding items to the order
   ⚠️  CRITICAL: If cart still has items, this is `modify_order` not `update_placed_order`.
   ⚠️  CRITICAL: Never use `final_response` to report the change — use `update_placed_order` so it actually writes to the DB.
7. User asks about order status, tracking, or what's in their order → `final_response`; summarise current order in response
8. Greeting, gratitude, goodbye, or unrelated topic → `final_response`; respond warmly
9. Anything else (unclear, question, complaint) → `final_response`; ask a helpful clarifying question

⚠️  CRITICAL: `extract_order` is ONLY for active new orders with food items named.
⚠️  CRITICAL: `modify_order` is ONLY for the in-progress cart (has items). Use `update_placed_order` when the cart is empty and the user refers to a previously placed order.

## Current Ordering State
Current order: {order_summary}
Order ID: {order_id or "none"}
Modification Target Order ID: {modification_target_id or "none"} (if set, user is actively modifying this placed order)
Missing fields: {missing_fields or "none"}
Awaiting customer confirmation: {awaiting_confirmation}

## Conversation History
{history}

## Latest User Message
{state.get('user_message')}

Remember: always fill `response` when next_step is "final_response"."""

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
		"Use the conversation history to resolve references like 'that', 'it', 'those', or previously mentioned items.\n\n"
		"Fields to extract:\n"
		"- items: list of food items with quantities\n"
		"- order_type: ONLY set this if the user EXPLICITLY stated how they want their order.\n"
		"  Leave it null/None if the user did NOT mention it — do NOT assume or default.\n"
		"  • use 'dine_in'  for: dine-in, dine in, eat in, eat here, sit in, table, inside\n"
		"  • use 'pickup'   for: takeaway, take away, collect, pick up, pickup\n"
		"  • use 'delivery' for: deliver to, send to, bring to, home delivery\n"
		"- delivery_address: only set when order_type is 'delivery' AND the user provided an address\n"
		"- customer_notes: any special instructions the user mentioned (e.g. 'no onions')\n\n"
		"⚠️  Do NOT invent or guess order_type. If the user did not say it, leave it null.\n\n"
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
	"order_type": "Would you like that for **delivery**, **pickup**, or **dine-in**?",
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
		# Clear the completed order so any subsequent "new order" starts fully fresh
		# (no stale order_type, items, or delivery_address carried over)
		"extracted_order": None,
		"order_ready": None,
		"missing_fields": None,
		"invalid_items": None,
		"response": f"Your order has been placed successfully! 🎉 Your order ID is **{order_result['order_id']}**.",
		"tool_result": {
			"order": order_result,
			"order_items": create_order_items_result,
			"delivery": delivery_result,
		},
		"next_step": "final_response",
	}


def update_placed_order_node(state: MainState) -> dict[str, Any]:
	"""Modify an already-placed DB order (change order type or add items)."""
	order_id = (
		state.get("modification_target_id")
		or state.get("order_id")
		or _extract_order_id_from_message(state.get("user_message") or "")
	)
	customer_id = state.get("customer_id")

	if not order_id:
		return {
			"response": (
				"I'd be happy to update your order! "
				"Could you share the order ID? (e.g. 'change order #19 to pickup' or 'add 2 burgers to order #19')"
			),
			"next_step": "final_response",
			"modification_target_id": None,
		}

	# Use the LLM to extract what the user wants to change
	class _ItemToAdd(BaseModel):
		item_name: str
		quantity: int = 1

	class PlacedOrderUpdateRequest(BaseModel):
		order_type: Literal["pickup", "delivery", "dine_in"] | None = Field(default=None)
		items_to_add: list[_ItemToAdd] | None = Field(default=None)

	prompt = (
		f"The customer wants to modify their already-placed order #{order_id}.\n"
		"Extract what they want to change:\n\n"
		"- order_type: set ONLY if they explicitly name a new type:\n"
		"  • 'dine_in'  → dine-in, eat in, sit in, eat here\n"
		"  • 'pickup'   → pickup, take away, collect\n"
		"  • 'delivery' → delivery, deliver to, bring to\n"
		"  Leave order_type as null if they did not specify a new type.\n\n"
		"- items_to_add: list of items the user wants to ADD to the order.\n"
		"  Each entry needs item_name (string) and quantity (integer).\n"
		"  Leave null/empty if the user is not adding items.\n\n"
		f"Conversation history:\n{_build_history_context(state.get('messages', []))}\n\n"
		f"Latest user message: {state.get('user_message')}"
	)

	try:
		req = _get_llm().with_structured_output(PlacedOrderUpdateRequest).invoke(prompt)
	except Exception:
		return {
			"response": "I had trouble understanding what you'd like to change. Could you clarify?",
			"next_step": "final_response",
			"modification_target_id": order_id,
		}

	items_to_add = (
		[{"item_name": i.item_name, "quantity": i.quantity} for i in req.items_to_add]
		if req.items_to_add else None
	)

	if not req.order_type and not items_to_add:
		return {
			"response": (
				f"What would you like to change on order #{order_id}? "
				"I can:\n"
				"• Update the order type to **pickup**, **delivery**, or **dine-in**\n"
				"• Add items (e.g. 'add 2 orange juices')"
			),
			"next_step": "final_response",
			"modification_target_id": order_id,
		}

	result = update_placed_order(
		order_id=order_id,
		customer_id=customer_id,
		order_type=req.order_type,
		items_to_add=items_to_add,
	)

	if result["success"]:
		changes = " and ".join(result.get("changes", []))
		response = f"Done! I've updated order #{order_id}: {changes}. Would you like to make any other changes?"
	else:
		response = f"I wasn't able to update the order: {result['message']}"

	return {
		"response": response,
		"next_step": "final_response",
		# Keep modification_target_id so user can continue modifying same order
		"modification_target_id": order_id if result["success"] else None,
	}


def cancel_order_node(state: MainState) -> dict[str, Any]:
	"""Actually cancel the order in the database, then return a response."""
	order_id = state.get("order_id")
	customer_id = state.get("customer_id")

	# If we still don't have an order_id, try to parse it from the user message
	if not order_id:
		order_id = _extract_order_id_from_message(state.get("user_message") or "")
	# Broader fallback: any standalone number in the message — safe here because
	# we are already inside cancel_order_node (routing already confirmed cancel intent).
	if not order_id:
		m = re.search(r"\b(\d+)\b", state.get("user_message") or "")
		if m:
			order_id = int(m.group(1))
	if not order_id:
		return {
			"response": (
				"I'd be happy to cancel your order! "
				"Could you please share the order ID? (e.g. 'cancel order #19')"
			),
			"next_step": "final_response",
		}

	result = cancel_order(order_id, customer_id=customer_id)
	if result["success"]:
		response = (
			f"Your order #{order_id} has been successfully cancelled. "
			"If you'd like to place a new order or need any other help, just let me know! 😊"
		)
		return {
			"response": response,
			"next_step": "final_response",
			# Clear order state so the next conversation starts completely fresh
			"extracted_order": None,
			"order_ready": None,
			"missing_fields": None,
			"invalid_items": None,
			"order_awaiting_confirmation": False,
			"order_id": None,
		}
	else:
		response = f"I wasn't able to cancel the order: {result['message']}"

	return {
		"response": response,
		"next_step": "final_response",
	}


def final_response_node(state: MainState) -> dict[str, Any]:
	return {"response": state.get("response") or "How can I help with your order?"}
