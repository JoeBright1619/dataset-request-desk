"""HTTP tests for the authentication endpoints."""

from typing import Annotated
from uuid import uuid4

import pytest
from app.api.dependencies import require_roles
from app.core.security import hash_password
from app.db.session import get_session
from app.main import app
from app.models.user import User
from fastapi import Depends
from httpx import ASGITransport, AsyncClient

AdminUser = Annotated[User, Depends(require_roles("admin"))]


@app.get("/test-admin-only")
async def admin_only_route(user: AdminUser) -> dict[str, str]:
    return {"email": user.email}


async def client_for_session(db_session) -> AsyncClient:
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def create_user(db_session, *, is_active: bool = True) -> User:
    user = User(
        email=f"auth-{uuid4()}@example.com",
        password_hash=hash_password("correct-password"),
        name="Auth Test User",
        role="operator",
        is_active=is_active,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_login_returns_tokens_and_me_returns_the_user(db_session):
    user = await create_user(db_session)
    client = await client_for_session(db_session)
    try:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "correct-password"},
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] == 1800
        assert tokens["access_token"]
        assert tokens["refresh_token"].startswith("rt_")

        me_response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["id"] == str(user.id)
        assert me_response.json()["email"] == user.email
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_failures_share_the_same_invalid_credentials_response(db_session):
    active_user = await create_user(db_session)
    inactive_user = await create_user(db_session, is_active=False)
    client = await client_for_session(db_session)
    try:
        responses = [
            await client.post(
                "/api/v1/auth/login",
                json={"email": "unknown@example.com", "password": "wrong"},
            ),
            await client.post(
                "/api/v1/auth/login",
                json={"email": active_user.email, "password": "wrong"},
            ),
            await client.post(
                "/api/v1/auth/login",
                json={"email": inactive_user.email, "password": "correct-password"},
            ),
        ]
        assert all(response.status_code == 401 for response in responses)
        assert all(response.json() == responses[0].json() for response in responses)
        assert responses[0].json()["error"]["code"] == "INVALID_CREDENTIALS"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_refresh_and_logout_endpoints(db_session):
    user = await create_user(db_session)
    client = await client_for_session(db_session)
    try:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "correct-password"},
        )
        tokens = login_response.json()
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh_response.status_code == 200
        refreshed = refresh_response.json()

        logout_response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refreshed["refresh_token"]},
            headers={"Authorization": f"Bearer {refreshed['access_token']}"},
        )
        assert logout_response.status_code == 204

        rejected_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refreshed["refresh_token"]},
        )
        assert rejected_refresh.status_code == 401
        assert rejected_refresh.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_missing_or_invalid_access_token_returns_authentication_required(
    db_session,
):
    client = await client_for_session(db_session)
    try:
        missing = await client.get("/api/v1/auth/me")
        invalid = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert missing.status_code == 401
        assert invalid.status_code == 401
        assert missing.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
        assert invalid.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_require_roles_rejects_a_user_with_the_wrong_role(db_session):
    user = await create_user(db_session)
    client = await client_for_session(db_session)
    try:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "correct-password"},
        )
        response = await client.get(
            "/test-admin-only",
            headers={
                "Authorization": f"Bearer {login_response.json()['access_token']}"
            },
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
