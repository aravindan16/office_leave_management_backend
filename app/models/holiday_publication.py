from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class HolidaySnapshotItem(BaseModel):
    name: str
    date: str
    description: Optional[str] = None


class HolidayYearPublication(BaseModel):
    year: int
    published: bool
    updated_at: datetime
    holidays: List[HolidaySnapshotItem] = []
    dirty: bool = False
