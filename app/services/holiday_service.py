from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.holiday import Holiday, HolidayCreate, HolidayUpdate
from app.core.database import get_database
from bson import ObjectId
from datetime import datetime, time


class HolidayService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.holidays

    def _parse_date_str(self, value: str) -> datetime:
        if value is None:
            raise ValueError("date is required")
        s = str(value).strip()
        if not s:
            raise ValueError("date is required")

        try:
            d = datetime.strptime(s, "%Y-%m-%d")
            return datetime.combine(d.date(), time.min)
        except ValueError:
            pass

        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return datetime.combine(dt.date(), time.min)
        except ValueError as e:
            raise ValueError("Invalid date format. Use YYYY-MM-DD") from e

    def _normalize_holiday_for_model(self, holiday_data: dict) -> dict:
        if holiday_data.get("date") is not None and isinstance(holiday_data["date"], datetime):
            holiday_data["date"] = holiday_data["date"].date().isoformat()
        return holiday_data

    async def create_holiday(self, holiday: HolidayCreate) -> Holiday:
        holiday_dict = holiday.dict(exclude_unset=True)

        holiday_dict["date"] = self._parse_date_str(holiday_dict.get("date"))

        existing = await self.collection.find_one({"date": holiday_dict["date"]})
        if existing is not None:
            raise ValueError("Holiday already exists for this date")

        holiday_dict["created_at"] = datetime.utcnow()
        holiday_dict["updated_at"] = datetime.utcnow()

        result = await self.collection.insert_one(holiday_dict)
        holiday_dict["id"] = str(result.inserted_id)

        holiday_dict = self._normalize_holiday_for_model(holiday_dict)
        return Holiday(**holiday_dict)

    async def get_holiday_by_id(self, holiday_id: str) -> Optional[Holiday]:
        if not ObjectId.is_valid(holiday_id):
            return None
        holiday_data = await self.collection.find_one({"_id": ObjectId(holiday_id)})
        if not holiday_data:
            return None
        holiday_data["id"] = str(holiday_data.pop("_id"))
        holiday_data = self._normalize_holiday_for_model(holiday_data)
        return Holiday(**holiday_data)

    async def get_all_holidays(self) -> List[Holiday]:
        holidays: List[Holiday] = []
        cursor = self.collection.find().sort("date", 1)
        async for holiday_data in cursor:
            holiday_data["id"] = str(holiday_data.pop("_id"))
            holiday_data = self._normalize_holiday_for_model(holiday_data)
            holidays.append(Holiday(**holiday_data))
        return holidays

    async def update_holiday(self, holiday_id: str, holiday_update: HolidayUpdate) -> Optional[Holiday]:
        if not ObjectId.is_valid(holiday_id):
            return None

        update_dict = holiday_update.dict(exclude_unset=True)
        if "date" in update_dict:
            update_dict["date"] = self._parse_date_str(update_dict.get("date"))

            existing = await self.collection.find_one({"date": update_dict["date"]})
            if existing is not None and str(existing.get("_id")) != str(ObjectId(holiday_id)):
                raise ValueError("Holiday already exists for this date")

        update_dict["updated_at"] = datetime.utcnow()

        result = await self.collection.update_one(
            {"_id": ObjectId(holiday_id)},
            {"$set": update_dict},
        )
        if result.matched_count == 0:
            return None
        return await self.get_holiday_by_id(holiday_id)

    async def delete_holiday(self, holiday_id: str) -> bool:
        if not ObjectId.is_valid(holiday_id):
            return False
        result = await self.collection.delete_one({"_id": ObjectId(holiday_id)})
        return result.deleted_count > 0


def get_holiday_service() -> HolidayService:
    return HolidayService(get_database())
