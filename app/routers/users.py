from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.models.user import User, UserCreate, UserUpdate, UserInDB
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
        return await user_service.create_user(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[User])
async def get_users(current_user: UserInDB = Depends(get_current_active_user), user_service: UserService = Depends(get_user_service)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return await user_service.get_all_users()

@router.get("/managers", response_model=List[User])
async def get_managers(user_service: UserService = Depends(get_user_service)):
    return await user_service.get_managers()

@router.get("/me", response_model=User)
async def get_current_user_info(current_user: UserInDB = Depends(get_current_active_user)):
    return User(**current_user.dict())

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
async def delete_user(user_id: str, current_user: UserInDB = Depends(get_current_active_user), user_service: UserService = Depends(get_user_service)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    if str(current_user.id) == str(user_id):
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    deleted = await user_service.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True}
