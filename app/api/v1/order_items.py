from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.repositories import order_item as order_item_repo
from app.repositories import order as order_repo
from app.repositories import menu_item as menu_item_repo
from app.core.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.OrderItem])
def read_order_items(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    return order_item_repo.get_multi(db, skip=skip, limit=limit)

@router.post("/", response_model=schemas.OrderItem)
def create_order_item(
    *,
    db: Session = Depends(get_db),
    order_item_in: schemas.OrderItemCreate,
) -> Any:
    order_obj = order_repo.get(db, id=order_item_in.order_id)
    if not order_obj:
        raise HTTPException(status_code=404, detail="Order not found")
        
    menu_item_obj = menu_item_repo.get(db, id=order_item_in.item_id)
    if not menu_item_obj:
        raise HTTPException(status_code=404, detail="Menu item not found")
        
    # Handle composite primary key for creation specifically if needed, 
    # but the base repo will pass **dict to the model
    return order_item_repo.create(db, obj_in=order_item_in.__dict__)

# OrderItem uses composite PK (order_id, item_id), so we use a route that takes both
@router.get("/{order_id}/{item_id}", response_model=schemas.OrderItem)
def read_order_item(
    order_id: int,
    item_id: int,
    db: Session = Depends(get_db),
) -> Any:
    # get_by_order & get_by_menu_item or we can just query it
    item = db.query(order_item_repo.model).filter_by(order_id=order_id, item_id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")
    return item

@router.put("/{order_id}/{item_id}", response_model=schemas.OrderItem)
def update_order_item(
    *,
    db: Session = Depends(get_db),
    order_id: int,
    item_id: int,
    item_in: schemas.OrderItemUpdate,
) -> Any:
    item = db.query(order_item_repo.model).filter_by(order_id=order_id, item_id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")
    return order_item_repo.update(db, db_obj=item, obj_in=item_in)

@router.delete("/{order_id}/{item_id}", response_model=schemas.OrderItem)
def delete_order_item(
    *,
    db: Session = Depends(get_db),
    order_id: int,
    item_id: int,
) -> Any:
    item = db.query(order_item_repo.model).filter_by(order_id=order_id, item_id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")
    db.delete(item)
    db.commit()
    return item
