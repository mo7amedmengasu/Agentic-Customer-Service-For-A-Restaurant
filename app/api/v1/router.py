from fastapi import APIRouter
from app.api.v1 import users, orders, menu_items, order_items, deliveries, transactions

api_router = APIRouter()

api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(menu_items.router, prefix="/menu-items", tags=["menu_items"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(order_items.router, prefix="/order-items", tags=["order_items"])
api_router.include_router(deliveries.router, prefix="/deliveries", tags=["deliveries"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
