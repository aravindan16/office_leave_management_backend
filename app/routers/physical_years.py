from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.user import UserInDB
from app.routers.auth import get_current_active_user
from app.models.physical_year import PhysicalYear, PhysicalYearCreate, PhysicalYearUpdate
from app.services.physical_year_service import PhysicalYearService, get_physical_year_service
from app.services.physical_calendar_service import PhysicalCalendarService, get_physical_calendar_service
from app.services.activity_log_service import ActivityLogService, get_activity_log_service
from app.models.activity_log import ActivityLogCreate


router = APIRouter()


@router.get("/", response_model=List[PhysicalYear])
async def list_physical_years(
    current_user: UserInDB = Depends(get_current_active_user),
    year_service: PhysicalYearService = Depends(get_physical_year_service),
):
    return await year_service.list_years()


@router.post("/", response_model=PhysicalYear)
async def create_physical_year(
    payload: PhysicalYearCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    year_service: PhysicalYearService = Depends(get_physical_year_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    try:
        created = await year_service.create_year(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="physical_year_created",
            title="Physical year created",
            description=f"{actor_name} created physical year FY {created.fy_start_year}-{str(created.fy_start_year + 1)[-2:]}",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            entity_type="physical_year",
            entity_id=str(created.id),
            metadata={
                "fy_start_year": created.fy_start_year,
                "name": created.name,
            },
        )
    )

    return created


@router.put("/{year_id}", response_model=PhysicalYear)
async def update_physical_year(
    year_id: str,
    payload: PhysicalYearUpdate,
    current_user: UserInDB = Depends(get_current_active_user),
    year_service: PhysicalYearService = Depends(get_physical_year_service),
    calendar_service: PhysicalCalendarService = Depends(get_physical_calendar_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    before = await year_service.get_by_id(year_id)
    if not before:
        raise HTTPException(status_code=404, detail="Physical year not found")

    try:
        updated = await year_service.update_year(year_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not updated:
        raise HTTPException(status_code=404, detail="Physical year not found")

    if payload.fy_start_year is not None and int(payload.fy_start_year) != int(before.fy_start_year):
        await calendar_service.collection.update_many(
            {"fy_start_year": int(before.fy_start_year)},
            {"$set": {"fy_start_year": int(updated.fy_start_year)}},
        )

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="physical_year_updated",
            title="Physical year updated",
            description=f"{actor_name} updated physical year FY {before.fy_start_year}-{str(before.fy_start_year + 1)[-2:]}",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            entity_type="physical_year",
            entity_id=str(updated.id),
            metadata={
                "fy_start_year_before": before.fy_start_year,
                "fy_start_year": updated.fy_start_year,
                "name_before": before.name,
                "name": updated.name,
            },
        )
    )

    return updated


@router.delete("/{year_id}", status_code=204)
async def delete_physical_year(
    year_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    year_service: PhysicalYearService = Depends(get_physical_year_service),
    calendar_service: PhysicalCalendarService = Depends(get_physical_calendar_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    existing = await year_service.get_by_id(year_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Physical year not found")

    await calendar_service.collection.delete_many({"fy_start_year": int(existing.fy_start_year)})
    deleted = await year_service.delete_year(year_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Physical year not found")

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="physical_year_deleted",
            title="Physical year deleted",
            description=f"{actor_name} deleted physical year FY {existing.fy_start_year}-{str(existing.fy_start_year + 1)[-2:]}",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            entity_type="physical_year",
            entity_id=str(existing.id),
            metadata={
                "fy_start_year": existing.fy_start_year,
                "name": existing.name,
            },
        )
    )

    return None
