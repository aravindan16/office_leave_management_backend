from pydantic import BaseModel
from pydantic import model_validator
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
    UNPAID = "unpaid"
    VACATION = "vacation"
    PERSONAL = "personal"
    MATERNITY = "maternity"
    PATERNITY = "paternity"

class RequestType(str, Enum):
    LEAVE = "leave"
    WFH = "wfh"

class LeaveBase(BaseModel):
    request_type: RequestType = RequestType.LEAVE
    leave_type: Optional[LeaveType] = LeaveType.VACATION
    start_date: date
    end_date: date
    duration_days: Optional[float] = None
    reason: str
    manager_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_request_type(self):
        if self.request_type == RequestType.WFH:
            self.leave_type = None
            return self

        if self.leave_type is None:
            raise ValueError("leave_type is required when request_type is leave")
        if self.duration_days is not None:
            if self.duration_days <= 0:
                raise ValueError("duration_days must be greater than 0")
            if self.duration_days == 0.5 and self.start_date != self.end_date:
                raise ValueError("Half-day leave must start and end on the same date")
        return self

class LeaveCreate(LeaveBase):
    pass

class LeaveUpdate(BaseModel):
    leave_type: Optional[LeaveType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_days: Optional[float] = None
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
