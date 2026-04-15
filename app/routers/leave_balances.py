from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.leave_balance import LeaveBalanceSummary, LeaveBalanceSummaryWithUser, LeaveResetRequest
from app.models.user import UserInDB
from app.routers.auth import get_current_active_user
from app.services.leave_balance_service import LeaveBalanceService, get_leave_balance_service
from app.services.user_service import UserService, get_user_service


router = APIRouter()


@router.get("/me", response_model=LeaveBalanceSummary)
async def get_my_leave_balance(
    current_user: UserInDB = Depends(get_current_active_user),
    balance_service: LeaveBalanceService = Depends(get_leave_balance_service),
):
    return await balance_service.get_balance_for_user(str(current_user.id))


@router.get("/users", response_model=List[LeaveBalanceSummaryWithUser])
async def get_users_leave_balances(
    current_user: UserInDB = Depends(get_current_active_user),
    balance_service: LeaveBalanceService = Depends(get_leave_balance_service),
    user_service: UserService = Depends(get_user_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    users = await user_service.get_all_users(exclude_admins=True)
    user_ids = [str(u.id) for u in users]
    return await balance_service.get_balances_for_users(user_ids)


@router.post("/users/{user_id}/reset", status_code=204)
async def reset_user_leave_entitlement(
    user_id: str,
    reset_data: Optional[LeaveResetRequest] = None,
    current_user: UserInDB = Depends(get_current_active_user),
    balance_service: LeaveBalanceService = Depends(get_leave_balance_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

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

    return None

