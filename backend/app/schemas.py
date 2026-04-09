from pydantic import BaseModel
from typing import Optional, List, Dict
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
class HostConfigBase(BaseModel):
    ip: str
    user_id: str
    password: str


class HostConfigCreate(HostConfigBase):
    pass


class HostConfigResponse(HostConfigBase):
    created: datetime

    class Config:
        from_attributes = True


class RTDConfigBase(BaseModel):
    line_name: str
    line_id: str
    business_unit: str
    home_dir_path: str
    host: str
    modifier: Optional[str] = None

class RTDConfigCreate(RTDConfigBase):
    pass

class RTDConfigResponse(RTDConfigBase):
    created: datetime
    class Config:
        from_attributes = True


class RTDLineResponse(BaseModel):
    line_name: str
    line_id: str
    home_dir_path: str


class RTDRuleResponse(BaseModel):
    home_dir_path: str
    rules: List[str]

class EzDFSConfigBase(BaseModel):
    module_name: str
    port_num: str
    home_dir_path: str
    host: str
    modifier: Optional[str] = None

class EzDFSConfigCreate(EzDFSConfigBase):
    pass

class EzDFSConfigResponse(EzDFSConfigBase):
    created: datetime
    class Config:
        from_attributes = True


class RTDTestRequest(BaseModel):
    rule_id: str
    target_lines: List[str]


class RTDLineStatus(BaseModel):
    line_name: str
    status: str
    raw_result_path: Optional[str] = None
    progress: int


class RTDStatusResponse(BaseModel):
    task_id: str
    status: str
    line_statuses: List[RTDLineStatus]


class RTDSessionPayload(BaseModel):
    step: int
    selectedBusiness: Optional[str] = None
    selectedLine: Optional[str] = None
    selectedRule: Optional[str] = None
    selectedTargets: List[str] = []
    summaryText: Optional[str] = None


class EzdfsTarget(BaseModel):
    module_name: str
    rule_name: str


class EzdfsTestRequest(BaseModel):
    targets: List[EzdfsTarget]


class EzdfsTargetStatus(BaseModel):
    module_name: str
    status: str
    raw_result_path: Optional[str] = None
    progress: int


class EzdfsStatusResponse(BaseModel):
    task_id: str
    status: str
    target_statuses: List[EzdfsTargetStatus]


class EzdfsSessionPayload(BaseModel):
    targets: List[Dict[str, Optional[str]]]
    summaryText: Optional[str] = None
