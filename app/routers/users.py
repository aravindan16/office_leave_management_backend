from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.models.user import User, UserCreate, UserUpdate, UserInDB
from app.services.user_service import get_user_service, UserService
from app.routers.auth import get_current_active_user

router = APIRouter()

@router.post("/", response_model=User)
async def create_user(
    user: UserCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
):
    if not (current_user.is_admin or current_user.is_manager):
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
    if not (current_user.is_admin or current_user.is_manager):
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
async def update_user(user_id: str, user_update: UserUpdate, current_user: UserInDB = Depends(get_current_active_user), user_service: UserService = Depends(get_user_service)):
    if current_user.id != user_id and not (current_user.is_manager or current_user.is_admin):
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
    return updated_user

@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user: UserInDB = Depends(get_current_active_user), user_service: UserService = Depends(get_user_service)):
    if not (current_user.is_admin or current_user.is_manager):
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
