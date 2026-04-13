from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class ActivityLogBase(BaseModel):
    action: str
    title: str
    description: str
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    target_user_id: Optional[str] = None
    target_user_name: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ActivityLogCreate(ActivityLogBase):
    pass


class ActivityLogInDB(ActivityLogBase):
    id: str
    created_at: datetime


class ActivityLog(ActivityLogInDB):
    pass
