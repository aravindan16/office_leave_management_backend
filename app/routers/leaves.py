from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.models.leave import Leave, LeaveCreate, LeaveUpdate, LeaveStatus
from app.models.user import UserInDB
from app.services.leave_service import get_leave_service, LeaveService
from app.services.user_service import get_user_service, UserService
from app.routers.auth import get_current_active_user
from app.services.activity_log_service import get_activity_log_service, ActivityLogService
from app.models.activity_log import ActivityLogCreate
from app.services.leave_balance_service import LeaveBalanceService, get_leave_balance_service
from bson import ObjectId

router = APIRouter()

def get_request_label(leave: Leave) -> str:
    if str(leave.request_type).lower() == "wfh":
        return "WFH"
    if str(leave.leave_type).lower() == "unpaid":
        return "Loss of Pay"
    return str(leave.leave_type)


def iter_month_ranges(start_date: date, end_date: date):
    cursor = date(start_date.year, start_date.month, 1)
    last_month = date(end_date.year, end_date.month, 1)

    while cursor <= last_month:
        if cursor.month == 12:
            next_month = date(cursor.year + 1, 1, 1)
        else:
            next_month = date(cursor.year, cursor.month + 1, 1)

        yield cursor, (next_month - timedelta(days=1))
        cursor = next_month


def get_requested_days(leave) -> float:
    duration = getattr(leave, "duration_days", None)
    if duration is not None:
        try:
            return float(duration)
        except (TypeError, ValueError):
            pass
    return float((leave.end_date - leave.start_date).days + 1)

@router.post("/", response_model=Leave)
async def create_leave_request(
    leave: LeaveCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    leave_service: LeaveService = Depends(get_leave_service),
    user_service: UserService = Depends(get_user_service),
    balance_service: LeaveBalanceService = Depends(get_leave_balance_service),
    log_service: ActivityLogService = Depends(get_activity_log_service)
):
    if leave.manager_id and not ObjectId.is_valid(str(leave.manager_id)):
        raise HTTPException(status_code=400, detail="Invalid manager ID")
    
    if leave.manager_id:
        manager = await user_service.get_user_by_id(str(leave.manager_id))
        if not manager or not manager.is_admin:
            raise HTTPException(status_code=400, detail="Invalid admin specified")
    else:
        managers = await user_service.get_managers()
        if not managers:
            raise HTTPException(status_code=400, detail="No managers available")
        leave.manager_id = managers[0].id

    # Prevent duplicate/overlapping requests for the same dates.
    start_dt = datetime.combine(leave.start_date, time.min)
    end_dt = datetime.combine(leave.end_date, time.max)
    overlap_query = {
        "employee_id": ObjectId(str(current_user.id)),
        "status": {"$in": [LeaveStatus.PENDING.value, LeaveStatus.APPROVED.value]},
        "start_date": {"$lte": end_dt},
        "end_date": {"$gte": start_dt},
    }
    existing_overlap = await leave_service.collection.find_one(overlap_query)
    if existing_overlap:
        raise HTTPException(
            status_code=400,
            detail="You already have a pending/approved request for the selected date(s).",
        )

    if str(leave.request_type).lower() == "wfh":
        for month_start, month_end in iter_month_ranges(leave.start_date, leave.end_date):
            existing_month_wfh = await leave_service.collection.find_one({
                "employee_id": ObjectId(str(current_user.id)),
                "request_type": "wfh",
                "status": {"$in": [LeaveStatus.PENDING.value, LeaveStatus.APPROVED.value]},
                "start_date": {"$lte": datetime.combine(month_end, time.max)},
                "end_date": {"$gte": datetime.combine(month_start, time.min)},
            })
            if existing_month_wfh:
                raise HTTPException(
                    status_code=400,
                    detail=f"Only one WFH request is allowed per month. You already have a WFH request for {month_start.strftime('%B %Y')}.",
                )
    
    # Guardrail: don't allow creating a Sick leave request that exceeds balance.
    if str(leave.request_type).lower() == "leave" and str(leave.leave_type).lower() == "sick":
        try:
            balance = await balance_service.get_balance_for_user(str(current_user.id))
        except Exception:
            balance = None
        if balance is not None:
            days = get_requested_days(leave)
            if days > (balance.sick.balance or 0):
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient Sick leave balance.",
                )

    created_leave = await leave_service.create_leave_request(leave, str(current_user.id))
    await log_service.create_log(
        ActivityLogCreate(
            action="leave_created",
            title="Leave request created",
            description=f"{current_user.full_name or current_user.username} created a leave request ({get_request_label(created_leave)})",
            actor_id=str(current_user.id),
            actor_name=current_user.full_name or current_user.username,
            target_user_id=str(current_user.id),
            target_user_name=current_user.full_name or current_user.username,
            entity_type="leave",
            entity_id=str(created_leave.id),
            metadata={
                "request_type": str(created_leave.request_type),
                "leave_type": str(created_leave.leave_type),
                "start_date": str(created_leave.start_date),
                "end_date": str(created_leave.end_date),
                "duration_days": getattr(created_leave, "duration_days", None),
                "reason": str(created_leave.reason),
                "status": str(created_leave.status),
            },
        )
    )
    return created_leave

@router.get("/", response_model=List[Leave])
async def get_leaves(
    current_user: UserInDB = Depends(get_current_active_user),
    leave_service: LeaveService = Depends(get_leave_service)
):
    if current_user.is_admin:
        return await leave_service.get_all_leaves()
    return await leave_service.get_leaves_by_employee(str(current_user.id))

