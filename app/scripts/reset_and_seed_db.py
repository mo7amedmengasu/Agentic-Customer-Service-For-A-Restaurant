from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import SessionLocal, engine, init_db
from app.models.complaint import Complaint
from app.models.delivery import Delivery
from app.models.faq import FAQ
from app.models.menu_item import MenuItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.transaction import Transaction
from app.models.user import User
from app.my_agent.tools.faq_tools import get_embedding
import json


def clear_all_rows() -> None:
    dialect = engine.dialect.name.lower()
    with engine.begin() as connection:
        if dialect.startswith("postgres"):
            connection.execute(
                text(
                    "TRUNCATE TABLE faqs, complaints, transactions, delivery, order_items, orders, menu_items, users RESTART IDENTITY CASCADE"
                )
            )
            return

        for table_name in ("faqs", "complaints", "transactions", "delivery", "order_items", "orders", "menu_items", "users"):
            connection.execute(text(f"DELETE FROM {table_name}"))


def seed_fake_data() -> dict[str, int]:
    init_db()
    clear_all_rows()

    db = SessionLocal()
    try:
        base_time = datetime.now(UTC).replace(tzinfo=None, microsecond=0)

        users = [
            User(
                user_type="customer",
                user_name="Maya Hassan",
                user_email="maya.hassan@example.com",
                user_tel="0100000001",
                user_password="demo-password-1",
            ),
            User(
                user_type="customer",
                user_name="Omar Nabil",
                user_email="omar.nabil@example.com",
                user_tel="0100000002",
                user_password="demo-password-2",
            ),
            User(
                user_type="staff",
                user_name="Sara Adel",
                user_email="sara.adel@example.com",
                user_tel="0100000003",
                user_password="demo-password-3",
            ),
        ]
        db.add_all(users)
        db.flush()

        menu_items = [
            MenuItem(item_name="Burger", item_description="Classic grilled burger", item_image="burger.jpg", item_price=Decimal("75.00")),
            MenuItem(item_name="Cola", item_description="Chilled soft drink", item_image="cola.jpg", item_price=Decimal("20.00")),
            MenuItem(item_name="Margherita Pizza", item_description="Cheese pizza with tomato sauce", item_image="pizza.jpg", item_price=Decimal("110.00")),
            MenuItem(item_name="Pasta Alfredo", item_description="Creamy chicken alfredo pasta", item_image="pasta.jpg", item_price=Decimal("95.00")),
            MenuItem(item_name="Chocolate Cake", item_description="Rich chocolate dessert", item_image="cake.jpg", item_price=Decimal("45.00")),
        ]
        db.add_all(menu_items)
        db.flush()

        orders = [
            Order(customer_id=users[0].user_id, order_type="takeaway", order_status="confirmed", order_date=base_time - timedelta(hours=5)),
            Order(customer_id=users[1].user_id, order_type="delivery", order_status="delivered", order_date=base_time - timedelta(hours=2)),
            Order(customer_id=users[0].user_id, order_type="delivery", order_status="preparing", order_date=base_time - timedelta(minutes=40)),
        ]
        db.add_all(orders)
        db.flush()

        order_items = [
            OrderItem(order_id=orders[0].order_id, item_id=menu_items[0].item_id, item_name=menu_items[0].item_name, item_price=menu_items[0].item_price, item_quantity=2),
            OrderItem(order_id=orders[0].order_id, item_id=menu_items[1].item_id, item_name=menu_items[1].item_name, item_price=menu_items[1].item_price, item_quantity=1),
            OrderItem(order_id=orders[1].order_id, item_id=menu_items[2].item_id, item_name=menu_items[2].item_name, item_price=menu_items[2].item_price, item_quantity=1),
            OrderItem(order_id=orders[1].order_id, item_id=menu_items[4].item_id, item_name=menu_items[4].item_name, item_price=menu_items[4].item_price, item_quantity=2),
            OrderItem(order_id=orders[2].order_id, item_id=menu_items[3].item_id, item_name=menu_items[3].item_name, item_price=menu_items[3].item_price, item_quantity=1),
            OrderItem(order_id=orders[2].order_id, item_id=menu_items[1].item_id, item_name=menu_items[1].item_name, item_price=menu_items[1].item_price, item_quantity=2),
        ]
        db.add_all(order_items)

        deliveries = [
            Delivery(order_id=orders[1].order_id, delivery_service="FastCourier", delivery_status="delivered", delivery_date=base_time - timedelta(hours=1, minutes=20)),
            Delivery(order_id=orders[2].order_id, delivery_service="CityRunner", delivery_status="out_for_delivery", delivery_date=base_time - timedelta(minutes=10)),
        ]
        db.add_all(deliveries)

        transactions = [
            Transaction(order_id=orders[0].order_id, tx_time=base_time - timedelta(hours=5), tx_type="card", tx_amount=Decimal("170.00"), tx_notes="Paid at pickup"),
            Transaction(order_id=orders[1].order_id, tx_time=base_time - timedelta(hours=2), tx_type="online", tx_amount=Decimal("200.00"), tx_notes="Paid by wallet"),
            Transaction(order_id=orders[2].order_id, tx_time=base_time - timedelta(minutes=35), tx_type="cash", tx_amount=Decimal("135.00"), tx_notes="Cash on delivery"),
        ]
        db.add_all(transactions)

        complaints = [
            Complaint(
                customer_id=users[1].user_id,
                order_id=orders[1].order_id,
                complaint_type="late_delivery",
                description="The order arrived later than expected.",
                priority="medium",
                complaint_status="open",
                created_at=base_time - timedelta(hours=1),
            ),
            Complaint(
                customer_id=users[0].user_id,
                order_id=orders[0].order_id,
                complaint_type="wrong_item",
                description="I received a different drink than the one I ordered.",
                priority="high",
                complaint_status="escalated",
                created_at=base_time - timedelta(hours=4, minutes=30),
            ),
        ]
        db.add_all(complaints)

        faq_entries = [
            FAQ(
                question="What are your opening hours?",
                answer="We are open daily from 10:00 AM to 11:00 PM.",
                embedding=json.dumps(get_embedding("What are your opening hours?")),
            ),
            FAQ(
                question="Do you offer delivery?",
                answer="Yes, we offer delivery through our app and website within our service area.",
                embedding=json.dumps(get_embedding("Do you offer delivery?")),
            ),
            FAQ(
                question="How long does delivery usually take?",
                answer="Delivery usually takes between 30 and 45 minutes depending on demand and distance.",
                embedding=json.dumps(get_embedding("How long does delivery usually take?")),
            ),
            FAQ(
                question="Can I customize my order?",
                answer="Yes, you can customize many menu items by adding notes or selecting available options.",
                embedding=json.dumps(get_embedding("Can I customize my order?")),
            ),
            FAQ(
                question="What payment methods do you accept?",
                answer="We accept cash, cards, and supported online payment methods.",
                embedding=json.dumps(get_embedding("What payment methods do you accept?")),
            ),
            FAQ(
                question="Do you have vegetarian options?",
                answer="Yes, we have several vegetarian items on the menu, including pizza, pasta, and sides.",
                embedding=json.dumps(get_embedding("Do you have vegetarian options?")),
            ),
            FAQ(
                question="How can I track my order?",
                answer="You can track your order status from your account in the app after placing it.",
                embedding=json.dumps(get_embedding("How can I track my order?")),
            ),
            FAQ(
                question="Can I cancel an order after placing it?",
                answer="You can request cancellation before the order starts preparation, subject to confirmation.",
                embedding=json.dumps(get_embedding("Can I cancel an order after placing it?")),
            ),
            FAQ(
                question="Do you have desserts?",
                answer="Yes, we offer desserts such as chocolate cake and other seasonal sweet items.",
                embedding=json.dumps(get_embedding("Do you have desserts?")),
            ),
            FAQ(
                question="How do I contact support?",
                answer="You can contact support through the support agent or the help section in the app.",
                embedding=json.dumps(get_embedding("How do I contact support?")),
            ),
        ]
        db.add_all(faq_entries)

        db.commit()

        return {
            "users": len(users),
            "menu_items": len(menu_items),
            "orders": len(orders),
            "order_items": len(order_items),
            "delivery": len(deliveries),
            "transactions": len(transactions),
            "complaints": len(complaints),
            "faqs": len(faq_entries),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    counts = seed_fake_data()
    print("Database reset complete. Seeded rows:")
    for table_name, count in counts.items():
        print(f"- {table_name}: {count}")


if __name__ == "__main__":
    main()