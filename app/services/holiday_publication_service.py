from typing import List, Optional
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.models.holiday_publication import HolidayYearPublication, HolidaySnapshotItem


class HolidayPublicationService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.holiday_year_publications

    async def list_published_years(self) -> List[int]:
        years: List[int] = []
        cursor = self.collection.find({"published": True}, {"year": 1}).sort("year", -1)
        async for doc in cursor:
            y = doc.get("year")
            if isinstance(y, int):
                years.append(y)
        return years

    async def list_publication_statuses(self) -> List[HolidayYearPublication]:
        out: List[HolidayYearPublication] = []
        cursor = self.collection.find({}, {"year": 1, "published": 1, "updated_at": 1, "dirty": 1}).sort(
            "year", -1
        )
        async for doc in cursor:
            try:
                out.append(
                    HolidayYearPublication(
                        year=int(doc.get("year")),
                        published=bool(doc.get("published")),
                        updated_at=doc.get("updated_at"),
                        holidays=[],
                        dirty=bool(doc.get("dirty") or False),
                    )
                )
            except Exception:
                continue
        return out

    async def set_year_published(self, year: int, published: bool) -> HolidayYearPublication:
        return await self.set_year_published_with_snapshot(year=year, published=published, holidays=None)

    async def set_year_published_with_snapshot(
        self,
        year: int,
        published: bool,
        holidays: Optional[List[HolidaySnapshotItem]],
    ) -> HolidayYearPublication:
        y = int(year)
        now = datetime.utcnow()
        payload = {"year": y, "published": bool(published), "updated_at": now}
        if holidays is not None:
            payload["holidays"] = [h.model_dump() for h in holidays]
            payload["dirty"] = False
        if not published:
            payload["dirty"] = False
        await self.collection.update_one(
            {"year": y},
            {"$set": payload},
            upsert=True,
        )
        return HolidayYearPublication(
            year=y,
            published=bool(published),
            updated_at=now,
            holidays=(holidays or []),
            dirty=bool(payload.get("dirty") or False),
        )

    async def mark_year_dirty(self, year: int) -> None:
        y = int(year)
        await self.collection.update_one(
            {"year": y, "published": True},
            {"$set": {"dirty": True, "updated_at": datetime.utcnow()}},
        )

    async def get_published_holidays(self, year: int) -> List[HolidaySnapshotItem]:
        y = int(year)
        doc = await self.collection.find_one({"year": y, "published": True})
        if not doc:
            return []
        raw = doc.get("holidays") or []
        out: List[HolidaySnapshotItem] = []
        for item in raw:
            try:
                out.append(HolidaySnapshotItem(**item))
            except Exception:
                continue
        return out


def get_holiday_publication_service() -> HolidayPublicationService:
    return HolidayPublicationService(get_database())
