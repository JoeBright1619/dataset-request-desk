"""Schemas for administrator user management."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

UserRole = Literal["client", "operator", "admin"]


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, repr=False)
    role: UserRole
    organisation: str | None = Field(default=None, max_length=128)


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserListResponse(BaseModel):
    items: list[UserResponse]
    next_cursor: str | None = None
    prev_cursor: str | None = None
    has_more: bool = False
    has_prev: bool = False
    limit: int
