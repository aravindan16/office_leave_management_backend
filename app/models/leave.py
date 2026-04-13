from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from enum import Enum

class LeaveStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class LeaveType(str, Enum):
    SICK = "sick"
    VACATION = "vacation"
    PERSONAL = "personal"
    MATERNITY = "maternity"
    PATERNITY = "paternity"

class LeaveBase(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str
    manager_id: Optional[str] = None

class LeaveCreate(LeaveBase):
    pass

class LeaveUpdate(BaseModel):
    leave_type: Optional[LeaveType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    reason: Optional[str] = None
    status: Optional[LeaveStatus] = None
    manager_comment: Optional[str] = None

class LeaveInDB(LeaveBase):
    id: str
    employee_id: str
    status: LeaveStatus
    manager_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class Leave(LeaveBase):
    id: str
    employee_id: str
    status: LeaveStatus
    manager_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime
