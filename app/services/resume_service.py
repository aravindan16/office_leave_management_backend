import base64
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime

from app.models.resume import ResumeInDB, ResumeListItem, ResumeUpdate
from app.core.database import get_database


class ResumeService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.resumes  

    async def create_resume(
        self,
        employee_id: str,
        user_id: str,
        role_applied: str,
        notes: str,
        file_name: str,
        file_bytes: bytes,
        content_type: str,
        uploaded_by_id: str,
        uploaded_by_name: str,
    ) -> ResumeInDB:
        encoded = base64.b64encode(file_bytes).decode("utf-8")

        doc = {
            "employee_id": employee_id,
            "user_id": user_id,
            "role_applied": role_applied,
            "notes": notes,
            "file_name": file_name,
            "file_data": encoded,
            "file_size": len(file_bytes),
            "content_type": content_type,
            "uploaded_by_id": uploaded_by_id,
            "uploaded_by_name": uploaded_by_name,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        result = await self.collection.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        return ResumeInDB(**doc)


    async def get_resumes_by_employee(self, user_id: str) -> List[ResumeListItem]:
        resumes = []
        async for doc in self.collection.find(
            {"user_id": user_id},
            {"file_data": 0}    
        ):
            doc["id"] = str(doc.pop("_id"))
            resumes.append(ResumeListItem(**doc))
        return resumes


    async def get_resume_by_id(self, resume_id: str) -> Optional[ResumeInDB]:
        if not ObjectId.is_valid(resume_id):
            return None
        doc = await self.collection.find_one({"_id": ObjectId(resume_id)})
        if not doc:
            return None
        doc["id"] = str(doc.pop("_id"))
        return ResumeInDB(**doc)

    # ── UPDATE (metadata only — role / notes) ────────────────────────────────

    async def update_resume(
        self, resume_id: str, update_data: ResumeUpdate
    ) -> Optional[ResumeListItem]:
        if not ObjectId.is_valid(resume_id):
            return None

        fields = update_data.dict(exclude_unset=True)
        fields["updated_at"] = datetime.utcnow()

        result = await self.collection.update_one(
            {"_id": ObjectId(resume_id)},
            {"$set": fields}
        )
        if result.matched_count == 0:
            return None

        doc = await self.collection.find_one(
            {"_id": ObjectId(resume_id)},
            {"file_data": 0}
        )
        doc["id"] = str(doc.pop("_id"))
        return ResumeListItem(**doc)

    # ── DELETE ────────────────────────────────────────────────────────────────

    async def delete_resume(self, resume_id: str) -> bool:
        if not ObjectId.is_valid(resume_id):
            return False
        result = await self.collection.delete_one({"_id": ObjectId(resume_id)})
        return result.deleted_count > 0


async def get_resume_service() -> ResumeService:
    db = get_database()
    return ResumeService(db)