@router.get("/my-leaves", response_model=List[Leave])
async def get_my_leaves(
    current_user: UserInDB = Depends(get_current_active_user),
    leave_service: LeaveService = Depends(get_leave_service)
):
    return await leave_service.get_leaves_by_employee(str(current_user.id))

@router.get("/pending-approvals", response_model=List[Leave])
async def get_pending_leaves(
    current_user: UserInDB = Depends(get_current_active_user),
    leave_service: LeaveService = Depends(get_leave_service)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return await leave_service.get_pending_leaves()

@router.put("/{leave_id}/approve", response_model=Leave)
async def approve_leave(
    leave_id: str,
    manager_comment: str = None,
    as_unpaid: bool = False,
    current_user: UserInDB = Depends(get_current_active_user),
    leave_service: LeaveService = Depends(get_leave_service),
    user_service: UserService = Depends(get_user_service),
    log_service: ActivityLogService = Depends(get_activity_log_service)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    leave = await leave_service.get_leave_by_id(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    leave_type_override = None
    if as_unpaid and str(leave.request_type).lower() == "leave":
        leave_type_override = "unpaid"

    updated_leave = await leave_service.update_leave_status(
        leave_id,
        LeaveStatus.APPROVED,
        manager_comment,
        leave_type=leave_type_override,
    )
    if updated_leave:
        employee = await user_service.get_user_by_id(str(updated_leave.employee_id))
        employee_name = None
        if employee:
            employee_name = employee.full_name or employee.username
        await log_service.create_log(
            ActivityLogCreate(
                action="leave_approved",
                title="Leave approved",
                description=f"{current_user.full_name or current_user.username} approved a leave request",
                actor_id=str(current_user.id),
                actor_name=current_user.full_name or current_user.username,
                target_user_id=str(updated_leave.employee_id),
                target_user_name=employee_name,
                entity_type="leave",
                entity_id=str(updated_leave.id),
                metadata={
                    "manager_comment": manager_comment,
                    "request_type": str(updated_leave.request_type),
                    "leave_type": str(updated_leave.leave_type),
                    "start_date": str(updated_leave.start_date),
                    "end_date": str(updated_leave.end_date),
                    "duration_days": getattr(updated_leave, "duration_days", None),
                    "reason": str(updated_leave.reason),
                    "status": str(updated_leave.status),
                },
            )
        )
    return updated_leave

@router.put("/{leave_id}/reject", response_model=Leave)
async def reject_leave(
    leave_id: str,
    manager_comment: str = None,
    current_user: UserInDB = Depends(get_current_active_user),
    leave_service: LeaveService = Depends(get_leave_service),
    user_service: UserService = Depends(get_user_service),
    log_service: ActivityLogService = Depends(get_activity_log_service)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    leave = await leave_service.get_leave_by_id(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    updated_leave = await leave_service.update_leave_status(leave_id, LeaveStatus.REJECTED, manager_comment)
    if updated_leave:
        employee = await user_service.get_user_by_id(str(updated_leave.employee_id))
        employee_name = None
        if employee:
            employee_name = employee.full_name or employee.username
        await log_service.create_log(
            ActivityLogCreate(
                action="leave_rejected",
                title="Leave rejected",
                description=f"{current_user.full_name or current_user.username} rejected a leave request",
                actor_id=str(current_user.id),
                actor_name=current_user.full_name or current_user.username,
                target_user_id=str(updated_leave.employee_id),
                target_user_name=employee_name,
                entity_type="leave",
                entity_id=str(updated_leave.id),
                metadata={
                    "manager_comment": manager_comment,
                    "request_type": str(updated_leave.request_type),
                    "leave_type": str(updated_leave.leave_type),
                    "start_date": str(updated_leave.start_date),
                    "end_date": str(updated_leave.end_date),
                    "duration_days": getattr(updated_leave, "duration_days", None),
                    "reason": str(updated_leave.reason),
                    "status": str(updated_leave.status),
                },
            )
        )
    return updated_leave

@router.put("/{leave_id}/cancel", response_model=Leave)
async def cancel_leave(
    leave_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    leave_service: LeaveService = Depends(get_leave_service),
    user_service: UserService = Depends(get_user_service),
    log_service: ActivityLogService = Depends(get_activity_log_service)
):
    leave = await leave_service.get_leave_by_id(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    if str(leave.employee_id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    updated_leave = await leave_service.cancel_leave(leave_id)
    if updated_leave:
        employee = await user_service.get_user_by_id(str(updated_leave.employee_id))
        employee_name = None
        if employee:
            employee_name = employee.full_name or employee.username
        await log_service.create_log(
            ActivityLogCreate(
                action="leave_cancelled",
                title="Leave cancelled",
                description=f"{current_user.full_name or current_user.username} cancelled a leave request",
                actor_id=str(current_user.id),
                actor_name=current_user.full_name or current_user.username,
                target_user_id=str(updated_leave.employee_id),
                target_user_name=employee_name,
                entity_type="leave",
                entity_id=str(updated_leave.id),
                metadata={
                    "request_type": str(updated_leave.request_type),
                    "leave_type": str(updated_leave.leave_type),
                    "start_date": str(updated_leave.start_date),
                    "end_date": str(updated_leave.end_date),
                    "duration_days": getattr(updated_leave, "duration_days", None),
                    "reason": str(updated_leave.reason),
                    "status": str(updated_leave.status),
                },
            )
        )
    return updated_leave
