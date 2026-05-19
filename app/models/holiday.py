from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class HolidayBase(BaseModel):
    name: str
    date: str
    description: Optional[str] = None


class HolidayCreate(HolidayBase):
    pass


class HolidayUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = None


class HolidayInDB(HolidayBase):
    id: str
    created_at: datetime
    updated_at: datetime


class Holiday(HolidayInDB):
    pass
