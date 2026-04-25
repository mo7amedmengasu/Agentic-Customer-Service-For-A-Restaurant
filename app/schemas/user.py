from pydantic import BaseModel, ConfigDict
from typing import Optional

class UserBase(BaseModel):
    user_type: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_tel: Optional[str] = None

class UserCreate(UserBase):
    user_email: str
    user_password: str

class UserUpdate(UserBase):
    user_password: Optional[str] = None

class User(UserBase):
    user_id: int
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: int


class UserLogin(BaseModel):
    user_email: str
    user_password: str
