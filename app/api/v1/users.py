from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.repositories import user as user_repo
from app.core.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.User])
def read_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    users = user_repo.get_multi(db, skip=skip, limit=limit)
    return users

@router.post("/", response_model=schemas.User)
def create_user(
    *,
    db: Session = Depends(get_db),
    user_in: schemas.UserCreate,
) -> Any:
    user = user_repo.get_by_email(db, email=user_in.user_email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    user = user_repo.create(db, obj_in=user_in.__dict__)
    return user

@router.get("/{user_id}", response_model=schemas.User)
def read_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
) -> Any:
    user = user_repo.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=schemas.User)
def update_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    user_in: schemas.UserUpdate,
) -> Any:
    user = user_repo.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = user_repo.update(db, db_obj=user, obj_in=user_in)
    return user

@router.delete("/{user_id}", response_model=schemas.User)
def delete_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
) -> Any:
    user = user_repo.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = user_repo.remove(db, id=user_id)
    return user
