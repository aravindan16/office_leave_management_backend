import motor.motor_asyncio
import asyncio
import os
import requests
from dotenv import load_dotenv

load_dotenv(".env")

async def run():
    mongodb_url = os.getenv('MONGODB_URL')
    client = motor.motor_asyncio.AsyncIOMotorClient(mongodb_url)
    db = client.get_database()
    
    email = 'antigravity-test@mail7.io'
    await db.users.delete_many({'email': email}) # Clean up if exists
    await db.users.insert_one({
        'email': email,
        'is_active': True,
        'employee_id': 'TEST999',
        'full_name': 'Test User'
    })
    print(f"Created test user: {email}")
    
    # Trigger the forgot-password API
    print("Triggering forgot-password API...")
    try:
        # Use localhost since we are inside or can reach the container port
        # Actually we are on the host, so use localhost:9051
        response = requests.post(
            "http://localhost:9051/api/auth/forgot-password",
            json={"email": email}
        )
        print(f"API Response: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Failed to trigger API: {e}")

if __name__ == "__main__":
    asyncio.run(run())
