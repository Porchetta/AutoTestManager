from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# --- User Schemas ---
class UserBase(BaseModel):
    user_id: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    is_approved: Optional[bool] = None

class UserResponse(UserBase):
    is_admin: bool
    is_approved: bool
    created_at: datetime

    class Config:
        from_attributes = True

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

# --- Config Schemas ---
class RTDConfigBase(BaseModel):
    business_unit: str
    development_line: str
    home_dir_path: str
    is_target_line: bool

class RTDConfigCreate(RTDConfigBase):
    pass

class RTDConfigResponse(RTDConfigBase):
    id: int
    class Config:
        from_attributes = True

class EzDFSConfigBase(BaseModel):
    target_server_name: str
    dir_path: str

class EzDFSConfigCreate(EzDFSConfigBase):
    pass

class EzDFSConfigResponse(EzDFSConfigBase):
    id: int
    class Config:
        from_attributes = True
