"""Authentication token issuance, refresh, and reuse detection."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationRequiredError
from app.core.security import (
    ACCESS_TOKEN_LIFETIME,
    REFRESH_TOKEN_LIFETIME,
    create_access_token,
)
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository


@dataclass(frozen=True)
class TokenPair:
    """Credentials returned after a successful login or token refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = int(ACCESS_TOKEN_LIFETIME.total_seconds())


def hash_refresh_token(token: str) -> str:
    """Produce the stable, non-reversible value persisted for an opaque token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    """Create an opaque, high-entropy refresh token for a client."""
    return f"rt_{secrets.token_urlsafe(32)}"


class AuthService:
    """Own the refresh-token lifecycle within a database transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._refresh_tokens = RefreshTokenRepository(session)

    async def issue_tokens(self, user: User) -> TokenPair:
        """Issue a JWT access token and persist a new opaque refresh token."""
        now = datetime.now(UTC)
        refresh_token = generate_refresh_token()
        await self._refresh_tokens.create(
            user_id=user.id,
            family_id=uuid4(),
            token_hash=hash_refresh_token(refresh_token),
            expires_at=now + REFRESH_TOKEN_LIFETIME,
        )
        return TokenPair(
            access_token=create_access_token(user.id, user.role),
            refresh_token=refresh_token,
        )

    async def refresh(self, refresh_token: str) -> TokenPair:
        """Rotate a refresh token, revoking its family if reuse is detected."""
        token = await self._refresh_tokens.get_by_hash_for_update(
            hash_refresh_token(refresh_token)
        )
        if token is None:
            raise AuthenticationRequiredError()

        now = datetime.now(UTC)
        if token.used_at is not None:
            await self._refresh_tokens.revoke_family(token.family_id, now)
            # The request-session dependency rolls back on an AppError. Reuse
            # revocation must survive that error response, so persist it first.
            await self._session.commit()
            raise AuthenticationRequiredError()

        if token.revoked_at is not None or token.expires_at <= now:
            raise AuthenticationRequiredError()

        user = await self._session.get(User, token.user_id)
        if user is None or not user.is_active:
            raise AuthenticationRequiredError()

        token.used_at = now
        next_refresh_token = generate_refresh_token()
        await self._refresh_tokens.create(
            user_id=user.id,
            family_id=token.family_id,
            token_hash=hash_refresh_token(next_refresh_token),
            expires_at=now + REFRESH_TOKEN_LIFETIME,
        )
        return TokenPair(
            access_token=create_access_token(user.id, user.role),
            refresh_token=next_refresh_token,
        )

    async def logout(self, user_id: UUID, refresh_token: str | None = None) -> None:
        """Revoke one supplied refresh token or every token for the user."""
        token_hash = (
            hash_refresh_token(refresh_token) if refresh_token is not None else None
        )
        await self._refresh_tokens.revoke_for_user(
            user_id,
            datetime.now(UTC),
            token_hash,
        )
