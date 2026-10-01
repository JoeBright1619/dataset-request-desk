"""HTTP endpoints for authentication and token lifecycle management."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.errors import InvalidCredentialsError
from app.core.security import verify_password
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
CurrentUser = Annotated[User, Depends(get_current_user)]


def token_response(tokens: TokenPair) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


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
    user: CurrentUser,
    payload: LogoutRequest = OPTIONAL_LOGOUT_BODY,
) -> Response:
    """Revoke the supplied refresh token, or all tokens for the caller."""
    await AuthService(session).logout(
        user.id,
        payload.refresh_token,
    )
    return Response(status_code=204)


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    user: CurrentUser,
) -> CurrentUserResponse:
    """Return the caller's current user profile."""
    return CurrentUserResponse.model_validate(user)
