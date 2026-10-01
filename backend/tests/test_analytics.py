"""Deterministic database-level tests for analytics aggregates."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.episode import Episode
from app.models.request import Request
from app.models.user import User
from app.repositories.analytics_repository import AnalyticsRepository


async def create_client(db_session) -> User:
    client = User(
        email=f"analytics-{uuid4()}@example.com",
        password_hash="not-used",
        name="Analytics Client",
        role="client",
    )
    db_session.add(client)
    await db_session.flush()
    return client


async def create_episode(
    db_session,
    *,
    episode_id: str,
    task_name: str,
    robot_id: str,
    quality: str,
    recorded_at: datetime,
) -> None:
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
async def test_analytics_aggregates_are_computed_in_database(db_session):
    range_from = datetime(2026, 1, 1, tzinfo=UTC)
    range_to = datetime(2026, 1, 4, tzinfo=UTC)
    await create_episode(
        db_session,
        episode_id="analytics-1",
        task_name="pick_cups",
        robot_id="arm-01",
        quality="good",
        recorded_at=range_from + timedelta(hours=1),
    )
    await create_episode(
        db_session,
        episode_id="analytics-2",
        task_name="pick_cups",
        robot_id="arm-01",
        quality="good",
        recorded_at=range_from + timedelta(hours=2),
    )
    await create_episode(
        db_session,
        episode_id="analytics-3",
        task_name="fold_towels",
        robot_id="arm-02",
        quality="good",
        recorded_at=range_from + timedelta(days=1),
    )
    await create_episode(
        db_session,
        episode_id="analytics-4",
        task_name="pick_cups",
        robot_id="arm-01",
        quality="bad",
        recorded_at=range_from + timedelta(days=1),
    )
    client = await create_client(db_session)
    await create_request(
        db_session,
        client.id,
        status="delivered",
        created_at=range_from,
        delivered_at=range_from + timedelta(hours=24),
    )
    await create_request(
        db_session,
        client.id,
        status="delivered",
        created_at=range_from + timedelta(hours=1),
        delivered_at=range_from + timedelta(days=2, hours=1),
    )
    await create_request(
        db_session,
        client.id,
        status="submitted",
        created_at=range_from + timedelta(days=1),
    )

    repository = AnalyticsRepository(db_session)

    episodes = await repository.episodes_by_day_robot(range_from, range_to)
    assert [(item.date, item.robot_id, item.count) for item in episodes] == [
        (date(2026, 1, 1), "arm-01", 2),
        (date(2026, 1, 2), "arm-01", 1),
        (date(2026, 1, 2), "arm-02", 1),
    ]

    statuses = await repository.requests_by_status(range_from, range_to)
    assert [(item.status, item.count) for item in statuses] == [
        ("delivered", 2),
        ("submitted", 1),
    ]
    assert (
        await repository.median_submitted_to_delivered_hours(range_from, range_to)
        == 36.0
    )

    top_tasks = await repository.top_tasks_by_good_episodes(range_from, range_to)
    assert [(item.task_name, item.good_episodes) for item in top_tasks] == [
        ("pick_cups", 2),
        ("fold_towels", 1),
    ]

    robot_episodes = await repository.episodes_by_day_robot(
        range_from, range_to, "arm-01"
    )
    assert [(item.robot_id, item.count) for item in robot_episodes] == [
        ("arm-01", 2),
        ("arm-01", 1),
    ]


@pytest.mark.asyncio
async def test_analytics_returns_empty_results_for_an_empty_range(db_session):
    repository = AnalyticsRepository(db_session)
    range_from = datetime(2026, 4, 1, tzinfo=UTC)
    range_to = datetime(2026, 4, 2, tzinfo=UTC)

    assert await repository.episodes_by_day_robot(range_from, range_to) == []
    assert await repository.requests_by_status(range_from, range_to) == []
    assert (
        await repository.median_submitted_to_delivered_hours(range_from, range_to)
        is None
    )
    assert await repository.top_tasks_by_good_episodes(range_from, range_to) == []
