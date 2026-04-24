from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PhysicalCalendarEntryBase(BaseModel):
    fy_start_year: int
    date: str
    name: str


class PhysicalCalendarEntryCreate(PhysicalCalendarEntryBase):
    pass


class PhysicalCalendarEntryUpdate(BaseModel):
    fy_start_year: Optional[int] = None
    date: Optional[str] = None
    name: Optional[str] = None


class PhysicalCalendarEntryInDB(PhysicalCalendarEntryBase):
    id: str
    created_at: datetime
    updated_at: datetime


class PhysicalCalendarEntry(PhysicalCalendarEntryInDB):
    pass
