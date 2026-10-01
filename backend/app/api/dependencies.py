"""Reusable dependencies for authentication and role-based authorization."""

from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationRequiredError, ForbiddenError
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.user import User

Session = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: Session,
    authorization: Annotated[str, Header()] = "",
) -> User:
    """Return the active user authenticated by a valid bearer token."""
    scheme, _, access_token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not access_token:
        raise AuthenticationRequiredError()

    try:
        claims = decode_access_token(access_token)
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise AuthenticationRequiredError() from None

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationRequiredError()
    return user


def require_roles(*roles: str) -> Callable[..., Awaitable[User]]:
    """Return a dependency that permits only users with one of *roles*."""
    allowed_roles = frozenset(roles)

    async def enforce_roles(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenError()
        return current_user

    return enforce_roles
