from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ResumeBase(BaseModel):
    employee_id: str       
    role_applied: str   
    notes: Optional[str] = ""


class ResumeCreate(ResumeBase):
    pass                  

class ResumeUpdate(BaseModel):
    role_applied: Optional[str] = None
    notes: Optional[str] = None


class Resume(ResumeBase):
    id: str
    user_id: str            
    file_name: str         
    file_size: int
    content_type: str
    uploaded_by_id: str
    uploaded_by_name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResumeInDB(Resume):
    file_data: str        


class ResumeListItem(BaseModel):
    id: str
    employee_id: str
    user_id: str
    role_applied: str
    notes: Optional[str]
    file_name: str
    file_size: int
    content_type: str
    uploaded_by_id: str
    uploaded_by_name: str
    created_at: datetime
    updated_at: datetime