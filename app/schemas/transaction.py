from pydantic import BaseModel, ConfigDict
from typing import Optional
from decimal import Decimal
from datetime import datetime

class TransactionBase(BaseModel):
    order_id: int
    tx_time: datetime
    tx_type: str
    tx_amount: Decimal
    tx_notes: Optional[str] = None

class TransactionCreate(TransactionBase):
    pass

class TransactionUpdate(BaseModel):
    tx_time: Optional[datetime] = None
    tx_type: Optional[str] = None
    tx_amount: Optional[Decimal] = None
    tx_notes: Optional[str] = None

class Transaction(TransactionBase):
    tx_id: int
    model_config = ConfigDict(from_attributes=True)
