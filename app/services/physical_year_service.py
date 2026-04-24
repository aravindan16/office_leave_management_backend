from typing import List, Optional
from datetime import datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.models.physical_year import PhysicalYear, PhysicalYearCreate, PhysicalYearUpdate


class PhysicalYearService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.physical_years

    def _normalize_for_model(self, doc: dict) -> dict:
        if not doc:
            return doc
        if doc.get("_id") is not None:
            doc["id"] = str(doc.pop("_id"))
        return doc

    async def list_years(self) -> List[PhysicalYear]:
        out: List[PhysicalYear] = []
        cursor = self.collection.find().sort("fy_start_year", -1)
        async for doc in cursor:
            out.append(PhysicalYear(**self._normalize_for_model(doc)))
        return out

    async def get_by_id(self, year_id: str) -> Optional[PhysicalYear]:
        if not ObjectId.is_valid(year_id):
            return None
        doc = await self.collection.find_one({"_id": ObjectId(year_id)})
        if not doc:
            return None
        return PhysicalYear(**self._normalize_for_model(doc))

    async def get_by_fy_start_year(self, fy_start_year: int) -> Optional[PhysicalYear]:
        doc = await self.collection.find_one({"fy_start_year": int(fy_start_year)})
        if not doc:
            return None
        return PhysicalYear(**self._normalize_for_model(doc))

    async def create_year(self, payload: PhysicalYearCreate) -> PhysicalYear:
        fy = int(payload.fy_start_year)
        existing = await self.collection.find_one({"fy_start_year": fy})
        if existing is not None:
            raise ValueError("Physical year already exists")

        now = datetime.utcnow()
        doc = {
            "fy_start_year": fy,
            "name": (payload.name or "").strip() or None,
            "created_at": now,
            "updated_at": now,
        }
        result = await self.collection.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        return PhysicalYear(**doc)

    async def update_year(self, year_id: str, payload: PhysicalYearUpdate) -> Optional[PhysicalYear]:
        if not ObjectId.is_valid(year_id):
            return None

        update_dict = payload.dict(exclude_unset=True)
        if not update_dict:
            return await self.get_by_id(year_id)

        if "fy_start_year" in update_dict:
            update_dict["fy_start_year"] = int(update_dict["fy_start_year"])
            existing = await self.collection.find_one({"fy_start_year": update_dict["fy_start_year"]})
            if existing is not None and str(existing.get("_id")) != str(ObjectId(year_id)):
                raise ValueError("Physical year already exists")

        if "name" in update_dict:
            update_dict["name"] = (update_dict.get("name") or "").strip() or None

        update_dict["updated_at"] = datetime.utcnow()

        result = await self.collection.update_one({"_id": ObjectId(year_id)}, {"$set": update_dict})
        if result.matched_count == 0:
            return None
        return await self.get_by_id(year_id)

    async def delete_year(self, year_id: str) -> bool:
        if not ObjectId.is_valid(year_id):
            return False
        result = await self.collection.delete_one({"_id": ObjectId(year_id)})
        return result.deleted_count > 0


def get_physical_year_service() -> PhysicalYearService:
    return PhysicalYearService(get_database())
