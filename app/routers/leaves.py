from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.models.leave import Leave, LeaveCreate, LeaveUpdate, LeaveStatus
from app.models.user import UserInDB
from app.services.leave_service import get_leave_service, LeaveService
from app.services.user_service import get_user_service, UserService
from app.routers.auth import get_current_active_user
from app.services.activity_log_service import get_activity_log_service, ActivityLogService
from app.models.activity_log import ActivityLogCreate
from bson import ObjectId

router = APIRouter()

@router.post("/", response_model=Leave)
async def create_leave_request(
    leave: LeaveCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    leave_service: LeaveService = Depends(get_leave_service),
    user_service: UserService = Depends(get_user_service),
    log_service: ActivityLogService = Depends(get_activity_log_service)
):
    if leave.manager_id and not ObjectId.is_valid(str(leave.manager_id)):
        raise HTTPException(status_code=400, detail="Invalid manager ID")
    
    if leave.manager_id:
        manager = await user_service.get_user_by_id(str(leave.manager_id))
        if not manager or not manager.is_manager:
            raise HTTPException(status_code=400, detail="Invalid manager specified")
    else:
        managers = await user_service.get_managers()
        if not managers:
            raise HTTPException(status_code=400, detail="No managers available")
        leave.manager_id = managers[0].id
    
    created_leave = await leave_service.create_leave_request(leave, str(current_user.id))
    await log_service.create_log(
        ActivityLogCreate(
            action="leave_created",
            title="Leave request created",
            description=f"{current_user.full_name or current_user.username} created a leave request ({created_leave.leave_type})",
            actor_id=str(current_user.id),
            actor_name=current_user.full_name or current_user.username,
            target_user_id=str(current_user.id),
            target_user_name=current_user.full_name or current_user.username,
            entity_type="leave",
            entity_id=str(created_leave.id),
            metadata={
                "leave_type": str(created_leave.leave_type),
                "start_date": str(created_leave.start_date),
                "end_date": str(created_leave.end_date),
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
    if current_user.is_manager:
        return await leave_service.get_all_leaves()
    else:
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
    if not (current_user.is_manager or current_user.is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return await leave_service.get_pending_leaves()

@router.put("/{leave_id}/approve", response_model=Leave)
async def approve_leave(
    leave_id: str,
    manager_comment: str = None,
    current_user: UserInDB = Depends(get_current_active_user),
    leave_service: LeaveService = Depends(get_leave_service),
    user_service: UserService = Depends(get_user_service),
    log_service: ActivityLogService = Depends(get_activity_log_service)
):
    if not (current_user.is_manager or current_user.is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    leave = await leave_service.get_leave_by_id(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    updated_leave = await leave_service.update_leave_status(leave_id, LeaveStatus.APPROVED, manager_comment)
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
                    "leave_type": str(updated_leave.leave_type),
                    "start_date": str(updated_leave.start_date),
                    "end_date": str(updated_leave.end_date),
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
    if not (current_user.is_manager or current_user.is_admin):
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
                    "leave_type": str(updated_leave.leave_type),
                    "start_date": str(updated_leave.start_date),
                    "end_date": str(updated_leave.end_date),
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
    
    if str(leave.employee_id) != str(current_user.id) and not (current_user.is_manager or current_user.is_admin):
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
                    "leave_type": str(updated_leave.leave_type),
                    "start_date": str(updated_leave.start_date),
                    "end_date": str(updated_leave.end_date),
                    "status": str(updated_leave.status),
                },
            )
        )
    return updated_leave
