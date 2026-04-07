from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.repositories import order as order_repo
from app.repositories import user as user_repo
from app.core.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Order])
def read_orders(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    return order_repo.get_multi(db, skip=skip, limit=limit)

@router.post("/", response_model=schemas.Order)
def create_order(
    *,
    db: Session = Depends(get_db),
    order_in: schemas.OrderCreate,
) -> Any:
    user = user_repo.get(db, id=order_in.customer_id)
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found")
    return order_repo.create(db, obj_in=order_in.__dict__)

@router.get("/{order_id}", response_model=schemas.Order)
def read_order(
    order_id: int,
    db: Session = Depends(get_db),
) -> Any:
    order_obj = order_repo.get(db, id=order_id)
    if not order_obj:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_obj

@router.put("/{order_id}", response_model=schemas.Order)
def update_order(
    *,
    db: Session = Depends(get_db),
    order_id: int,
    order_in: schemas.OrderUpdate,
) -> Any:
    order_obj = order_repo.get(db, id=order_id)
    if not order_obj:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_repo.update(db, db_obj=order_obj, obj_in=order_in)

@router.delete("/{order_id}", response_model=schemas.Order)
def delete_order(
    *,
    db: Session = Depends(get_db),
    order_id: int,
) -> Any:
    order_obj = order_repo.get(db, id=order_id)
    if not order_obj:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_repo.remove(db, id=order_id)
