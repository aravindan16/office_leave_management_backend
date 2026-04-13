from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.models.activity_log import ActivityLog, ActivityLogCreate


class ActivityLogService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.activity_logs

    async def create_log(self, log: ActivityLogCreate) -> ActivityLog:
        log_dict = log.dict(exclude_unset=True)
        log_dict["created_at"] = datetime.utcnow()

        result = await self.collection.insert_one(log_dict)
        log_dict["id"] = str(result.inserted_id)
        return ActivityLog(**log_dict)

    async def get_logs(self, skip: int = 0, limit: int = 50) -> List[ActivityLog]:
        logs: List[ActivityLog] = []
        cursor = self.collection.find().sort("created_at", -1).skip(skip).limit(limit)
        async for log_data in cursor:
            log_data["id"] = str(log_data.pop("_id"))
            logs.append(ActivityLog(**log_data))
        return logs

    async def get_logs_for_user(self, user_id: str, skip: int = 0, limit: int = 50) -> List[ActivityLog]:
        logs: List[ActivityLog] = []
        cursor = (
            self.collection.find({"target_user_id": str(user_id)})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        async for log_data in cursor:
            log_data["id"] = str(log_data.pop("_id"))
            logs.append(ActivityLog(**log_data))
        return logs


def get_activity_log_service() -> ActivityLogService:
    return ActivityLogService(get_database())
