"""Administrator-only user-management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_roles
from app.db.session import get_session
from app.models.user import User
from app.schemas.user import (
    UserCreateRequest,
    UserListResponse,
    UserResponse,
    UserRole,
    UserUpdateRequest,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])
Session = Annotated[AsyncSession, Depends(get_session)]
AdminUser = Annotated[User, Depends(require_roles("admin"))]


@router.get("", response_model=UserListResponse)
async def list_users(
    session: Session,
    _: AdminUser,
    role: UserRole | None = None,
    is_active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> UserListResponse:
    users = await UserService(session).list_users(role, is_active, limit)
    return UserListResponse(
        items=[UserResponse.model_validate(user) for user in users],
        limit=limit,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest, session: Session, _: AdminUser
) -> UserResponse:
    return UserResponse.model_validate(await UserService(session).create_user(payload))


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, session: Session, _: AdminUser) -> UserResponse:
    return UserResponse.model_validate(await UserService(session).get_user(user_id))


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    session: Session,
    current_user: AdminUser,
) -> UserResponse:
    return UserResponse.model_validate(
        await UserService(session).update_user(user_id, payload, current_user)
    )
