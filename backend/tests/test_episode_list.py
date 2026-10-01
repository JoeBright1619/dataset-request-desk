"""HTTP coverage for episode list and detail endpoints."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.security import hash_password
from app.db.session import get_session
from app.main import app
from app.models.episode import Episode
from app.models.user import User
from httpx import ASGITransport, AsyncClient


async def client_for_session(db_session) -> AsyncClient:
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def create_user(db_session, role: str) -> User:
    user = User(
        email=f"episode-{role}-{uuid4()}@example.com",
        password_hash=hash_password("correct-password"),
        name=f"Episode {role.title()}",
        role=role,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def access_token(client: AsyncClient, user: User) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "correct-password"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def create_episode(
    db_session, *, episode_id: str, recorded_at: datetime, quality: str = "good"
) -> Episode:
    episode = Episode(
        episode_id=episode_id,
        robot_id="arm-01",
        task_name="pick_cups",
        recorded_at=recorded_at,
        duration_seconds=Decimal("12.50"),
        operator_name="Rae",
        quality=quality,
    )
    db_session.add(episode)
    await db_session.flush()
    return episode


@pytest.mark.asyncio
async def test_episode_list_is_restricted_to_operational_roles(db_session):
    operator = await create_user(db_session, "operator")
    client_user = await create_user(db_session, "client")
    client = await client_for_session(db_session)
    try:
        operator_token = await access_token(client, operator)
        client_token = await access_token(client, client_user)

        allowed = await client.get(
            "/api/v1/episodes",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        denied = await client.get(
            "/api/v1/episodes",
            headers={"Authorization": f"Bearer {client_token}"},
        )

        assert allowed.status_code == 200
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "FORBIDDEN"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_episode_list_filters_and_navigates_with_cursors(db_session):
    operator = await create_user(db_session, "operator")
    now = datetime.now(UTC).replace(microsecond=0)
    await create_episode(db_session, episode_id="episode-001", recorded_at=now)
    await create_episode(
        db_session, episode_id="episode-002", recorded_at=now - timedelta(minutes=1)
    )
    await create_episode(
        db_session,
        episode_id="episode-003",
        recorded_at=now - timedelta(minutes=2),
        quality="usable",
    )
    client = await client_for_session(db_session)
    try:
        token = await access_token(client, operator)
        headers = {"Authorization": f"Bearer {token}"}
        first_page = await client.get(
            "/api/v1/episodes?quality=good&limit=1", headers=headers
        )

        assert first_page.status_code == 200
        first_body = first_page.json()
        assert first_body["items"][0]["episode_id"] == "episode-001"
        assert first_body["items"][0]["is_assigned"] is False
        assert first_body["has_more"] is True
        assert first_body["has_prev"] is False
        assert first_body["next_cursor"] is not None
        assert first_body["prev_cursor"] is None

        second_page = await client.get(
            "/api/v1/episodes",
            params={
                "quality": "good",
                "limit": 1,
                "cursor": first_body["next_cursor"],
            },
            headers=headers,
        )
        second_body = second_page.json()
        assert second_page.status_code == 200
        assert second_body["items"][0]["episode_id"] == "episode-002"
        assert second_body["has_more"] is False
        assert second_body["has_prev"] is True

        previous_page = await client.get(
            "/api/v1/episodes",
            params={
                "quality": "good",
                "limit": 1,
                "cursor": second_body["prev_cursor"],
            },
            headers=headers,
        )
        assert previous_page.status_code == 200
        assert previous_page.json()["items"][0]["episode_id"] == "episode-001"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unknown_episode_returns_not_found(db_session):
    operator = await create_user(db_session, "operator")
    client = await client_for_session(db_session)
    try:
        token = await access_token(client, operator)
        response = await client.get(
            "/api/v1/episodes/does-not-exist",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
