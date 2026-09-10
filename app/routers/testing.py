from fastapi import APIRouter, Depends, HTTPException

from app.models.user import UserInDB
from app.routers.auth import get_current_active_user
from app.services.testing_service import TestingSettings, TestingToggleUpdate, TestingService, get_testing_service

router = APIRouter()


@router.get("/", response_model=TestingSettings)
async def get_testing_settings(
    current_user: UserInDB = Depends(get_current_active_user),
    service: TestingService = Depends(get_testing_service),
):
    return await service.get_settings(str(current_user.id) if current_user.is_admin else None)


@router.put("/", response_model=TestingSettings)
async def update_testing_settings(
    settings: TestingToggleUpdate,
    current_user: UserInDB = Depends(get_current_active_user),
    service: TestingService = Depends(get_testing_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can change testing settings.")
    return await service.set_enabled(settings.enabled, str(current_user.id))
