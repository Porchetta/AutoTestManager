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
    module_name: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    password: Optional[str] = None
    module_name: Optional[str] = None
    is_admin: Optional[bool] = None
    is_approved: Optional[bool] = None

class UserResponse(UserBase):
    is_admin: bool
    is_approved: bool
    created: datetime

    class Config:
        from_attributes = True

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

# --- Config Schemas ---
class RTDConfigBase(BaseModel):
    line_name: str
    line_id: str
    business_unit: str
    home_dir_path: str
    modifier: Optional[str] = None

class RTDConfigCreate(RTDConfigBase):
    pass

class RTDConfigResponse(RTDConfigBase):
    created: datetime
    class Config:
        from_attributes = True

class EzDFSConfigBase(BaseModel):
    module_name: str
    port_num: str
    home_dir_path: str
    modifier: Optional[str] = None

class EzDFSConfigCreate(EzDFSConfigBase):
    pass

class EzDFSConfigResponse(EzDFSConfigBase):
    created: datetime
    class Config:
        from_attributes = True
