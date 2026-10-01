"""HTTP tests for administrator user management."""

from uuid import uuid4

import pytest
from app.core.security import hash_password
from app.db.session import get_session
from app.main import app
from app.models.user import User
from httpx import ASGITransport, AsyncClient


async def client_for_session(db_session) -> AsyncClient:
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def create_user(db_session, role: str, *, is_active: bool = True) -> User:
    user = User(
        email=f"users-{uuid4()}@example.com",
        password_hash=hash_password("correct-password"),
        name="User Management Test",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def login(client: AsyncClient, user: User) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "correct-password"},
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_only_admins_can_manage_users(db_session):
    admin = await create_user(db_session, "admin")
    operator = await create_user(db_session, "operator")
    client = await client_for_session(db_session)
    try:
        admin_tokens = await login(client, admin)
        operator_tokens = await login(client, operator)
        allowed = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
        )
        denied = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {operator_tokens['access_token']}"},
        )
        assert allowed.status_code == 200
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "FORBIDDEN"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_can_create_get_and_filter_users(db_session):
    admin = await create_user(db_session, "admin")
    client = await client_for_session(db_session)
    try:
        tokens = await login(client, admin)
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        response = await client.post(
            "/api/v1/users",
            headers=headers,
            json={
                "email": "new-operator@example.com",
                "name": "New Operator",
                "password": "new-password",
                "role": "operator",
            },
        )
        assert response.status_code == 201
        created = response.json()
        assert "password" not in created
        assert created["role"] == "operator"

        fetched = await client.get(f"/api/v1/users/{created['id']}", headers=headers)
        listed = await client.get("/api/v1/users?role=operator", headers=headers)
        assert fetched.status_code == 200
        assert listed.status_code == 200
        assert any(item["id"] == created["id"] for item in listed.json()["items"])
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_cannot_demote_or_deactivate_themselves(db_session):
    admin = await create_user(db_session, "admin")
    client = await client_for_session(db_session)
    try:
        tokens = await login(client, admin)
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        for payload in ({"role": "operator"}, {"is_active": False}):
            response = await client.patch(
                f"/api/v1/users/{admin.id}", headers=headers, json=payload
            )
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "FORBIDDEN"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_deactivation_revokes_a_users_refresh_tokens(db_session):
    admin = await create_user(db_session, "admin")
    target = await create_user(db_session, "client")
    client = await client_for_session(db_session)
    try:
        admin_tokens = await login(client, admin)
        target_tokens = await login(client, target)
        response = await client.patch(
            f"/api/v1/users/{target.id}",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json={"is_active": False},
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

        refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": target_tokens["refresh_token"]},
        )
        assert refresh.status_code == 401
        assert refresh.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
