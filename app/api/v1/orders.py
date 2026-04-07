from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse, OrderStatus
from app.services.order_service import OrderService
from app.api.deps import get_current_active_user, get_current_superuser
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new order."""
    service = OrderService(db)
    return service.create_order(current_user.id, order_data)


@router.get("/", response_model=List[OrderResponse])
def get_my_orders(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's orders."""
    service = OrderService(db)
    return service.get_user_orders(current_user.id, skip=skip, limit=limit)


@router.get("/all", response_model=List[OrderResponse])
def get_all_orders(
    skip: int = 0,
    limit: int = 100,
    status: OrderStatus = None,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Get all orders (admin only)."""
    service = OrderService(db)
    if status:
        return service.get_orders_by_status(status, skip=skip, limit=limit)
    return service.get_all_orders(skip=skip, limit=limit)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific order."""
    service = OrderService(db)
    order = service.get_order(order_id)
    
    # Users can only see their own orders, admins can see all
    if order.user_id != current_user.id and not current_user.is_superuser:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return order


@router.put("/{order_id}", response_model=OrderResponse)
def update_order(
    order_id: int,
    order_data: OrderUpdate,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Update an order (admin only)."""
    service = OrderService(db)
    return service.update_order(order_id, order_data)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cancel an order."""
    service = OrderService(db)
    return service.cancel_order(order_id, current_user.id)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(
    order_id: int,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Delete an order (admin only)."""
    service = OrderService(db)
    service.delete_order(order_id)
