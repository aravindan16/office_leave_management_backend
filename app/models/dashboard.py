from pydantic import BaseModel
from typing import List, Optional


class DashboardEmployee(BaseModel):
    id: str
    full_name: str = ""
    username: str
    email: str
    position: str = ""
    profile_image: str = ""
    date_of_birth: Optional[str] = None


class DashboardBirthdayItem(BaseModel):
    user: DashboardEmployee
    next_birthday: str


class DashboardUpcomingItem(BaseModel):
    id: str
    request_type: str
    leave_type: str
    start_date: str
    end_date: str
    employee: DashboardEmployee


class DashboardSummary(BaseModel):
    birthdays_this_month: List[DashboardBirthdayItem]
    upcoming_approved: List[DashboardUpcomingItem]
