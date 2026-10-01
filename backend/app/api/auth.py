"""HTTP endpoints for authentication and token lifecycle management."""

from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Body, Depends, Header, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationRequiredError, InvalidCredentialsError
from app.core.security import decode_access_token, verify_password
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])
OPTIONAL_LOGOUT_BODY = Body(default_factory=LogoutRequest)

Session = Annotated[AsyncSession, Depends(get_session)]


def token_response(tokens: TokenPair) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


async def authenticated_user(authorization: str | None, session: AsyncSession) -> User:
    """Load the active user named by a valid bearer token."""
    if authorization is None:
        raise AuthenticationRequiredError()

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


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: Session) -> TokenResponse:
    """Authenticate with an email and password."""
    user = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise InvalidCredentialsError()

    try:
        password_matches = verify_password(payload.password, user.password_hash)
    except ValueError:
        password_matches = False
    if not password_matches:
        raise InvalidCredentialsError()

    return token_response(await AuthService(session).issue_tokens(user))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, session: Session) -> TokenResponse:
    """Rotate an opaque refresh token."""
    return token_response(await AuthService(session).refresh(payload.refresh_token))


@router.post("/logout", status_code=204)
async def logout(
    session: Session,
    payload: LogoutRequest = OPTIONAL_LOGOUT_BODY,
    authorization: Annotated[str, Header()] = "",
) -> Response:
    """Revoke the supplied refresh token, or all tokens for the caller."""
    user = await authenticated_user(authorization, session)
    await AuthService(session).logout(
        user.id,
        payload.refresh_token,
    )
    return Response(status_code=204)


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    session: Session,
    authorization: Annotated[str, Header()] = "",
) -> CurrentUserResponse:
    """Return the caller's current user profile."""
    return CurrentUserResponse.model_validate(
        await authenticated_user(authorization, session)
    )
