from typing import Optional, List
import re
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.user import User, UserInDB, UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password
from app.core.database import get_database
from bson import ObjectId
from datetime import datetime, date, time

class UserService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.users

    async def create_user(self, user_data: UserCreate) -> User:
        existing_username = await self.collection.find_one({"username": user_data.username})
        if existing_username:
            raise ValueError("Username already registered")

        existing_employee_id = await self.collection.find_one({"employee_id": user_data.employee_id})
        if existing_employee_id:
            raise ValueError("Employee ID already registered")

        user_dict = user_data.dict()
        user_dict["hashed_password"] = get_password_hash(user_dict.pop("password"))
        user_dict["created_at"] = datetime.utcnow()
        user_dict["updated_at"] = datetime.utcnow()
        
        result = await self.collection.insert_one(user_dict)
        user_dict["id"] = str(result.inserted_id)
        return User(**user_dict)

    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        user_data = await self.collection.find_one({"email": email, "is_active": True})

        if user_data:
            user_data["id"] = str(user_data.pop("_id"))
            return UserInDB(**user_data)
        return None

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        if not ObjectId.is_valid(user_id):
            return None
        user_data = await self.collection.find_one({"_id": ObjectId(user_id), "is_active": True})

        if user_data:
            user_data["id"] = str(user_data.pop("_id"))
            return User(**user_data)
        return None

    async def authenticate_user(self, email: str, password: str) -> Optional[UserInDB]:
        user = await self.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        if not ObjectId.is_valid(user_id):
            return False
        user_in_db = await self.collection.find_one({"_id": ObjectId(user_id)})
        if not user_in_db:
            return False
        hashed_password = user_in_db.get("hashed_password")
        if not hashed_password or not verify_password(current_password, hashed_password):
            return False

        new_hash = get_password_hash(new_password)
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"hashed_password": new_hash, "updated_at": datetime.utcnow()}},
        )
        return result.matched_count > 0

    async def update_password_by_email(self, email: str, new_password: str) -> bool:
        result = await self.collection.update_one(
            {"email": email},
            {
                "$set": {
                    "hashed_password": get_password_hash(new_password),
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return result.matched_count > 0

    async def update_user(self, user_id: str, user_data: UserUpdate) -> Optional[User]:
        if not ObjectId.is_valid(user_id):
            return None
        
        update_data = user_data.dict(exclude_unset=True)

        username = update_data.get("username")
        if username:
            existing_username = await self.collection.find_one({
                "username": username,
                "_id": {"$ne": ObjectId(user_id)},
            })
            if existing_username:
                raise ValueError("Username already registered")

        dob = update_data.get("date_of_birth")
        if isinstance(dob, date) and not isinstance(dob, datetime):
            update_data["date_of_birth"] = datetime.combine(dob, time.min)

        update_data["updated_at"] = datetime.utcnow()
        
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            return None
        return await self.get_user_by_id(user_id)

    async def get_all_users(self, exclude_admins: bool = False) -> List[User]:
        users = []
        query = {"is_active": True}
        if exclude_admins:
            query["is_admin"] = {"$ne": True}

        async for user_data in self.collection.find(query):
            user_data["id"] = str(user_data.pop("_id"))
            users.append(User(**user_data))
        return users

    async def get_managers(self) -> List[User]:
        managers = []
        async for user_data in self.collection.find({"is_active": True, "$or": [{"is_manager": True}, {"is_admin": True}]}):
            user_data["id"] = str(user_data.pop("_id"))
            managers.append(User(**user_data))
        return managers

    async def delete_user(self, user_id: str) -> bool:
        if not ObjectId.is_valid(user_id):
            return False
        # Soft delete: set is_active to False
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        return result.matched_count > 0

    async def get_next_employee_id(self) -> str:
        # WG followed by 4 digits
        cursor = self.collection.find(
            {"employee_id": {"$regex": "^WG\\d+$"}},
            {"employee_id": 1}
        ).sort("employee_id", -1).limit(1)
        
        last_user = await cursor.to_list(length=1)
        if not last_user:
            return "WG0001"
            
        last_id = last_user[0]["employee_id"]
        match = re.search(r"(\d+)", last_id)
        if match:
            num_str = match.group(1)
            num = int(num_str)
            next_num = num + 1
            # Maintain the same padding if possible, or default to 4
            padding = len(num_str)
            return f"WG{next_num:0{padding}d}"
        
        return "WG0001"

def get_user_service() -> UserService:
    return UserService(get_database())
