from datetime import datetime
from typing import List
from langchain_core.tools import tool
from app.core.database import SessionLocal
from app.repositories.menu_item import menu_item_repo
from app.repositories.order import order_repo
from app.repositories.order_item import order_item_repo
from app.repositories.delivery import delivery_repo


#Menu Tools

@tool("get_menu", description="Get the full restaurant menu with all available items and prices. Call with no arguments.")
def get_menu(_: str = "") -> str:
    """Return the full menu."""
    db = SessionLocal()
    try:
        items = menu_item_repo.get_multi(db)
        if not items:
            return "The menu is currently empty."
        lines = []
        for item in items:
            lines.append(
                f"- {item.item_name} (ID: {item.item_id}): ${item.item_price} "
                f"— {item.item_description or 'No description'}"
            )
        return "Restaurant Menu:\n" + "\n".join(lines)
    finally:
        db.close()


@tool("search_menu", description="Search the menu by item name. Use this when the customer asks about a specific dish.")
def search_menu(query: str) -> str:
    
    db = SessionLocal()
    try:
        items = menu_item_repo.search_by_name(db, name=query)
        if not items:
            return f"No menu items found matching '{query}'."
        lines = []
        for item in items:
            lines.append(
                f"- {item.item_name} (ID: {item.item_id}): ${item.item_price} "
                f"— {item.item_description or 'No description'}"
            )
        return f"Menu items matching '{query}':\n" + "\n".join(lines)
    finally:
        db.close()


#Order Tools 

@tool("get_order_status", description="Check the current status of an order by its order ID.")
def get_order_status(order_id: int) -> str:
   
    db = SessionLocal()
    try:
        order = order_repo.get(db, id=order_id)
        if not order:
            return f"No order found with ID {order_id}."
        return (
            f"Order #{order.order_id}:\n"
            f"  Status: {order.order_status}\n"
            f"  Type: {order.order_type}\n"
            f"  Date: {order.order_date}"
        )
    finally:
        db.close()


@tool("get_customer_orders", description="Get all orders for a specific customer by their customer ID.")
def get_customer_orders(customer_id: int) -> str:

    db = SessionLocal()
    try:
        orders = order_repo.get_by_customer(db, customer_id=customer_id)
        if not orders:
            return f"No orders found for customer {customer_id}."
        lines = []
        for o in orders:
            lines.append(
                f"- Order #{o.order_id}: {o.order_status} ({o.order_type}) — {o.order_date}"
            )
        return f"Orders for customer {customer_id}:\n" + "\n".join(lines)
    finally:
        db.close()


@tool(
    "place_order",
    description=(
        "Place a new order for a customer. "
        "Requires customer_id (int) and items (list of dicts, each with "
        "item_id, item_name, item_price, item_quantity)."
    ),
)
def place_order(customer_id: int, items: List[dict]) -> str:

    db = SessionLocal()
    try:
        order = order_repo.create(db, obj_in={
            "customer_id": customer_id,
            "order_type": "delivery",
            "order_status": "pending",
            "order_date": datetime.now(),
        })
        for item in items:
            order_item_repo.create(db, obj_in={
                "order_id": order.order_id,
                "item_id": item["item_id"],
                "item_name": item["item_name"],
                "item_price": item["item_price"],
                "item_quantity": item["item_quantity"],
            })
        return (
            f"Order #{order.order_id} placed successfully!\n"
            f"  Customer: {customer_id}\n"
            f"  Items: {len(items)}\n"
            f"  Status: pending"
        )
    except Exception as e:
        db.rollback()
        return f"Failed to place order: {str(e)}"
    finally:
        db.close()


#Delivery Tools 

@tool("track_delivery", description="Track the delivery status for a specific order by order ID.")
def track_delivery(order_id: int) -> str:
    
    db = SessionLocal()
    try:
        delivery = delivery_repo.get_by_order(db, order_id=order_id)
        if not delivery:
            return f"No delivery found for order #{order_id}."
        return (
            f"Delivery for Order #{order_id}:\n"
            f"  Service: {delivery.delivery_service}\n"
            f"  Status: {delivery.delivery_status}\n"
            f"  Date: {delivery.delivery_date}"
        )
    finally:
        db.close()


# Tool collections for each agent

menu_tools = [get_menu, search_menu]
order_tools = [place_order, get_order_status, get_customer_orders]
support_tools = [track_delivery, get_order_status]
