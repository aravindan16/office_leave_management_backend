from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.models.user import User, UserCreate, UserUpdate, UserInDB, ChangePasswordRequest
from app.services.user_service import get_user_service, UserService
from app.routers.auth import get_current_active_user
from app.services.activity_log_service import get_activity_log_service, ActivityLogService
from app.models.activity_log import ActivityLogCreate

router = APIRouter()

@router.post("/", response_model=User)
async def create_user(
    user: UserCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    db_user = await user_service.get_user_by_email(email=user.email)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    try:
        created_user = await user_service.create_user(user)
        actor_name = current_user.full_name or current_user.username
        target_name = created_user.full_name or created_user.username
        await log_service.create_log(
            ActivityLogCreate(
                action="user_created",
                title="User created",
                description=f"{actor_name} created {target_name}",
                actor_id=str(current_user.id),
                actor_name=actor_name,
                target_user_id=str(created_user.id),
                target_user_name=target_name,
                entity_type="user",
                entity_id=str(created_user.id),
                metadata={
                    "email": getattr(created_user, "email", None),
                    "employee_id": getattr(created_user, "employee_id", None),
                },
            )
        )
        return created_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[User])
async def get_users(current_user: UserInDB = Depends(get_current_active_user), user_service: UserService = Depends(get_user_service)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return await user_service.get_all_users(exclude_admins=True)

@router.get("/managers", response_model=List[User])
async def get_managers(user_service: UserService = Depends(get_user_service)):
    return await user_service.get_managers()

@router.get("/me", response_model=User)
async def get_current_user_info(current_user: UserInDB = Depends(get_current_active_user)):
    return User(**current_user.dict())


@router.get("/{user_id}", response_model=User)
async def get_user_by_id(
    user_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
):
    if not current_user.is_admin and str(current_user.id) != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/me/change-password")
async def change_my_password(
    payload: ChangePasswordRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
):
    ok = await user_service.change_password(str(current_user.id), payload.current_password, payload.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    return {"success": True}

@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: UserInDB = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    if not current_user.is_admin:
        if user_update.is_admin is not None or user_update.is_manager is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to change roles"
            )
    updated_user = await user_service.update_user(user_id, user_update)
    if not updated_user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    actor_name = current_user.full_name or current_user.username
    target_name = updated_user.full_name or updated_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="user_updated",
            title="Profile updated" if str(current_user.id) == str(user_id) else "User updated",
            description=f"{actor_name} updated {target_name} profile",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            target_user_id=str(updated_user.id),
            target_user_name=target_name,
            entity_type="user",
            entity_id=str(updated_user.id),
            metadata={"updated_fields": list(user_update.dict(exclude_unset=True).keys())},
        )
    )
    return updated_user

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    if str(current_user.id) == str(user_id):
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    target_user = await user_service.get_user_by_id(user_id)
    target_name = None
    if target_user:
        target_name = target_user.full_name or target_user.username
    deleted = await user_service.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="user_deleted",
            title="User deleted",
            description=f"{actor_name} deleted {target_name or user_id}",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            target_user_id=str(user_id),
            target_user_name=target_name,
            entity_type="user",
            entity_id=str(user_id),
        )
    )
    return {"success": True}

@router.get("/next-employee-id")
async def get_next_employee_id(
    current_user: UserInDB = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    next_id = await user_service.get_next_employee_id()
    return {"next_id": next_id}
