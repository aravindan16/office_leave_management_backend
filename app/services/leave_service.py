from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.leave import Leave, LeaveCreate, LeaveUpdate, LeaveStatus
from app.core.database import get_database
from bson import ObjectId
from datetime import datetime, date, time

class LeaveService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.leaves

    def _normalize_leave_for_model(self, leave_data: dict) -> dict:
        def to_date(value):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date) and not isinstance(value, datetime):
                return value
            if isinstance(value, str):
                # Accept both "YYYY-MM-DD" and full ISO strings.
                try:
                    return date.fromisoformat(value[:10])
                except ValueError:
                    try:
                        return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                    except ValueError:
                        return value
            return value

        if "start_date" in leave_data:
            leave_data["start_date"] = to_date(leave_data.get("start_date"))
        if "end_date" in leave_data:
            leave_data["end_date"] = to_date(leave_data.get("end_date"))

        def to_datetime(value):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value.replace('Z', '+00:00'))
                except ValueError:
                    return value
            return value

        if "created_at" in leave_data:
            leave_data["created_at"] = to_datetime(leave_data.get("created_at"))
        if "updated_at" in leave_data:
            leave_data["updated_at"] = to_datetime(leave_data.get("updated_at"))
        return leave_data

    async def create_leave_request(self, leave_data: LeaveCreate, employee_id: str) -> Leave:
        leave_dict = leave_data.dict()
        if isinstance(leave_dict.get("start_date"), date) and not isinstance(leave_dict.get("start_date"), datetime):
            leave_dict["start_date"] = datetime.combine(leave_dict["start_date"], time.min)
        if isinstance(leave_dict.get("end_date"), date) and not isinstance(leave_dict.get("end_date"), datetime):
            leave_dict["end_date"] = datetime.combine(leave_dict["end_date"], time.min)
        if leave_dict.get("manager_id") is not None and ObjectId.is_valid(str(leave_dict["manager_id"])):
            leave_dict["manager_id"] = ObjectId(str(leave_dict["manager_id"]))
        leave_dict["employee_id"] = ObjectId(employee_id)
        leave_dict["status"] = LeaveStatus.PENDING.value
        leave_dict["created_at"] = datetime.utcnow()
        leave_dict["updated_at"] = datetime.utcnow()
        
        result = await self.collection.insert_one(leave_dict)
        leave_dict["id"] = str(result.inserted_id)
        leave_dict["employee_id"] = str(leave_dict["employee_id"])
        if leave_dict.get("manager_id") is not None:
            leave_dict["manager_id"] = str(leave_dict["manager_id"])
        leave_dict = self._normalize_leave_for_model(leave_dict)
        return Leave(**leave_dict)

    async def get_leave_by_id(self, leave_id: str) -> Optional[Leave]:
        if not ObjectId.is_valid(leave_id):
            return None
        leave_data = await self.collection.find_one({"_id": ObjectId(leave_id)})
        if leave_data:
            leave_data["id"] = str(leave_data.pop("_id"))
            leave_data["employee_id"] = str(leave_data["employee_id"])
            if leave_data.get("manager_id") is not None:
                leave_data["manager_id"] = str(leave_data["manager_id"])
            leave_data = self._normalize_leave_for_model(leave_data)
            return Leave(**leave_data)
        return None

    async def get_leaves_by_employee(self, employee_id: str) -> List[Leave]:
        leaves = []
        if not ObjectId.is_valid(str(employee_id)):
            return leaves
        async for leave_data in self.collection.find({"employee_id": ObjectId(str(employee_id))}):
            leave_data["id"] = str(leave_data.pop("_id"))
            leave_data["employee_id"] = str(leave_data["employee_id"])
            if leave_data.get("manager_id") is not None:
                leave_data["manager_id"] = str(leave_data["manager_id"])
            leave_data = self._normalize_leave_for_model(leave_data)
            try:
                leaves.append(Leave(**leave_data))
            except Exception:
                continue
        return leaves

    async def get_leaves_for_manager(self, manager_id: str) -> List[Leave]:
        leaves = []
        manager_query = {"manager_id": ObjectId(manager_id), "status": LeaveStatus.PENDING.value}
        if ObjectId.is_valid(manager_id):
            manager_query = {
                "manager_id": {"$in": [ObjectId(manager_id), manager_id]},
                "status": LeaveStatus.PENDING.value,
            }
        async for leave_data in self.collection.find(manager_query):
            leave_data["id"] = str(leave_data.pop("_id"))
            leave_data["employee_id"] = str(leave_data["employee_id"])
            if leave_data.get("manager_id") is not None:
                leave_data["manager_id"] = str(leave_data["manager_id"])
            leave_data = self._normalize_leave_for_model(leave_data)
            try:
                leaves.append(Leave(**leave_data))
            except Exception:
                continue
        return leaves

    async def get_pending_leaves(self) -> List[Leave]:
        leaves = []
        async for leave_data in self.collection.find({"status": LeaveStatus.PENDING.value}):
            leave_data["id"] = str(leave_data.pop("_id"))
            leave_data["employee_id"] = str(leave_data["employee_id"])
            if leave_data.get("manager_id") is not None:
                leave_data["manager_id"] = str(leave_data["manager_id"])
            leave_data = self._normalize_leave_for_model(leave_data)
            try:
                leaves.append(Leave(**leave_data))
            except Exception:
                continue
        return leaves

    async def update_leave_status(
        self,
        leave_id: str,
        status: LeaveStatus,
        manager_comment: Optional[str] = None,
        leave_type: Optional[str] = None,
    ) -> Optional[Leave]:
        if not ObjectId.is_valid(leave_id):
            return None
        
        update_data = {
            "status": status.value if isinstance(status, LeaveStatus) else status,
            "updated_at": datetime.utcnow()
        }
        if manager_comment:
            update_data["manager_comment"] = manager_comment
        if leave_type is not None:
            update_data["leave_type"] = leave_type
        
        result = await self.collection.update_one(
            {"_id": ObjectId(leave_id)},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            return None
        return await self.get_leave_by_id(leave_id)

    async def get_all_leaves(self) -> List[Leave]:
        leaves = []
        async for leave_data in self.collection.find():
            leave_data["id"] = str(leave_data.pop("_id"))
            leave_data["employee_id"] = str(leave_data["employee_id"])
            if leave_data.get("manager_id") is not None:
                leave_data["manager_id"] = str(leave_data["manager_id"])
            leave_data = self._normalize_leave_for_model(leave_data)
            try:
                leaves.append(Leave(**leave_data))
            except Exception:
                continue
        return leaves

    async def cancel_leave(self, leave_id: str) -> Optional[Leave]:
        return await self.update_leave_status(leave_id, LeaveStatus.CANCELLED)

def get_leave_service() -> LeaveService:
    return LeaveService(get_database())
