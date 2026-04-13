from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List

from app.models.holiday import Holiday, HolidayCreate, HolidayUpdate
from app.models.user import UserInDB
from app.routers.auth import get_current_active_user
from app.services.holiday_service import HolidayService, get_holiday_service
from app.services.activity_log_service import ActivityLogService, get_activity_log_service
from app.models.activity_log import ActivityLogCreate


router = APIRouter()


@router.get("/", response_model=List[Holiday])
async def list_holidays(
    current_user: UserInDB = Depends(get_current_active_user),
    holiday_service: HolidayService = Depends(get_holiday_service),
):
    return await holiday_service.get_all_holidays()


@router.post("/", response_model=Holiday)
async def create_holiday(
    holiday: HolidayCreate = Body(...),
    current_user: UserInDB = Depends(get_current_active_user),
    holiday_service: HolidayService = Depends(get_holiday_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    try:
        created = await holiday_service.create_holiday(holiday)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="holiday_created",
            title="Holiday created",
            description=f"{actor_name} created a holiday: {created.name}",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            entity_type="holiday",
            entity_id=str(created.id),
            metadata={
                "holiday_name": created.name,
                "holiday_date": str(created.date),
            },
        )
    )

    return created


@router.put("/{holiday_id}", response_model=Holiday)
async def update_holiday(
    holiday_id: str,
    holiday_update: HolidayUpdate = Body(...),
    current_user: UserInDB = Depends(get_current_active_user),
    holiday_service: HolidayService = Depends(get_holiday_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    before = await holiday_service.get_holiday_by_id(holiday_id)
    try:
        updated = await holiday_service.update_holiday(holiday_id, holiday_update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not updated:
        raise HTTPException(status_code=404, detail="Holiday not found")

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="holiday_updated",
            title="Holiday updated",
            description=f"{actor_name} updated a holiday: {updated.name}",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            entity_type="holiday",
            entity_id=str(updated.id),
            metadata={
                "holiday_name": updated.name,
                "holiday_date": str(updated.date),
                "updated_fields": list(holiday_update.dict(exclude_unset=True).keys()),
                "previous": before.dict() if before else None,
            },
        )
    )

    return updated


@router.delete("/{holiday_id}")
async def delete_holiday(
    holiday_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    holiday_service: HolidayService = Depends(get_holiday_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    existing = await holiday_service.get_holiday_by_id(holiday_id)
    deleted = await holiday_service.delete_holiday(holiday_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Holiday not found")

    actor_name = current_user.full_name or current_user.username
    if existing:
        await log_service.create_log(
            ActivityLogCreate(
                action="holiday_deleted",
                title="Holiday deleted",
                description=f"{actor_name} deleted a holiday: {existing.name}",
                actor_id=str(current_user.id),
                actor_name=actor_name,
                entity_type="holiday",
                entity_id=str(existing.id),
                metadata={
                    "holiday_name": existing.name,
                    "holiday_date": str(existing.date),
                },
            )
        )

    return {"success": True}
