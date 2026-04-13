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

    async def _enrich_target_user_names(self, logs: List[dict]) -> List[dict]:
        target_ids: List[str] = []
        object_ids: List[ObjectId] = []

        for log in logs:
            if log.get("target_user_name"):
                continue
            tid = log.get("target_user_id")
            if not tid:
                continue
            tid_str = str(tid)
            if tid_str in target_ids:
                continue
            if ObjectId.is_valid(tid_str):
                target_ids.append(tid_str)
                object_ids.append(ObjectId(tid_str))

        if not object_ids:
            return logs

        user_map = {}
        cursor = self.db.users.find({"_id": {"$in": object_ids}}, {"full_name": 1, "username": 1})
        async for user in cursor:
            uid = str(user.get("_id"))
            name = (user.get("full_name") or "").strip() or (user.get("username") or "")
            if name:
                user_map[uid] = name

        for log in logs:
            if log.get("target_user_name"):
                continue
            tid = log.get("target_user_id")
            if not tid:
                continue
            tid_str = str(tid)
            if tid_str in user_map:
                log["target_user_name"] = user_map[tid_str]

        return logs

    async def create_log(self, log: ActivityLogCreate) -> ActivityLog:
        log_dict = log.dict(exclude_unset=True)
        log_dict["created_at"] = datetime.utcnow()

        result = await self.collection.insert_one(log_dict)
        log_dict["id"] = str(result.inserted_id)
        return ActivityLog(**log_dict)

    async def get_logs(self, skip: int = 0, limit: int = 50) -> List[ActivityLog]:
        raw_logs: List[dict] = []
        cursor = self.collection.find().sort("created_at", -1).skip(skip).limit(limit)
        async for log_data in cursor:
            log_data["id"] = str(log_data.pop("_id"))
            raw_logs.append(log_data)
        raw_logs = await self._enrich_target_user_names(raw_logs)
        return [ActivityLog(**l) for l in raw_logs]

    async def get_logs_for_user(self, user_id: str, skip: int = 0, limit: int = 50) -> List[ActivityLog]:
        raw_logs: List[dict] = []
        cursor = (
            self.collection.find({"target_user_id": str(user_id)})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        async for log_data in cursor:
            log_data["id"] = str(log_data.pop("_id"))
            raw_logs.append(log_data)
        raw_logs = await self._enrich_target_user_names(raw_logs)
        return [ActivityLog(**l) for l in raw_logs]


def get_activity_log_service() -> ActivityLogService:
    return ActivityLogService(get_database())
