from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    user_name: str
    module_name: str
    is_admin: bool
    is_approved: bool
    created_at: datetime
    updated_at: datetime


class RoleUpdateRequest(BaseModel):
    is_admin: bool


class UserUpdateRequest(BaseModel):
    module_name: str
    is_admin: bool
    is_approved: bool


class HostConfigCreate(BaseModel):
    name: str
    ip: str
    login_user: str
    login_password: str


class HostConfigUpdate(BaseModel):
    name: str
    ip: str
    login_user: str
    login_password: str


class HostConfigResponse(HostConfigCreate):
    model_config = ConfigDict(from_attributes=True)

    modifier: str
    created_at: datetime
    updated_at: datetime


class HostSshLimitResponse(BaseModel):
    host_name: str
    parallel_limit: int
    source: str


class RtdConfigCreate(BaseModel):
    line_name: str
    line_id: str
    business_unit: str
    home_dir_path: str
    host_name: str


class RtdConfigUpdate(BaseModel):
    line_name: str
    line_id: str
    business_unit: str
    home_dir_path: str
    host_name: str


class RtdConfigResponse(RtdConfigCreate):
    model_config = ConfigDict(from_attributes=True)

    modifier: str
    created_at: datetime
    updated_at: datetime


class EzdfsConfigCreate(BaseModel):
    module_name: str
    port: int
    home_dir_path: str
    host_name: str


class EzdfsConfigUpdate(BaseModel):
    module_name: str
    port: int
    home_dir_path: str
    host_name: str


class EzdfsConfigResponse(EzdfsConfigCreate):
    model_config = ConfigDict(from_attributes=True)

    modifier: str
    created_at: datetime
    updated_at: datetime
