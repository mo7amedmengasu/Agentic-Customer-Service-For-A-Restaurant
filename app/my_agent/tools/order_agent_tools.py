from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.database import SessionLocal
from app.my_agent.shcemas.order_agent_schemas import OrderChange, OrderUpdatePayload
from app.repositories.menu_repository import menu_repository
from app.repositories.order_repository import order_repository


def _get_llm() -> ChatOpenAI:
	return ChatOpenAI(model="gpt-4o-mini", temperature=0)


def _normalize_order(extracted_order: dict[str, Any] | None) -> dict[str, Any]:
	payload = dict(extracted_order or {})
	items = payload.get("items") or []

	if not items and payload.get("item_name"):
		items = [{"item_name": payload.get("item_name"), "quantity": payload.get("quantity")}]

	normalized_items = []
	for item in items:
		if not item:
			continue
		item_name = (item.get("item_name") or "").strip()
		quantity = item.get("quantity")
		normalized_items.append({"item_name": item_name, "quantity": quantity})

	payload["items"] = normalized_items
	return payload


def _serialize_menu_item(menu_item: Any) -> dict[str, Any]:
	return {
		"item_id": menu_item.item_id,
		"item_name": menu_item.item_name,
		"item_price": float(menu_item.item_price),
		"is_available": True,
	}


def _heuristic_confirmation(user_message: str) -> bool:
	lowered = user_message.lower()
	positive_tokens = ("yes", "confirm", "go ahead", "place it", "place the order", "do it")
	negative_tokens = ("no", "change", "remove", "replace", "instead", "cancel", "add")
	return any(token in lowered for token in positive_tokens) and not any(token in lowered for token in negative_tokens)


def _invoke_structured_output(prompt: str, schema: type[BaseModel]) -> BaseModel:
	llm = _get_llm().with_structured_output(schema)
	return llm.invoke(prompt)


def search_menu_item(item_name: str) -> dict[str, Any] | None:
	db = SessionLocal()
	try:
		menu_item = menu_repository.search_item_by_name(db, item_name=item_name)
		if menu_item is None:
			return None
		return _serialize_menu_item(menu_item)
	finally:
		db.close()


def get_menu_items_by_names(item_names: list[str]) -> list[dict[str, Any]]:
	db = SessionLocal()
	try:
		return [_serialize_menu_item(item) for item in menu_repository.get_items_by_names(db, item_names=item_names)]
	finally:
		db.close()


