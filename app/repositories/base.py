from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from sqlalchemy.orm import Session
from app.core.database import Base
from pydantic import BaseModel

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        """
        Base Repository with common CRUD operations
        """
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        """Get a single record by primary key."""
        return db.get(self.model, id)

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Get multiple records with skip and limit."""
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> ModelType:
        """Create a new record."""
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, *, db_obj: ModelType, obj_in: Union[Dict[str, Any], BaseModel]) -> ModelType:
        """Update an existing record."""
        obj_data = db_obj.__dict__
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
            
        for field in update_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])
                
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: Any) -> Optional[ModelType]:
        """Delete a record by primary key."""
        obj = db.get(self.model, id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj
