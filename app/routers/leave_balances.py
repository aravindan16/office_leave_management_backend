from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.leave_balance import (
    LeaveBalanceSummary,
    LeaveBalanceSummaryWithUser,
    LeaveResetRequest,
    BulkLeaveResetRequest,
)
from app.models.user import UserInDB
from app.routers.auth import get_current_active_user
from app.services.leave_balance_service import LeaveBalanceService, get_leave_balance_service
from app.services.user_service import UserService, get_user_service
from app.services.activity_log_service import ActivityLogService, get_activity_log_service
from app.models.activity_log import ActivityLogCreate
from bson import ObjectId


router = APIRouter()

def get_current_fy_start_year() -> int:
    from datetime import datetime
    now = datetime.utcnow()
    return now.year if now.month >= 4 else now.year - 1


@router.get("/me", response_model=LeaveBalanceSummary)
async def get_my_leave_balance(
    current_user: UserInDB = Depends(get_current_active_user),
    balance_service: LeaveBalanceService = Depends(get_leave_balance_service),
    fy_start_year: Optional[int] = None,
):
    return await balance_service.get_balance_for_user(str(current_user.id), fy_start_year=fy_start_year)


@router.get("/users", response_model=List[LeaveBalanceSummaryWithUser])
async def get_users_leave_balances(
    current_user: UserInDB = Depends(get_current_active_user),
    balance_service: LeaveBalanceService = Depends(get_leave_balance_service),
    user_service: UserService = Depends(get_user_service),
    fy_start_year: Optional[int] = None,
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    users = await user_service.get_all_users(exclude_admins=True)
    user_ids = [str(u.id) for u in users]
    return await balance_service.get_balances_for_users(user_ids, fy_start_year=fy_start_year)


@router.post("/users/{user_id}/reset", status_code=204)
async def reset_user_leave_entitlement(
    user_id: str,
    reset_data: Optional[LeaveResetRequest] = None,
    current_user: UserInDB = Depends(get_current_active_user),
    balance_service: LeaveBalanceService = Depends(get_leave_balance_service),
    user_service: UserService = Depends(get_user_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    target_user = await user_service.get_user_by_id(user_id)
    target_name = None
    if target_user:
        target_name = target_user.full_name or target_user.username

    sick_total_before = None
    wfh_total_before = None
    fy_before = None
    if ObjectId.is_valid(str(user_id)):
        existing = await balance_service.entitlements.find_one({"user_id": ObjectId(str(user_id))}, sort=[("fy_start_year", -1)])
        if existing:
            sick_total_before = existing.get("sick_total")
            wfh_total_before = existing.get("wfh_total")
            fy_before = existing.get("fy_start_year")

    try:
        sick_total = reset_data.sick_total if reset_data else None
        wfh_total = reset_data.wfh_total if reset_data else None
        fy_year = reset_data.fy_start_year if reset_data else None
        
        await balance_service.reset_entitlement_to_default(
            user_id, 
            sick_total=sick_total, 
            wfh_total=wfh_total, 
            fy_start_year=fy_year
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="leave_balance_reset",
            title="Leave balance reset",
            description=f"{actor_name} reset leave balance for {target_name or user_id}",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            target_user_id=str(user_id),
            target_user_name=target_name,
            entity_type="leave_balance",
            entity_id=str(user_id),
            metadata={
                "fy_start_year": fy_year,
                "sick_total": sick_total,
                "wfh_total": wfh_total,
                "fy_start_year_before": fy_before,
                "sick_total_before": sick_total_before,
                "wfh_total_before": wfh_total_before,
            },
        )
    )

    return None


@router.post("/users/reset-all-leave", status_code=204)
async def reset_leave_for_all_users(
    reset_data: Optional[BulkLeaveResetRequest] = None,
    current_user: UserInDB = Depends(get_current_active_user),
    balance_service: LeaveBalanceService = Depends(get_leave_balance_service),
    user_service: UserService = Depends(get_user_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    next_fy_start_year = get_current_fy_start_year() + 1
    target_fy = int(reset_data.fy_start_year) if reset_data and reset_data.fy_start_year else next_fy_start_year

    users = await user_service.get_all_users(exclude_admins=True)
    user_ids = [str(u.id) for u in users]
    await balance_service.reset_sick_leave_for_all_users(user_ids, fy_start_year=target_fy)

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="leave_balance_bulk_reset",
            title="Leave balance reset for all users",
            description=f"{actor_name} reset sick leave for all users for FY {target_fy}-{str(target_fy + 1)[-2:]}",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            entity_type="leave_balance",
            entity_id="all_users",
            metadata={
                "scope": "all_users",
                "fy_start_year": target_fy,
                "sick_total": 12,
                "wfh_changed": False,
            },
        )
    )

    return None

