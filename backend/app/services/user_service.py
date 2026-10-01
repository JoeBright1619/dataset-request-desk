"""Business rules for administrator-managed users."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreateRequest, UserUpdateRequest


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)

    async def list_users(
        self, role: str | None, is_active: bool | None, limit: int
    ) -> list[User]:
        return await self._users.list(role, is_active, limit)

    async def get_user(self, user_id: UUID) -> User:
        user = await self._users.get(user_id)
        if user is None:
            raise NotFoundError()
        return user

    async def create_user(self, payload: UserCreateRequest) -> User:
        if await self._users.get_by_email(payload.email) is not None:
            raise AppError("VALIDATION_ERROR", "Email already exists", 409, "email")
        return await self._users.create(
            User(
                email=payload.email,
                name=payload.name,
                password_hash=hash_password(payload.password),
                role=payload.role,
                organisation=payload.organisation,
            )
        )

    async def update_user(
        self, user_id: UUID, payload: UserUpdateRequest, current_user: User
    ) -> User:
        user = await self.get_user(user_id)
        if user.id == current_user.id and (
            payload.is_active is False
            or (payload.role is not None and payload.role != user.role)
        ):
            raise ForbiddenError(
                "Administrators cannot deactivate or change their own role"
            )

        if payload.role is not None:
            user.role = payload.role
        if payload.is_active is not None:
            was_active = user.is_active
            user.is_active = payload.is_active
            if was_active and not user.is_active:
                await self._refresh_tokens.revoke_for_user(user.id, datetime.now(UTC))
        return user
