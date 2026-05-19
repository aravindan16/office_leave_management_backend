from typing import List, Optional
from datetime import datetime, time

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.models.physical_calendar_entry import (
    PhysicalCalendarEntry,
    PhysicalCalendarEntryCreate,
    PhysicalCalendarEntryUpdate,
)


class PhysicalCalendarService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.physical_calendar_entries

    def _normalize_for_model(self, doc: dict) -> dict:
        if not doc:
            return doc
        if doc.get("_id") is not None:
            doc["id"] = str(doc.pop("_id"))
        if doc.get("date") is not None and isinstance(doc["date"], datetime):
            doc["date"] = doc["date"].date().isoformat()
        return doc

    def _parse_date(self, value: str) -> datetime:
        if value is None:
            raise ValueError("date is required")
        s = str(value).strip()
        if not s:
            raise ValueError("date is required")

        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return datetime.combine(dt.date(), time.min)
        except Exception:
            pass

        try:
            dt2 = datetime.strptime(s[:10], "%Y-%m-%d")
            return datetime.combine(dt2.date(), time.min)
        except Exception as e:
            raise ValueError("Invalid date format. Use YYYY-MM-DD") from e

    async def list_entries(self, fy_start_year: int) -> List[PhysicalCalendarEntry]:
        out: List[PhysicalCalendarEntry] = []
        cursor = self.collection.find({"fy_start_year": int(fy_start_year)}).sort("date", 1)
        async for doc in cursor:
            out.append(PhysicalCalendarEntry(**self._normalize_for_model(doc)))
        return out

    async def get_by_id(self, entry_id: str) -> Optional[PhysicalCalendarEntry]:
        if not ObjectId.is_valid(entry_id):
            return None
        doc = await self.collection.find_one({"_id": ObjectId(entry_id)})
        if not doc:
            return None
        return PhysicalCalendarEntry(**self._normalize_for_model(doc))

    async def create_entry(self, payload: PhysicalCalendarEntryCreate) -> PhysicalCalendarEntry:
        fy = int(payload.fy_start_year)
        name = str(payload.name or "").strip()
        if not name:
            raise ValueError("name is required")

        dt = self._parse_date(payload.date)
        existing = await self.collection.find_one({"fy_start_year": fy, "date": dt})
        if existing is not None:
            raise ValueError("Entry already exists for this date")

        now = datetime.utcnow()
        doc = {
            "fy_start_year": fy,
            "date": dt,
            "name": name,
            "created_at": now,
            "updated_at": now,
        }
        result = await self.collection.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        doc = self._normalize_for_model(doc)
        return PhysicalCalendarEntry(**doc)

    async def update_entry(self, entry_id: str, payload: PhysicalCalendarEntryUpdate) -> Optional[PhysicalCalendarEntry]:
        if not ObjectId.is_valid(entry_id):
            return None

        update_dict = payload.dict(exclude_unset=True)
        if not update_dict:
            return await self.get_by_id(entry_id)

        if "fy_start_year" in update_dict:
            update_dict["fy_start_year"] = int(update_dict["fy_start_year"])

        if "name" in update_dict:
            update_dict["name"] = str(update_dict.get("name") or "").strip()
            if not update_dict["name"]:
                raise ValueError("name is required")

        if "date" in update_dict:
            update_dict["date"] = self._parse_date(update_dict.get("date"))

        if "fy_start_year" in update_dict or "date" in update_dict:
            existing_doc = await self.collection.find_one({"_id": ObjectId(entry_id)})
            if not existing_doc:
                return None

            next_fy = int(update_dict.get("fy_start_year", existing_doc.get("fy_start_year")))
            next_date = update_dict.get("date", existing_doc.get("date"))
            dup = await self.collection.find_one({"fy_start_year": next_fy, "date": next_date})
            if dup is not None and str(dup.get("_id")) != str(ObjectId(entry_id)):
                raise ValueError("Entry already exists for this date")

        update_dict["updated_at"] = datetime.utcnow()

        result = await self.collection.update_one({"_id": ObjectId(entry_id)}, {"$set": update_dict})
        if result.matched_count == 0:
            return None
        return await self.get_by_id(entry_id)

    async def delete_entry(self, entry_id: str) -> bool:
        if not ObjectId.is_valid(entry_id):
            return False
        result = await self.collection.delete_one({"_id": ObjectId(entry_id)})
        return result.deleted_count > 0


def get_physical_calendar_service() -> PhysicalCalendarService:
    return PhysicalCalendarService(get_database())
