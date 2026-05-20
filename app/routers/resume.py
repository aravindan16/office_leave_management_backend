import base64
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import Response
from typing import List

from app.models.resume import ResumeListItem, ResumeUpdate, ResumeInDB
from app.models.user import UserInDB
from app.services.resume_service import ResumeService, get_resume_service
from app.services.user_service import UserService, get_user_service
from app.routers.auth import get_current_active_user

router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE = 10 * 1024 * 1024   # 10 MB


@router.post("/upload/{user_id}", response_model=ResumeListItem, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    user_id: str,
    role_applied: str = Form(...),
    notes: str = Form(""),
    file: UploadFile = File(...),
    current_user: UserInDB = Depends(get_current_active_user),
    resume_service: ResumeService = Depends(get_resume_service),
    user_service: UserService = Depends(get_user_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    employee = await user_service.get_user_by_id(user_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF or Word files are allowed")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max size is 10 MB")

    resume = await resume_service.create_resume(
        employee_id=employee.employee_id,
        user_id=user_id,
        role_applied=role_applied,
        notes=notes,
        file_name=file.filename,
        file_bytes=file_bytes,
        content_type=file.content_type,
        uploaded_by_id=str(current_user.id),
        uploaded_by_name=current_user.full_name or current_user.username,
    )
    return ResumeListItem(**resume.dict())


@router.get("/employee/{user_id}", response_model=List[ResumeListItem])
async def list_resumes_for_employee(
    user_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    resume_service: ResumeService = Depends(get_resume_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    return await resume_service.get_resumes_by_employee(user_id)



@router.get("/download/{resume_id}")
async def download_resume(
    resume_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    resume_service: ResumeService = Depends(get_resume_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    resume = await resume_service.get_resume_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    file_bytes = base64.b64decode(resume.file_data)

    return Response(
        content=file_bytes,
        media_type=resume.content_type,
        headers={"Content-Disposition": f'attachment; filename="{resume.file_name}"'},
    )

@router.get("/get/{resume_id}")
async def get_resume(
    resume_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    resume_service: ResumeService = Depends(get_resume_service),
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins only"
        )

    resume = await resume_service.get_resume_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found"
        )

    return {
        "id": resume.id,
        "file_data": resume.file_data,
        "content_type": resume.content_type,
        "file_name": resume.file_name,
    }


# ── UPDATE metadata (role / notes only) ───────────────────────────────────────

@router.put("/update/{resume_id}", response_model=ResumeListItem)
async def update_resume(
    resume_id: str,
    update_data: ResumeUpdate,
    current_user: UserInDB = Depends(get_current_active_user),
    resume_service: ResumeService = Depends(get_resume_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    updated = await resume_service.update_resume(resume_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Resume not found")
    return updated


# ── DELETE ────────────────────────────────────────────────────────────────────

@router.delete("/delete/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    resume_service: ResumeService = Depends(get_resume_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")

    deleted = await resume_service.delete_resume(resume_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"success": True}