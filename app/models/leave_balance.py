from pydantic import BaseModel
from typing import Optional


class LeaveBalanceItem(BaseModel):
    total: int
    taken: int
    balance: int


class LeaveBalanceSummary(BaseModel):
    fy_start_year: int
    fy_end_year: int
    sick: LeaveBalanceItem
    wfh: LeaveBalanceItem
    reset_at: Optional[str] = None


class LeaveBalanceSummaryWithUser(LeaveBalanceSummary):
    user_id: str


class LeaveResetRequest(BaseModel):
    sick_total: Optional[int] = None
    wfh_total: Optional[int] = None
    fy_start_year: Optional[int] = None


class BulkLeaveResetRequest(BaseModel):
    fy_start_year: Optional[int] = None

