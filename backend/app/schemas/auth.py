from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SignupRequest(BaseModel):
    user_id: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=100)
    user_name: str = Field(min_length=1, max_length=100)
    module_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    user_id: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=4, max_length=100)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    user_name: str
    module_name: str
    is_admin: bool
    is_approved: bool
    created_at: datetime
    updated_at: datetime
