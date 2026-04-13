from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime, date

class UserBase(BaseModel):
    email: EmailStr
    username: str
    employee_id: str
    full_name: str = ""
    department: str = ""
    position: str = ""
    location: str = ""
    phone_number: str = ""
    gender: str = ""
    date_of_birth: Optional[date] = None
    profile_image: str = ""
    is_active: bool = True
    is_manager: bool = False
    is_admin: bool = False

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    employee_id: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    location: Optional[str] = None
    phone_number: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    profile_image: Optional[str] = None
    is_active: Optional[bool] = None
    is_manager: Optional[bool] = None
    is_admin: Optional[bool] = None

class UserInDB(UserBase):
    id: str
    hashed_password: str
    created_at: datetime
    updated_at: datetime

class User(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime

class UserInLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
