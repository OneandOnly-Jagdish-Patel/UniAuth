from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient  # Async version
from typing import Optional, Dict
from datetime import datetime


# Async client (preferred for FastAPI)
async_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = async_client["auth_db"]
users_collection = db["users"]
sessions_collection = db["sessions"]
previous_devices = db["previous_devices"]

async def save_user(user_id: str, email: str, device_id: str, platform: str):
    await users_collection.insert_one({
        "user_id": user_id,
        "email": email,
        "device_id": device_id,
        "platform": platform
    })

async def get_user_by_device(device_id: str) -> Optional[Dict]:
    return await users_collection.find_one({"device_id": device_id})

async def revoke_old_sessions(user_id: str):
    await sessions_collection.delete_many({"user_id": user_id})

async def save_session(user_id: str, device_id: str, platform: str, access_token: str):
    await sessions_collection.insert_one({
        "user_id": user_id,
        "device_id": device_id,
        "platform": platform,
        "access_token": access_token,
        "created_at": datetime.utcnow()
    })