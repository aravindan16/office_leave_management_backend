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

    async def _enrich_log_user_details(self, logs: List[dict]) -> List[dict]:
        user_ids_to_fetch = set()
        for log in logs:
            if log.get("actor_id"):
                user_ids_to_fetch.add(ObjectId(log["actor_id"]))
            if log.get("target_user_id"):
                user_ids_to_fetch.add(ObjectId(log["target_user_id"]))

        if not user_ids_to_fetch:
            return logs

        user_map = {}
        cursor = self.db.users.find(
            {"_id": {"$in": list(user_ids_to_fetch)}},
            {"full_name": 1, "username": 1, "profile_image": 1}
        )
        async for user in cursor:
            uid = str(user.get("_id"))
            name = (user.get("full_name") or "").strip() or (user.get("username") or "")
            user_map[uid] = {
                "name": name,
                "profile_image": user.get("profile_image")
            }

        for log in logs:
            aid = log.get("actor_id")
            if aid and aid in user_map:
                if not log.get("actor_name"):
                    log["actor_name"] = user_map[aid]["name"]
                log["actor_profile_image"] = user_map[aid]["profile_image"]
            
            tid = log.get("target_user_id")
            if tid and tid in user_map:
                if not log.get("target_user_name"):
                    log["target_user_name"] = user_map[tid]["name"]
                log["target_profile_image"] = user_map[tid]["profile_image"]

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
        raw_logs = await self._enrich_log_user_details(raw_logs)
        return [ActivityLog(**l) for l in raw_logs]

    async def get_logs_for_user(self, user_id: str, skip: int = 0, limit: int = 50) -> List[ActivityLog]:
        raw_logs: List[dict] = []
        # Find logs where user is either the target OR the actor
        query = {
            "$or": [
                {"target_user_id": str(user_id)},
                {"actor_id": str(user_id)}
            ]
        }
        cursor = (
            self.collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        async for log_data in cursor:
            log_data["id"] = str(log_data.pop("_id"))
            raw_logs.append(log_data)
        raw_logs = await self._enrich_log_user_details(raw_logs)
        return [ActivityLog(**l) for l in raw_logs]


def get_activity_log_service() -> ActivityLogService:
    return ActivityLogService(get_database())
