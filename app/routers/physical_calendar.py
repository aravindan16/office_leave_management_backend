from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.user import UserInDB
from app.routers.auth import get_current_active_user
from app.models.physical_calendar_entry import (
    PhysicalCalendarEntry,
    PhysicalCalendarEntryCreate,
    PhysicalCalendarEntryUpdate,
)
from app.services.physical_calendar_service import PhysicalCalendarService, get_physical_calendar_service
from app.services.activity_log_service import ActivityLogService, get_activity_log_service
from app.models.activity_log import ActivityLogCreate


router = APIRouter()


@router.get("/", response_model=List[PhysicalCalendarEntry])
async def list_physical_calendar_entries(
    fy_start_year: int,
    current_user: UserInDB = Depends(get_current_active_user),
    calendar_service: PhysicalCalendarService = Depends(get_physical_calendar_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return await calendar_service.list_entries(int(fy_start_year))


@router.post("/", response_model=PhysicalCalendarEntry)
async def create_physical_calendar_entry(
    payload: PhysicalCalendarEntryCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    calendar_service: PhysicalCalendarService = Depends(get_physical_calendar_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    try:
        created = await calendar_service.create_entry(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="physical_calendar_entry_created",
            title="Physical calendar entry created",
            description=f"{actor_name} created physical calendar entry",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            entity_type="physical_calendar_entry",
            entity_id=str(created.id),
            metadata={
                "fy_start_year": created.fy_start_year,
                "date": created.date,
                "name": created.name,
            },
        )
    )

    return created


@router.put("/{entry_id}", response_model=PhysicalCalendarEntry)
async def update_physical_calendar_entry(
    entry_id: str,
    payload: PhysicalCalendarEntryUpdate,
    current_user: UserInDB = Depends(get_current_active_user),
    calendar_service: PhysicalCalendarService = Depends(get_physical_calendar_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    before = await calendar_service.get_by_id(entry_id)
    if not before:
        raise HTTPException(status_code=404, detail="Entry not found")

    try:
        updated = await calendar_service.update_entry(entry_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found")

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="physical_calendar_entry_updated",
            title="Physical calendar entry updated",
            description=f"{actor_name} updated physical calendar entry",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            entity_type="physical_calendar_entry",
            entity_id=str(updated.id),
            metadata={
                "fy_start_year_before": before.fy_start_year,
                "fy_start_year": updated.fy_start_year,
                "date_before": before.date,
                "date": updated.date,
                "name_before": before.name,
                "name": updated.name,
            },
        )
    )

    return updated


@router.delete("/{entry_id}", status_code=204)
async def delete_physical_calendar_entry(
    entry_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    calendar_service: PhysicalCalendarService = Depends(get_physical_calendar_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    existing = await calendar_service.get_by_id(entry_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")

    deleted = await calendar_service.delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="physical_calendar_entry_deleted",
            title="Physical calendar entry deleted",
            description=f"{actor_name} deleted physical calendar entry",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            entity_type="physical_calendar_entry",
            entity_id=str(existing.id),
            metadata={
                "fy_start_year": existing.fy_start_year,
                "date": existing.date,
                "name": existing.name,
            },
        )
    )

    return None
