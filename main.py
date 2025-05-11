from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, field_validator
from typing import Optional
import secrets
from auth import verify_google_token, create_jwt_token, get_current_user
from database import save_user, get_user_by_device, revoke_old_sessions  # <-- Import MongoDB functions
import re

app = FastAPI()

# Models
class GoogleSignInRequest(BaseModel):
    google_token: str
    device_id: str
    platform: str  

    @field_validator('device_id')
    def validate_device_id(cls, v, values):
        platform = values.get('platform')
        if platform == 'ios':
            if not re.match(r'^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$', v, re.IGNORECASE):
                raise ValueError('Invalid iOS device UUID format')
        elif platform == 'android':
            if not re.match(r'^[a-zA-Z0-9]{16}$', v):  
                raise ValueError('Invalid Android device ID format')
        return v

    @field_validator('platform')
    def validate_platform(cls, v):
        if v not in ['ios', 'android', 'web']:
            raise ValueError('Platform must be one of: ios, android, web')
        return v

class UserResponse(BaseModel):
    user_id: str
    email: str
    access_token: str

@app.post("/signup-with-google")
async def signup_with_google(request: GoogleSignInRequest):
    try:
        
        device_id = request.device_id
        platform = request.platform
        
        
        user_email = verify_google_token(request.google_token)
        if not user_email:
            raise HTTPException(status_code=400, detail="Invalid Google token")

        
        existing_user = await get_user_by_device(device_id)  # <-- Async call
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="This device is already linked to another account"
            )

        
        user_id = f"user_{secrets.token_hex(8)}"
        await save_user(  # <-- Async call
            user_id=user_id,
            email=user_email,
            device_id=device_id,
            platform=platform
        )
        
        access_token = create_jwt_token(user_id)
        return UserResponse(
            user_id=user_id,
            email=user_email,
            access_token=access_token
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auto-login")
async def auto_login(device_id: str):
  
    user = await get_user_by_device(device_id)  
    if not user:
        raise HTTPException(
            status_code=404,
            detail="No account linked to this device"
        )

    # 2. Revoke old sessions (MongoDB update)
    await revoke_old_sessions(user["user_id"])  

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