from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.repositories import menu_item as menu_item_repo
from app.core.database import get_db
from app.my_agent.agents.menu_agent import menu_agent
from langchain_core.messages import HumanMessage

router = APIRouter()

@router.get("/", response_model=List[schemas.MenuItem])
def read_menu_items(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    return menu_item_repo.get_multi(db, skip=skip, limit=limit)

@router.post("/", response_model=schemas.MenuItem)
def create_menu_item(
    *,
    db: Session = Depends(get_db),
    item_in: schemas.MenuItemCreate,
) -> Any:
    return menu_item_repo.create(db, obj_in=item_in.__dict__)

@router.get("/{item_id}", response_model=schemas.MenuItem)
def read_menu_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> Any:
    item = menu_item_repo.get(db, id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return item

@router.put("/{item_id}", response_model=schemas.MenuItem)
def update_menu_item(
    *,
    db: Session = Depends(get_db),
    item_id: int,
    item_in: schemas.MenuItemUpdate,
) -> Any:
    item = menu_item_repo.get(db, id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return menu_item_repo.update(db, db_obj=item, obj_in=item_in)

@router.delete("/{item_id}", response_model=schemas.MenuItem)
def delete_menu_item(
    *,
    db: Session = Depends(get_db),
    item_id: int,
) -> Any:
    item = menu_item_repo.get(db, id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return menu_item_repo.remove(db, id=item_id)


@router.post("/ask")
def ask_menu(
    question: str,
    db: Session = Depends(get_db),
):
    final_state=menu_agent(question=question, db=db)

    return {
        "question": question,
        "answer": final_state["response"],
        "iterations": final_state["iteration_count"],
        "satisfied": final_state["reflection_satisfied"],
    }