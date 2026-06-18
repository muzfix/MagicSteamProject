import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

from app.modules.auth.models import UserRole

_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_-]+$')


def _validate_username_str(v: str) -> str:
    v = v.strip()
    if len(v) < 2:
        raise ValueError("Username must be at least 2 characters")
    if len(v) > 30:
        raise ValueError("Username must not exceed 30 characters")
    if not _USERNAME_RE.match(v):
        raise ValueError("Username may only contain letters, numbers, underscores, and hyphens")
    return v


def _validate_password_str(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v) > 128:
        raise ValueError("Password must not exceed 128 characters")
    return v


class UserRegister(BaseModel):
    email: EmailStr
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_str(v)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        return _validate_username_str(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    username: str
    role: UserRole
    guild_tag: Optional[str] = None
    username_changed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GuildTagUpdate(BaseModel):
    guild_tag: Optional[str] = None


class UsernameUpdate(BaseModel):
    new_username: str
    current_password: str

    @field_validator("new_username")
    @classmethod
    def validate_new_username(cls, v: str) -> str:
        return _validate_username_str(v)


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password_str(v)