def validate_order_items(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
	normalized_items = _normalize_order({"items": items}).get("items", [])
	requested_names = [item["item_name"] for item in normalized_items if item.get("item_name")]
	menu_items = {item["item_name"].lower(): item for item in get_menu_items_by_names(requested_names)}

	result = {
		"valid_items": [],
		"invalid_items": [],
		"unavailable_items": [],
	}

	for item in normalized_items:
		item_name = item.get("item_name") or ""
		quantity = item.get("quantity")
		menu_item = menu_items.get(item_name.lower())
		if menu_item is None and item_name:
			menu_item = search_menu_item(item_name)

		if not item_name or quantity is None or int(quantity) <= 0:
			result["invalid_items"].append(item)
			continue
		if menu_item is None:
			result["invalid_items"].append(item)
			continue
		if not menu_item["is_available"]:
			result["unavailable_items"].append({**item, **menu_item})
			continue

		result["valid_items"].append(
			{
				"item_id": menu_item["item_id"],
				"item_name": menu_item["item_name"],
				"quantity": int(quantity),
				"unit_price": menu_item["item_price"],
			}
		)

	return result


def check_missing_order_fields(extracted_order: dict[str, Any]) -> dict[str, Any]:
	order = _normalize_order(extracted_order)
	missing_fields: list[str] = []
	has_items = bool(order.get("items"))

	if not has_items:
		missing_fields.append("items")
	else:
		for item in order["items"]:
			quantity = item.get("quantity")
			if quantity is None or int(quantity) <= 0:
				label = item.get("item_name") or "requested item"
				missing_fields.append(f"quantity for {label}")

	order_type = order.get("order_type")
	if has_items and order_type not in {"pickup", "delivery", "dine_in"}:
		missing_fields.append("order_type")

	if order_type == "delivery" and not (order.get("delivery_address") or "").strip():
		missing_fields.append("delivery_address")

	return {
		"is_complete": not missing_fields,
		"missing_fields": missing_fields,
	}


def calculate_order_total(extracted_order: dict[str, Any]) -> dict[str, Any]:
	validation_result = validate_order_items(_normalize_order(extracted_order).get("items", []))
	line_items: list[dict[str, Any]] = []
	total_amount = Decimal("0")

	for item in validation_result["valid_items"]:
		unit_price = Decimal(str(item["unit_price"]))
		quantity = int(item["quantity"])
		subtotal = unit_price * quantity
		line_items.append(
			{
				"item_id": item["item_id"],
				"item_name": item["item_name"],
				"quantity": quantity,
				"unit_price": float(unit_price),
				"subtotal": float(subtotal),
			}
		)
		total_amount += subtotal

	return {
		"items": line_items,
		"total_amount": float(total_amount),
		"invalid_items": validation_result["invalid_items"],
		"unavailable_items": validation_result["unavailable_items"],
	}


def update_extracted_order(old_order: dict[str, Any], user_message: str) -> dict[str, Any]:
	base_order = _normalize_order(old_order)

	prompt = (
		"Update the existing restaurant order based on the user message.\n\n"
		"IMPORTANT RULES:\n"
		"- 'remove N [item]' (e.g., 'remove 1 burger', 'remove 2 pizzas') → use action='change_quantity' "
		"and set quantity to (current_quantity - N). Do NOT use action='remove' for these cases.\n"
		"- 'remove [item]' with no number, or 'remove all [item]' → use action='remove' (removes item completely).\n"
		"- Only remove items completely if the user clearly wants none left.\n"
		"- Do not change items that are not explicitly mentioned.\n"
		"- If the user says they want to change/update the order type but does NOT specify the new type "
		"(e.g. 'I need to change the type', 'change my order type'), use action='clear_order_type'. "
		"Do NOT guess or keep the old type.\n"
		"- Only use action='set_order_type' when the user explicitly states pickup, delivery, or dine-in.\n\n"
		f"Existing order: {base_order}\n"
		f"User message: {user_message}"
	)

	try:
		payload = _invoke_structured_output(prompt, OrderUpdatePayload)
		changes = payload.changes
	except Exception:
		changes = []
		lowered = user_message.lower()
		if "pickup" in lowered:
			changes.append(OrderChange(action="set_order_type", order_type="pickup"))
		if "delivery" in lowered:
			changes.append(OrderChange(action="set_order_type", order_type="delivery"))
		address_match = re.search(r"(?:to|address is)\s+(.+)$", user_message, re.IGNORECASE)
		if address_match and "delivery" in lowered:
			changes.append(OrderChange(action="set_delivery_address", delivery_address=address_match.group(1).strip()))
		elif base_order.get("order_type") == "delivery" and not base_order.get("delivery_address") and user_message.strip():
			changes.append(OrderChange(action="set_delivery_address", delivery_address=user_message.strip()))

	items_by_name = Counter()
	item_lookup: dict[str, dict[str, Any]] = {}
	for item in base_order.get("items", []):
		name = item.get("item_name", "").strip()
		if not name:
			continue
		normalized_name = name.lower()
		item_lookup[normalized_name] = {"item_name": name, "quantity": int(item.get("quantity") or 0)}
		items_by_name[normalized_name] = int(item.get("quantity") or 0)

	for change in changes:
		if change.action == "add" and change.item_name:
			normalized_name = change.item_name.lower()
			item_lookup.setdefault(normalized_name, {"item_name": change.item_name, "quantity": 0})
			item_lookup[normalized_name]["quantity"] += int(change.quantity or 1)
		elif change.action == "remove" and change.item_name:
			item_lookup.pop(change.item_name.lower(), None)
		elif change.action == "replace" and change.item_name and change.new_item_name:
			item_lookup.pop(change.item_name.lower(), None)
			item_lookup[change.new_item_name.lower()] = {
				"item_name": change.new_item_name,
				"quantity": int(change.quantity or 1),
			}
		elif change.action == "change_quantity" and change.item_name and change.quantity is not None:
			normalized_name = change.item_name.lower()
			item_lookup.setdefault(normalized_name, {"item_name": change.item_name, "quantity": 0})
			item_lookup[normalized_name]["quantity"] = int(change.quantity)
		elif change.action == "set_order_type" and change.order_type:
			base_order["order_type"] = change.order_type
			if change.order_type == "pickup":
				base_order["delivery_address"] = None
		elif change.action == "clear_order_type":
			base_order["order_type"] = None
			base_order["delivery_address"] = None
		elif change.action == "set_delivery_address":
			base_order["delivery_address"] = change.delivery_address
		elif change.action == "set_customer_notes":
			base_order["customer_notes"] = change.customer_notes

	base_order["items"] = list(item_lookup.values())
	return base_order


def create_order(customer_id: int, extracted_order: dict[str, Any], total_amount: float) -> dict[str, Any]:
	db = SessionLocal()
	try:
		order = order_repository.create_order(
			db,
			customer_id=customer_id,
			order_type=_normalize_order(extracted_order).get("order_type", "pickup"),
		)
		return {
			"order_id": order.order_id,
			"order_status": order.order_status,
			"total_amount": total_amount,
		}
	finally:
		db.close()


def create_order_items(order_id: int, items: list[dict[str, Any]]) -> dict[str, Any]:
	db = SessionLocal()
	try:
		created_items = order_repository.create_order_items(db, order_id=order_id, items=items)
		return {
			"order_id": order_id,
			"created_items": len(created_items),
		}
	finally:
		db.close()


def create_delivery_if_needed(order_id: int, extracted_order: dict[str, Any]) -> dict[str, Any]:
	order = _normalize_order(extracted_order)
	if order.get("order_type") != "delivery":
		return {"created": False, "order_type": order.get("order_type")}

	db = SessionLocal()
	try:
		delivery = order_repository.create_delivery(
			db,
			order_id=order_id,
			delivery_service="in_house_delivery",
		)
		return {
			"created": True,
			"delivery_id": delivery.delivery_id,
			"delivery_status": delivery.delivery_status,
			"delivery_address": order.get("delivery_address"),
		}
	finally:
		db.close()


def get_order_by_id(order_id: int) -> dict[str, Any] | None:
	db = SessionLocal()
	try:
		order = order_repository.get_order_by_id(db, order_id=order_id)
		if order is None:
			return None

		return {
			"order_id": order.order_id,
			"customer_id": order.customer_id,
			"order_type": order.order_type,
			"order_status": order.order_status,
			"items": [
				{
					"item_id": item.item_id,
					"item_name": item.item_name,
					"quantity": item.item_quantity,
					"unit_price": float(item.item_price),
					"subtotal": float(Decimal(str(item.item_price)) * item.item_quantity),
				}
				for item in order.order_items
			],
			"delivery": None
			if order.delivery is None
			else {
				"delivery_id": order.delivery.delivery_id,
				"delivery_service": order.delivery.delivery_service,
				"delivery_status": order.delivery.delivery_status,
			},
		}
	finally:
		db.close()


def cancel_order(order_id: int, customer_id: int | None = None) -> dict[str, Any]:
	"""Set an order's status to 'cancelled' in the database.

	Returns a result dict with keys: success (bool), order_id, message.
	If customer_id is provided, it verifies the order belongs to that customer
	before cancelling.
	"""
	db = SessionLocal()
	try:
		order = order_repository.get_order_by_id(db, order_id=order_id)
		if order is None:
			return {
				"success": False,
				"order_id": order_id,
				"message": f"Order #{order_id} was not found.",
			}
		if customer_id is not None and order.customer_id != customer_id:
			return {
				"success": False,
				"order_id": order_id,
				"message": f"Order #{order_id} does not belong to your account.",
			}
		if order.order_status == "cancelled":
			return {
				"success": False,
				"order_id": order_id,
				"message": f"Order #{order_id} is already cancelled.",
			}
		order_repository.update_order_status(db, order_id=order_id, order_status="cancelled")
		return {
			"success": True,
			"order_id": order_id,
			"message": f"Order #{order_id} has been successfully cancelled.",
		}
	finally:
		db.close()


def update_placed_order(
	order_id: int,
	customer_id: int | None = None,
	order_type: str | None = None,
	items_to_add: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
	"""Update attributes of an already-placed order in the database.

	Supports:
	- Changing order_type (pickup / delivery / dine_in)
	- Adding items to the order (items_to_add: list of {item_name, quantity})

	Returns a result dict with keys: success (bool), order_id, changes (list[str]), message.
	"""
	db = SessionLocal()
	try:
		order = order_repository.get_order_by_id(db, order_id=order_id)
		if order is None:
			return {"success": False, "order_id": order_id, "message": f"Order #{order_id} was not found."}
		if customer_id is not None and order.customer_id != customer_id:
			return {"success": False, "order_id": order_id, "message": f"Order #{order_id} does not belong to your account."}
		if order.order_status == "cancelled":
			return {"success": False, "order_id": order_id, "message": f"Order #{order_id} is cancelled and cannot be modified."}

		changes: list[str] = []

		if order_type and order_type in {"pickup", "delivery", "dine_in"}:
			old_type = order.order_type
			order_repository.update_order_type(db, order_id=order_id, order_type=order_type)
			display = {"dine_in": "dine-in"}.get(order_type, order_type)
			changes.append(f"order type from {old_type} to {display}")

		if items_to_add:
			validation = validate_order_items(items_to_add)
			valid = validation["valid_items"]
			invalid = validation["invalid_items"]
			if valid:
				order_repository.create_order_items(db, order_id=order_id, items=valid)
				names = ", ".join(f"{i['quantity']}x {i['item_name']}" for i in valid)
				changes.append(f"added {names}")
			if invalid:
				invalid_names = ", ".join(i.get("item_name", "?") for i in invalid)
				# Report invalid items but don't fail the whole request if some items were valid
				if not valid:
					return {
						"success": False,
						"order_id": order_id,
						"message": f"Could not find these items on the menu: {invalid_names}.",
					}

		if not changes:
			return {"success": False, "order_id": order_id, "message": "No recognised changes were requested."}

		return {"success": True, "order_id": order_id, "changes": changes, "message": "Order updated successfully."}
	finally:
		db.close()
