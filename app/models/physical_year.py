from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PhysicalYearBase(BaseModel):
    fy_start_year: int
    name: Optional[str] = None


class PhysicalYearCreate(PhysicalYearBase):
    pass


class PhysicalYearUpdate(BaseModel):
    fy_start_year: Optional[int] = None
    name: Optional[str] = None


class PhysicalYearInDB(PhysicalYearBase):
    id: str
    created_at: datetime
    updated_at: datetime


class PhysicalYear(PhysicalYearInDB):
    pass
