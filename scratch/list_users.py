import motor.motor_asyncio
import asyncio
import os
from dotenv import load_dotenv

# Load .env
load_dotenv(".env")

async def run():
    mongodb_url = os.getenv('MONGODB_URL')
    print(f"Connecting to MongoDB: {mongodb_url[:20]}...")
    client = motor.motor_asyncio.AsyncIOMotorClient(mongodb_url)
    db = client.get_database() # or use client.get_default_database()
    
    # Try to find users
    users_cursor = db.users.find()
    users = await users_cursor.to_list(length=100)
    print("User emails in database:")
    for u in users:
        print(f"- {u.get('email')}")

if __name__ == "__main__":
    asyncio.run(run())
