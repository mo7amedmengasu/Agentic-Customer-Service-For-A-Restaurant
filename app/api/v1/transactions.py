from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.repositories import transaction as transaction_repo
from app.repositories import order as order_repo
from app.core.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Transaction])
def read_transactions(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    return transaction_repo.get_multi(db, skip=skip, limit=limit)

@router.post("/", response_model=schemas.Transaction)
def create_transaction(
    *,
    db: Session = Depends(get_db),
    transaction_in: schemas.TransactionCreate,
) -> Any:
    order = order_repo.get(db, id=transaction_in.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return transaction_repo.create(db, obj_in=transaction_in.__dict__)

@router.get("/{tx_id}", response_model=schemas.Transaction)
def read_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
) -> Any:
    transaction_obj = transaction_repo.get(db, id=tx_id)
    if not transaction_obj:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction_obj

@router.put("/{tx_id}", response_model=schemas.Transaction)
def update_transaction(
    *,
    db: Session = Depends(get_db),
    tx_id: int,
    transaction_in: schemas.TransactionUpdate,
) -> Any:
    transaction_obj = transaction_repo.get(db, id=tx_id)
    if not transaction_obj:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction_repo.update(db, db_obj=transaction_obj, obj_in=transaction_in)

@router.delete("/{tx_id}", response_model=schemas.Transaction)
def delete_transaction(
    *,
    db: Session = Depends(get_db),
    tx_id: int,
) -> Any:
    transaction_obj = transaction_repo.get(db, id=tx_id)
    if not transaction_obj:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction_repo.remove(db, id=tx_id)
