"""HTTP endpoint tests for analytics."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.core.security import hash_password
from app.db.session import get_session
from app.main import app
from app.models.episode import Episode
from app.models.request import Request
from app.models.user import User
from httpx import ASGITransport, AsyncClient


async def client_for_session(db_session) -> AsyncClient:
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def create_user(db_session, role: str, name: str = "Test User") -> User:
    user = User(
        email=f"analytics-api-{role}-{uuid4()}@example.com",
        password_hash=hash_password("correct-password"),
        name=name,
        role=role,
        is_active=True,
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
    db_session,
    *,
    episode_id: str,
    task_name: str,
    robot_id: str,
    quality: str,
    recorded_at: datetime,
) -> None:
    from decimal import Decimal

    db_session.add(
        Episode(
            episode_id=episode_id,
            task_name=task_name,
            robot_id=robot_id,
            quality=quality,
            recorded_at=recorded_at,
            duration_seconds=Decimal("30.00"),
        )
    )
    await db_session.flush()


async def create_request(
    db_session,
    client_id,
    *,
    status: str,
    created_at: datetime,
    delivered_at: datetime | None = None,
) -> None:
    from datetime import timedelta

    db_session.add(
        Request(
            client_id=client_id,
            task_name="pick_cups",
            episodes_requested=2,
            deadline=created_at + timedelta(days=7),
            status=status,
            created_at=created_at,
            updated_at=created_at,
            delivered_at=delivered_at,
        )
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_analytics_allows_operators_and_admins(db_session):
    operator = await create_user(db_session, "operator")
    admin = await create_user(db_session, "admin")

    client = await client_for_session(db_session)
    try:
        operator_token = await access_token(client, operator)
        admin_token = await access_token(client, admin)

        params = {
            "from": "2026-01-01T00:00:00Z",
            "to": "2026-02-01T00:00:00Z",
        }

        operator_response = await client.get(
            "/api/v1/analytics",
            params=params,
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert operator_response.status_code == 200

        admin_response = await client.get(
            "/api/v1/analytics",
            params=params,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert admin_response.status_code == 200
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_forbids_clients(db_session):
    client_user = await create_user(db_session, "client")

    client = await client_for_session(db_session)
    try:
        token = await access_token(client, client_user)

        response = await client.get(
            "/api/v1/analytics",
            params={
                "from": "2026-01-01T00:00:00Z",
                "to": "2026-02-01T00:00:00Z",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("range_from", "range_to"),
    [
        ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        ("2026-02-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    ],
)
async def test_analytics_rejects_invalid_range(
    db_session,
    range_from: str,
    range_to: str,
):
    operator = await create_user(db_session, "operator")

    client = await client_for_session(db_session)
    try:
        token = await access_token(client, operator)

        response = await client.get(
            "/api/v1/analytics",
            params={"from": range_from, "to": range_to},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing_parameter",
    ["from", "to"],
)
async def test_analytics_requires_from_and_to(db_session, missing_parameter: str):
    operator = await create_user(db_session, "operator")

    client = await client_for_session(db_session)
    try:
        token = await access_token(client, operator)

        params = {
            "from": "2026-01-01T00:00:00Z",
            "to": "2026-02-01T00:00:00Z",
        }
        del params[missing_parameter]

        response = await client.get(
            "/api/v1/analytics",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_returns_documented_response_shape(db_session):
    range_from = datetime(2026, 1, 1, tzinfo=UTC)
    range_to = datetime(2026, 1, 4, tzinfo=UTC)

    operator = await create_user(db_session, "operator")
    client_user = await create_user(db_session, "client")

    await create_episode(
        db_session,
        episode_id="analytics-api-1",
        task_name="pick_cups",
        robot_id="arm-01",
        quality="good",
        recorded_at=datetime(2026, 1, 1, 1, tzinfo=UTC),
    )
    await create_episode(
        db_session,
        episode_id="analytics-api-2",
        task_name="pick_cups",
        robot_id="arm-01",
        quality="good",
        recorded_at=datetime(2026, 1, 1, 2, tzinfo=UTC),
    )
    await create_episode(
        db_session,
        episode_id="analytics-api-3",
        task_name="fold_towels",
        robot_id="arm-02",
        quality="good",
        recorded_at=datetime(2026, 1, 2, 1, tzinfo=UTC),
    )
    await create_episode(
        db_session,
        episode_id="analytics-api-4",
        task_name="pick_cups",
        robot_id="arm-01",
        quality="bad",
        recorded_at=datetime(2026, 1, 2, 2, tzinfo=UTC),
    )

    await create_request(
        db_session,
        client_user.id,
        status="delivered",
        created_at=datetime(2026, 1, 1, 0, tzinfo=UTC),
        delivered_at=datetime(2026, 1, 2, 0, tzinfo=UTC),
    )
    await create_request(
        db_session,
        client_user.id,
        status="submitted",
        created_at=datetime(2026, 1, 2, 0, tzinfo=UTC),
    )

    client = await client_for_session(db_session)
    try:
        token = await access_token(client, operator)

        response = await client.get(
            "/api/v1/analytics",
            params={
                "from": range_from.isoformat(),
                "to": range_to.isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

        body = response.json()

        assert body["range"] == {
            "from": "2026-01-01T00:00:00Z",
            "to": "2026-01-04T00:00:00Z",
        }

        assert body["episodes_by_day_robot"] == [
            {
                "date": "2026-01-01",
                "robot_id": "arm-01",
                "count": 2,
            },
            {
                "date": "2026-01-02",
                "robot_id": "arm-01",
                "count": 1,
            },
            {
                "date": "2026-01-02",
                "robot_id": "arm-02",
                "count": 1,
            },
        ]

        assert body["requests_by_status"] == [
            {
                "status": "delivered",
                "count": 1,
            },
            {
                "status": "submitted",
                "count": 1,
            },
        ]

        assert body["median_submitted_to_delivered_hours"] == 24.0

        assert body["top_tasks_by_good_episodes"] == [
            {
                "task_name": "pick_cups",
                "good_episodes": 2,
            },
            {
                "task_name": "fold_towels",
                "good_episodes": 1,
            },
        ]
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_robot_id_filters_episode_metrics(db_session):
    operator = await create_user(db_session, "operator")
    client_user = await create_user(db_session, "client")

    await create_episode(
        db_session,
        episode_id="robot-filter-1",
        task_name="pick_cups",
        robot_id="arm-01",
        quality="good",
        recorded_at=datetime(2026, 1, 1, 1, tzinfo=UTC),
    )
    await create_episode(
        db_session,
        episode_id="robot-filter-2",
        task_name="pick_cups",
        robot_id="arm-02",
        quality="good",
        recorded_at=datetime(2026, 1, 1, 2, tzinfo=UTC),
    )
    await create_episode(
        db_session,
        episode_id="robot-filter-3",
        task_name="fold_towels",
        robot_id="arm-01",
        quality="good",
        recorded_at=datetime(2026, 1, 2, 1, tzinfo=UTC),
    )

    await create_request(
        db_session,
        client_user.id,
        status="submitted",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    client = await client_for_session(db_session)
    try:
        token = await access_token(client, operator)

        response = await client.get(
            "/api/v1/analytics",
            params={
                "from": "2026-01-01T00:00:00Z",
                "to": "2026-01-03T00:00:00Z",
                "robot_id": "arm-01",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

        body = response.json()

        assert body["episodes_by_day_robot"] == [
            {
                "date": "2026-01-01",
                "robot_id": "arm-01",
                "count": 1,
            },
            {
                "date": "2026-01-02",
                "robot_id": "arm-01",
                "count": 1,
            },
        ]

        assert body["top_tasks_by_good_episodes"] == [
            {
                "task_name": "fold_towels",
                "good_episodes": 1,
            },
            {
                "task_name": "pick_cups",
                "good_episodes": 1,
            },
        ]

        # Requests have no robot_id relationship, so the filter does not
        # affect request-level analytics.
        assert body["requests_by_status"] == [
            {
                "status": "submitted",
                "count": 1,
            }
        ]
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_empty_range_returns_empty_aggregates(db_session):
    operator = await create_user(db_session, "operator")

    client = await client_for_session(db_session)
    try:
        token = await access_token(client, operator)

        response = await client.get(
            "/api/v1/analytics",
            params={
                "from": "2026-04-01T00:00:00Z",
                "to": "2026-04-02T00:00:00Z",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

        assert response.json() == {
            "range": {
                "from": "2026-04-01T00:00:00Z",
                "to": "2026-04-02T00:00:00Z",
            },
            "episodes_by_day_robot": [],
            "requests_by_status": [],
            "median_submitted_to_delivered_hours": None,
            "top_tasks_by_good_episodes": [],
        }
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
