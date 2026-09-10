from dataclasses import dataclass
from typing import List

from bson import ObjectId
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.core.database import get_database
from app.models.user import UserInDB
from app.routers.auth import get_current_active_user


class TestingSettings(BaseModel):
    enabled: bool = False
    test_user_ids: List[str] = Field(default_factory=list)


class TestingToggleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class TestingService:
    def __init__(self, db):
        self.db = db

    async def get_settings(self, admin_id: str | None = None) -> TestingSettings:
        document = await self.db.app_settings.find_one({"_id": "testing"})
        preference = None
        if admin_id is not None:
            preference = await self.db.app_settings.find_one({"_id": f"testing-admin:{admin_id}"})
        return TestingSettings(
            enabled=(preference or {}).get("enabled", False),
            test_user_ids=(document or {}).get("test_user_ids", []),
        )

    async def set_enabled(self, enabled: bool, admin_id: str) -> TestingSettings:
        settings = await self.get_settings(admin_id)
        if enabled and not settings.test_user_ids:
            raise HTTPException(status_code=400, detail="No test account is configured.")
        await self.db.app_settings.update_one(
            {"_id": f"testing-admin:{admin_id}"}, {"$set": {"enabled": enabled}}, upsert=True,
        )
        settings.enabled = enabled
        return settings


def get_testing_service():
    return TestingService(get_database())


@dataclass(frozen=True)
class RequestVisibility:
    hidden_user_ids: frozenset[str] = frozenset()

    def filter(self, records, field="employee_id"):
        return [record for record in records if str(getattr(record, field, "")) not in self.hidden_user_ids]

    def log_query(self):
        if not self.hidden_user_ids:
            return {}
        ids = list(self.hidden_user_ids)
        ids += [ObjectId(value) for value in self.hidden_user_ids if ObjectId.is_valid(value)]
        return {"$nor": [{"actor_id": {"$in": ids}}, {"target_user_id": {"$in": ids}}]}


async def get_request_visibility(
    include_test_users: bool = False,
    current_user: UserInDB = Depends(get_current_active_user),
    testing_service: TestingService = Depends(get_testing_service),
):
    settings = await testing_service.get_settings(str(current_user.id) if current_user.is_admin else None)
    # Explicit admin inclusion is used by the Employees tab and its detail pages.
    if current_user.is_admin and (settings.enabled or include_test_users):
        return RequestVisibility()
    return RequestVisibility(frozenset(settings.test_user_ids) - {str(current_user.id)})
