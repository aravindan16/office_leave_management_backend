from typing import Optional, List
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
        user_data = await self.collection.find_one({"email": email})
        if user_data:
            user_data["id"] = str(user_data.pop("_id"))
            return UserInDB(**user_data)
        return None

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        if not ObjectId.is_valid(user_id):
            return None
        user_data = await self.collection.find_one({"_id": ObjectId(user_id)})
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

    async def get_all_users(self) -> List[User]:
        users = []
        async for user_data in self.collection.find({"is_active": True}):
            user_data["id"] = str(user_data.pop("_id"))
            users.append(User(**user_data))
        return users

    async def get_managers(self) -> List[User]:
        managers = []
        async for user_data in self.collection.find({"is_manager": True, "is_active": True}):
            user_data["id"] = str(user_data.pop("_id"))
            managers.append(User(**user_data))
        return managers

    async def delete_user(self, user_id: str) -> bool:
        if not ObjectId.is_valid(user_id):
            return False
        result = await self.collection.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0

def get_user_service() -> UserService:
    return UserService(get_database())
