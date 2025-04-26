from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
import secrets
from auth import verify_google_token, create_jwt_token, get_current_user
from database import save_user, get_user_by_device, revoke_old_sessions  # <-- Import MongoDB functions

app = FastAPI()

# Models
class GoogleSignInRequest(BaseModel):
    google_token: str
    device_id: str
    platform: str  

class UserResponse(BaseModel):
    user_id: str
    email: str
    access_token: str

# === Updated Endpoints (Async + MongoDB) ===

@app.post("/signup-with-google")
async def signup_with_google(request: GoogleSignInRequest):
    # 1. Verify Google token
    user_email = verify_google_token(request.google_token)
    if not user_email:
        raise HTTPException(status_code=400, detail="Invalid Google token")

    # 2. Check if device is already registered (MongoDB query)
    existing_user = await get_user_by_device(request.device_id)  # <-- Async call
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="This device is already linked to another account"
        )

    # 3. Save new user to MongoDB
    user_id = f"user_{secrets.token_hex(8)}"
    await save_user(  # <-- Async call
        user_id=user_id,
        email=user_email,
        device_id=request.device_id,
        platform=request.platform
    )

    # 4. Generate JWT token (auto-login)
    access_token = create_jwt_token(user_id)
    return UserResponse(
        user_id=user_id,
        email=user_email,
        access_token=access_token
    )

@app.post("/auto-login")
async def auto_login(device_id: str):
    # 1. Check if device exists in MongoDB
    user = await get_user_by_device(device_id)  # <-- Async call
    if not user:
        raise HTTPException(
            status_code=404,
            detail="No account linked to this device"
        )

    # 2. Revoke old sessions (MongoDB update)
    await revoke_old_sessions(user["user_id"])  # <-- Async call

    # 3. Generate new token
    access_token = create_jwt_token(user["user_id"])
    return UserResponse(
        user_id=user["user_id"],
        email=user["email"],
        access_token=access_token
    )

# Protected endpoint (example)
@app.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {"user_id": user["user_id"], "email": user["email"]}