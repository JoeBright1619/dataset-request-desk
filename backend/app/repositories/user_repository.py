"""Persistence operations for users."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: object) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        return (
            await self._session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

    async def list(
        self, role: str | None, is_active: bool | None, limit: int
    ) -> list[User]:
        statement = select(User).order_by(User.created_at.desc(), User.id.desc())
        if role is not None:
            statement = statement.where(User.role == role)
        if is_active is not None:
            statement = statement.where(User.is_active == is_active)
        result = await self._session.execute(statement.limit(limit))
        return list(result.scalars().all())

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user
