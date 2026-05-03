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


def _ensure_menu_embedding_column() -> None:
    """Add item_embedding column to menu_items if it doesn't exist yet (schema migration helper)."""
    dialect = engine.dialect.name.lower()
    with engine.begin() as connection:
        if dialect.startswith("postgres"):
            connection.execute(
                text(
                    "ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS item_embedding TEXT"
                )
            )
        else:
            # SQLite: check via pragma
            cols = connection.execute(text("PRAGMA table_info(menu_items)")).fetchall()
            col_names = [row[1] for row in cols]
            if "item_embedding" not in col_names:
                connection.execute(
                    text("ALTER TABLE menu_items ADD COLUMN item_embedding TEXT")
                )


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
    _ensure_menu_embedding_column()
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

        menu_item_data = [
            # ── Burgers & Sandwiches ──────────────────────────────────────────
            ("Classic Beef Burger",      "Grilled beef patty with lettuce, tomato, and pickles",        "burger.jpg",        Decimal("75.00")),
            ("Crispy Chicken Sandwich",  "Fried chicken fillet with coleslaw and mayo",                 "chicken_sand.jpg",  Decimal("70.00")),
            ("Veggie Burger",            "Plant-based patty with avocado, lettuce, and tomato (V)",     "veggie_burger.jpg", Decimal("65.00")),

            # ── Pizzas ────────────────────────────────────────────────────────
            ("Margherita Pizza",         "Classic tomato sauce with mozzarella and fresh basil (V)",    "pizza.jpg",         Decimal("110.00")),
            ("Pepperoni Pizza",          "Spicy pepperoni on rich tomato sauce and mozzarella",         "pepperoni.jpg",     Decimal("125.00")),
            ("Veggie Supreme Pizza",     "Bell peppers, mushrooms, olives, onion, and mozzarella (V)",  "veggie_pizza.jpg",  Decimal("115.00")),

            # ── Pasta ─────────────────────────────────────────────────────────
            ("Pasta Alfredo",            "Creamy chicken alfredo with parmesan",                        "pasta.jpg",         Decimal("95.00")),
            ("Pesto Pasta",              "Basil pesto, cherry tomatoes, and pine nuts (V)",             "pesto_pasta.jpg",   Decimal("90.00")),
            ("Pasta Arrabbiata",         "Spicy tomato sauce with garlic and chilli flakes (V)",        "arrabbiata.jpg",    Decimal("85.00")),

            # ── Salads & Sides ────────────────────────────────────────────────
            ("Garden Salad",             "Mixed greens, cucumber, tomato, and lemon dressing (V)",      "salad.jpg",         Decimal("40.00")),
            ("Caesar Salad",             "Romaine lettuce, croutons, parmesan, and Caesar dressing",    "caesar.jpg",        Decimal("50.00")),
            ("French Fries",             "Crispy golden fries with ketchup",                            "fries.jpg",         Decimal("30.00")),
            ("Onion Rings",              "Beer-battered onion rings with dipping sauce (V)",            "onion_rings.jpg",   Decimal("35.00")),

            # ── Desserts ──────────────────────────────────────────────────────
            ("Chocolate Cake",           "Rich moist chocolate layer cake (V)",                         "cake.jpg",          Decimal("45.00")),
            ("Cheesecake",               "New York-style vanilla cheesecake with berry compote (V)",    "cheesecake.jpg",    Decimal("50.00")),

            # ── Drinks ───────────────────────────────────────────────────────
            ("Cola",                     "Chilled can of cola",                                         "cola.jpg",          Decimal("20.00")),
            ("Fresh Orange Juice",       "Freshly squeezed orange juice (V)",                           "oj.jpg",            Decimal("30.00")),
            ("Mineral Water",            "Still mineral water 500 ml (V)",                              "water.jpg",         Decimal("10.00")),
        ]

        print("Computing menu item embeddings…")
        menu_items = []
        for name, description, image, price in menu_item_data:
            embedding_text = f"{name}: {description}"
            embedding = get_embedding(embedding_text)
            menu_items.append(
                MenuItem(
                    item_name=name,
                    item_description=description,
                    item_image=image,
                    item_price=price,
                    item_embedding=json.dumps(embedding),
                )
            )
        db.add_all(menu_items)
        db.flush()

        orders = [
            Order(customer_id=users[0].user_id, order_type="takeaway", order_status="confirmed", order_date=base_time - timedelta(hours=5)),
            Order(customer_id=users[1].user_id, order_type="delivery", order_status="delivered", order_date=base_time - timedelta(hours=2)),
            Order(customer_id=users[0].user_id, order_type="delivery", order_status="preparing", order_date=base_time - timedelta(minutes=40)),
        ]
        db.add_all(orders)
        db.flush()

        # Indices: 0=Classic Beef Burger, 1=Crispy Chicken Sandwich, 2=Veggie Burger,
        #          3=Margherita Pizza, 4=Pepperoni Pizza, 5=Veggie Supreme Pizza,
        #          6=Pasta Alfredo, 7=Pesto Pasta, 8=Pasta Arrabbiata,
        #          9=Garden Salad, 10=Caesar Salad, 11=French Fries, 12=Onion Rings,
        #          13=Chocolate Cake, 14=Cheesecake,
        #          15=Cola, 16=Fresh Orange Juice, 17=Mineral Water
        order_items = [
            OrderItem(order_id=orders[0].order_id, item_id=menu_items[0].item_id, item_name=menu_items[0].item_name, item_price=menu_items[0].item_price, item_quantity=2),
            OrderItem(order_id=orders[0].order_id, item_id=menu_items[15].item_id, item_name=menu_items[15].item_name, item_price=menu_items[15].item_price, item_quantity=2),
            OrderItem(order_id=orders[0].order_id, item_id=menu_items[11].item_id, item_name=menu_items[11].item_name, item_price=menu_items[11].item_price, item_quantity=1),
            OrderItem(order_id=orders[1].order_id, item_id=menu_items[3].item_id, item_name=menu_items[3].item_name, item_price=menu_items[3].item_price, item_quantity=1),
            OrderItem(order_id=orders[1].order_id, item_id=menu_items[13].item_id, item_name=menu_items[13].item_name, item_price=menu_items[13].item_price, item_quantity=2),
            OrderItem(order_id=orders[1].order_id, item_id=menu_items[16].item_id, item_name=menu_items[16].item_name, item_price=menu_items[16].item_price, item_quantity=1),
            OrderItem(order_id=orders[2].order_id, item_id=menu_items[2].item_id, item_name=menu_items[2].item_name, item_price=menu_items[2].item_price, item_quantity=1),
            OrderItem(order_id=orders[2].order_id, item_id=menu_items[9].item_id, item_name=menu_items[9].item_name, item_price=menu_items[9].item_price, item_quantity=1),
            OrderItem(order_id=orders[2].order_id, item_id=menu_items[17].item_id, item_name=menu_items[17].item_name, item_price=menu_items[17].item_price, item_quantity=1),
        ]
        db.add_all(order_items)

        deliveries = [
            Delivery(order_id=orders[1].order_id, delivery_service="FastCourier", delivery_status="delivered", delivery_date=base_time - timedelta(hours=1, minutes=20)),
            Delivery(order_id=orders[2].order_id, delivery_service="CityRunner", delivery_status="out_for_delivery", delivery_date=base_time - timedelta(minutes=10)),
        ]
        db.add_all(deliveries)

        # Order 0: 2×Beef Burger(75) + 2×Cola(20) + 1×Fries(30) = 220
        # Order 1: 1×Margherita(110) + 2×Choc Cake(45) + 1×OJ(30) = 230
        # Order 2: 1×Veggie Burger(65) + 1×Garden Salad(40) + 1×Water(10) = 115
        transactions = [
            Transaction(order_id=orders[0].order_id, tx_time=base_time - timedelta(hours=5), tx_type="card", tx_amount=Decimal("220.00"), tx_notes="Paid at pickup"),
            Transaction(order_id=orders[1].order_id, tx_time=base_time - timedelta(hours=2), tx_type="online", tx_amount=Decimal("230.00"), tx_notes="Paid by wallet"),
            Transaction(order_id=orders[2].order_id, tx_time=base_time - timedelta(minutes=35), tx_type="cash", tx_amount=Decimal("115.00"), tx_notes="Cash on delivery"),
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

        faq_data = [
            # General
            ("What are your opening hours?",
             "We are open every day from 10:00 AM to 11:00 PM, including weekends and public holidays."),
            ("Where are you located?",
             "We are located at 14 Nile Corniche Street, Cairo. You can also find us on Google Maps by searching our restaurant name."),
            ("Do you have a dine-in area?",
             "Yes, we have a comfortable dine-in area with seating for up to 80 guests. Reservations are recommended during peak hours."),
            ("How do I make a reservation?",
             "You can make a reservation by calling us, messaging us through the app, or booking through our website."),
            ("Is there parking available?",
             "Yes, we have a free parking area for up to 20 cars right next to the restaurant."),

            # Menu & Dietary
            ("Do you have vegetarian options?",
             "Absolutely! We have a wide range of vegetarian options including Veggie Burger, Margherita Pizza, Veggie Supreme Pizza, Pesto Pasta, Pasta Arrabbiata, Garden Salad, Onion Rings, and more. Items marked (V) on our menu are vegetarian."),
            ("Do you have vegan options?",
             "Some of our vegetarian dishes can be made vegan on request — for example, our Garden Salad and Pasta Arrabbiata. Please mention your preference when ordering and our team will do their best to accommodate."),
            ("Do you have gluten-free options?",
             "We currently do not have a dedicated gluten-free menu, but please inform us of any allergies when you order and we will advise you on safe choices."),
            ("What allergens are in your food?",
             "Our dishes may contain gluten, dairy, eggs, nuts, and soy. Please let us know about any allergies before ordering and we will provide detailed ingredient information."),
            ("Do you have desserts?",
             "Yes! We have Chocolate Cake and New York-style Cheesecake. Both are available for dine-in, takeaway, and delivery."),
            ("What drinks do you serve?",
             "We serve Cola, Fresh Orange Juice, and Mineral Water. We also have seasonal specials — ask your server or check the app for the latest."),
            ("Are your ingredients fresh?",
             "Yes, we source fresh ingredients daily from local suppliers to ensure the best quality in every dish."),

            # Ordering
            ("How can I place an order?",
             "You can order through our app, website, or by speaking to one of our staff if you're dining in."),
            ("Can I customize my order?",
             "Yes! You can add notes to your order — for example, requesting no onions, extra sauce, or a specific cooking preference."),
            ("What is the minimum order for delivery?",
             "The minimum order amount for delivery is 80 EGP."),
            ("Can I order for a group?",
             "Of course! For large group orders (10+ people), we recommend calling us in advance so we can prepare everything on time."),

            # Delivery
            ("Do you offer delivery?",
             "Yes, we offer delivery through our app and website to all areas within our service zone."),
            ("How long does delivery take?",
             "Delivery usually takes between 30 and 45 minutes. During busy hours it may take slightly longer."),
            ("How can I track my order?",
             "Once your order is confirmed, you can track its status in real time from the Orders section in the app."),
            ("What is your delivery fee?",
             "The delivery fee is 15 EGP flat for all orders within our delivery zone."),
            ("Do you deliver outside your zone?",
             "Currently we only deliver within our designated service area. You can check if your address is covered in the app when placing an order."),

            # Payment
            ("What payment methods do you accept?",
             "We accept cash on delivery, debit and credit cards, and online payment via our app wallet."),
            ("Can I pay online?",
             "Yes, you can pay securely through the app using your saved card or wallet balance."),
            ("Do you issue receipts?",
             "Yes, a digital receipt is sent to your registered email after every completed order."),

            # Cancellations & Refunds
            ("Can I cancel my order?",
             "You can cancel your order before it moves to the preparing stage. Once preparation has started, cancellations are no longer possible."),
            ("How do I get a refund?",
             "If there is an issue with your order, please contact our support agent and we will review your case. Approved refunds are processed within 3–5 business days."),
            ("What if I received the wrong item?",
             "We apologize for the mistake! Please contact our support agent and we will arrange a replacement or refund as quickly as possible."),

            # Support
            ("How do I contact customer support?",
             "You can reach our support team directly through the chat assistant in the app, which is available 24/7."),
            ("How do I file a complaint?",
             "Simply tell our chat assistant what went wrong and we will open a support ticket for you immediately."),
            ("How long does it take to resolve a complaint?",
             "Most complaints are reviewed within 24 hours. Urgent issues such as missing or wrong items are prioritized and handled faster."),
        ]
        print("Computing FAQ embeddings…")
        faq_entries = [
            FAQ(
                question=q,
                answer=a,
                embedding=json.dumps(get_embedding(q)),
            )
            for q, a in faq_data
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