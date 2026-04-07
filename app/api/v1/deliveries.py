from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.repositories import delivery as delivery_repo
from app.repositories import order as order_repo
from app.core.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Delivery])
def read_deliveries(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    return delivery_repo.get_multi(db, skip=skip, limit=limit)

@router.post("/", response_model=schemas.Delivery)
def create_delivery(
    *,
    db: Session = Depends(get_db),
    delivery_in: schemas.DeliveryCreate,
) -> Any:
    order = order_repo.get(db, id=delivery_in.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return delivery_repo.create(db, obj_in=delivery_in.__dict__)

@router.get("/{delivery_id}", response_model=schemas.Delivery)
def read_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
) -> Any:
    delivery_obj = delivery_repo.get(db, id=delivery_id)
    if not delivery_obj:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery_obj

@router.put("/{delivery_id}", response_model=schemas.Delivery)
def update_delivery(
    *,
    db: Session = Depends(get_db),
    delivery_id: int,
    delivery_in: schemas.DeliveryUpdate,
) -> Any:
    delivery_obj = delivery_repo.get(db, id=delivery_id)
    if not delivery_obj:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery_repo.update(db, db_obj=delivery_obj, obj_in=delivery_in)

@router.delete("/{delivery_id}", response_model=schemas.Delivery)
def delete_delivery(
    *,
    db: Session = Depends(get_db),
    delivery_id: int,
) -> Any:
    delivery_obj = delivery_repo.get(db, id=delivery_id)
    if not delivery_obj:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery_repo.remove(db, id=delivery_id)
