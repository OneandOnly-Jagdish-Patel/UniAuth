from fastapi import FastAPI, Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from pydantic import BaseModel, field_validator
from typing import Optional
import secrets
from auth import verify_google_token, create_jwt_token, get_current_user
from database import save_user, get_user_by_device, revoke_old_sessions  # <-- Import MongoDB functions
import re

app = FastAPI()

API_KEY_NAME = "X-API-KEY"
API_KEY = "example123"  #Will be stores as environment variable in production

api_key_header = APIKeyHeader(name=API_KEY_NAME)

async def validate_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
# Models
class GoogleSignInRequest(BaseModel):
    email: str
    google_token: str
    device_id: str
    platform: str  

    @field_validator('device_id')
    def validate_device_id(cls, v, values):
        platform = values.get('platform')
        if platform == 'ios':
            if not re.match(r'^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$', v, re.IGNORECASE):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error_code": "INVALID_IOS_UUID",
                        "message": "Invalid iOS device UUID format"
                    }
                )
        elif platform == 'android':
            if not re.match(r'^[a-zA-Z0-9]{16}$', v):  
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error_code": "INVALID_ANDROID_ID",
                        "message": "Invalid Android device ID format"
                    }
                )
        return v

    @field_validator('platform')
    def validate_platform(cls, v):
        if v not in ['ios', 'android']:
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "INVALID_PLATFORM",
                    "message": "Platform must be one of: ios, android, web"
                }
            )
        return v

class UserResponse(BaseModel):
    user_id: str
    email: str
    access_token: str

@app.post("/signup-with-google")
async def signup_with_google(request: GoogleSignInRequest, _ = Depends(validate_api_key)):
    try:
        
        device_id = request.device_id
        platform = request.platform
        
        user_email = verify_google_token(request.google_token)
        if not user_email:
            raise HTTPException(status_code=400, detail="Invalid Google token")

        
        existing_user = await get_user_by_device(device_id)  
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="This device is already linked to another account"
            )

        
        user_id = f"user_{secrets.token_hex(8)}"
        await save_user(
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
async def auto_login(device_id: str, _ = Depends(validate_api_key)):
  
    user = await get_user_by_device(device_id)  
    if not user:
        raise HTTPException(
            status_code=404,
            detail="No account linked to this device"
        )

    
    await revoke_old_sessions(user["user_id"])  

    
    access_token = create_jwt_token(user["user_id"])
    return UserResponse(
        user_id=user["user_id"],
        email=user["email"],
        access_token=access_token
    )

@app.post("/signin-to-new-device")
async def signin_to_new_device(
    device_id: str,
    google_token: str,
    user_id: str, _ = Depends(validate_api_key)
):
    
    user_email = verify_google_token(google_token)
    if not user_email:
        raise HTTPException(status_code=400, detail="Invalid Google token")

    
    existing_user = await get_user_by_device(device_id)  
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="This device is already linked to another account"
        )

    
    await save_user(
        user_id=user_id,
        email=user_email,
        device_id=device_id
    )
    
    access_token = create_jwt_token(user_id)
    return UserResponse(
        user_id=user_id,
        email=user_email,
        access_token=access_token
    )

@app.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {"user_id": user["user_id"], "email": user["email"]}