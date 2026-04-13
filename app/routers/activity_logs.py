from fastapi import APIRouter, Depends
from typing import List

from app.models.activity_log import ActivityLog
from app.models.user import UserInDB
from app.routers.auth import get_current_active_user
from app.services.activity_log_service import ActivityLogService, get_activity_log_service


router = APIRouter()


@router.get("/", response_model=List[ActivityLog])
async def get_activity_logs(
    skip: int = 0,
    limit: int = 50,
    current_user: UserInDB = Depends(get_current_active_user),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if current_user.is_admin or current_user.is_manager:
        return await log_service.get_logs(skip=skip, limit=limit)
    return await log_service.get_logs_for_user(str(current_user.id), skip=skip, limit=limit)
