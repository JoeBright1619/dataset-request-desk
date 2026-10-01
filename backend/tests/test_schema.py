"""
Tests for database schema constraints and seed idempotency.

Verifies:
1. Partial unique index on assignments prevents duplicate active assignments
2. Release-then-reassign workflow succeeds
3. Seed idempotency (running seed twice produces no duplicates)
"""

from datetime import UTC, datetime

import pytest
from app.models.assignment import Assignment
from app.models.episode import Episode
from app.models.request import Request
from app.models.user import User
from app.services.seed_service import seed_users
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError


@pytest.mark.asyncio
async def test_partial_unique_index_prevents_duplicate_active_assignments(db_session):
    """Test that the partial unique index rejects a second active assignment.

    The index: ix_assignments_episode_id_active on
    (episode_id) WHERE released_at IS NULL
    ensures that an episode can only have one active (non-released)
    assignment at a time.
    """
    session = db_session

    # Create test user (operator)
    user = User(
        email="test-operator@example.com",
        password_hash="dummy_hash",
        name="Test Operator",
        role="operator",
    )
    session.add(user)
    await session.flush()

    # Create test episode
    episode = Episode(
        episode_id="test-episode-001",
        task_name="test_task",
        robot_id="robot-1",
        quality="good",
        recorded_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        duration_seconds=120,
    )
    session.add(episode)
    await session.flush()

    # Create test client
    client = User(
        email="test-client@example.com",
        password_hash="dummy_hash",
        name="Test Client",
        role="client",
    )
    session.add(client)
    await session.flush()

    # Create test request
    request = Request(
        client_id=client.id,
        task_name="test_task",
        episodes_requested=1,
        deadline=datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
        status="submitted",
    )
    session.add(request)
    await session.flush()

    # Create first active assignment (released_at = NULL)
    assignment1 = Assignment(
        request_id=request.id,
        episode_id=episode.id,
        assigned_by=user.id,
    )
    session.add(assignment1)
    await session.flush()

    # Try to create a second active assignment for the same episode
    assignment2 = Assignment(
        request_id=request.id,
        episode_id=episode.id,
        assigned_by=user.id,
    )
    session.add(assignment2)

    # This should raise IntegrityError due to the partial unique index
    with pytest.raises(IntegrityError) as exc_info:
        await session.flush()

    # Verify the error is about the unique constraint
    error_msg = str(exc_info.value).lower()
    assert (
        "ix_assignments_episode_id_active" in error_msg or "duplicate key" in error_msg
    )


@pytest.mark.asyncio
async def test_release_then_reassign_succeeds(db_session):
    """Test that releasing an assignment and then reassigning succeeds.

    Once released_at is set, the partial unique index no longer applies,
    allowing the same episode to be assigned again.
    """
    session = db_session

    # Create test user
    user = User(
        email="test-operator2@example.com",
        password_hash="dummy_hash",
        name="Test Operator 2",
        role="operator",
    )
    session.add(user)
    await session.flush()

    # Create test episode
    episode = Episode(
        episode_id="test-episode-002",
        task_name="test_task2",
        robot_id="robot-2",
        quality="good",
        recorded_at=datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC),
        duration_seconds=150,
    )
    session.add(episode)
    await session.flush()

    # Create test client and request
    client = User(
        email="test-client2@example.com",
        password_hash="dummy_hash",
        name="Test Client 2",
        role="client",
    )
    session.add(client)
    await session.flush()

    request1 = Request(
        client_id=client.id,
        task_name="test_task2",
        episodes_requested=1,
        deadline=datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
        status="submitted",
    )
    session.add(request1)
    await session.flush()

    # Create first assignment
    assignment1 = Assignment(
        request_id=request1.id,
        episode_id=episode.id,
        assigned_by=user.id,
    )
    session.add(assignment1)
    await session.flush()

    # Release the first assignment by setting released_at
    assignment1.released_at = datetime.now(UTC)
    await session.flush()

    # Create second request
    request2 = Request(
        client_id=client.id,
        task_name="test_task2",
        episodes_requested=1,
        deadline=datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
        status="submitted",
    )
    session.add(request2)
    await session.flush()

    # Create second assignment for the same episode
    assignment2 = Assignment(
        request_id=request2.id,
        episode_id=episode.id,
        assigned_by=user.id,
    )
    session.add(assignment2)

    # This should succeed because assignment1 is released
    await session.flush()

    # Verify both assignments exist
    result = await session.execute(
        select(Assignment).where(Assignment.episode_id == episode.id)
    )
    assignments = result.scalars().all()
    assert len(assignments) == 2
    assert assignments[0].released_at is not None  # First is released
    assert assignments[1].released_at is None  # Second is active


@pytest.mark.asyncio
async def test_seed_idempotency(db_session):
    """Running seed_users twice in the same transaction produces no duplicates."""
    session = db_session

    result1 = await seed_users(session)
    assert result1["created"] + result1["existing"] == 5

    result2 = await seed_users(session)
    assert result2["created"] == 0
    assert result2["existing"] == 5

    seed_emails = [
        "admin@example.com",
        "ops1@example.com",
        "ops2@example.com",
        "client-a@example.com",
        "client-b@example.com",
    ]
    result = await session.execute(select(User).where(User.email.in_(seed_emails)))
    rows = result.scalars().all()
    assert len(rows) == 5

    for email in seed_emails:
        count = (
            await session.execute(
                select(func.count()).select_from(User).where(User.email == email)
            )
        ).scalar_one()
        assert count == 1, f"{email} should appear exactly once"


@pytest.mark.asyncio
async def test_seed_users_have_correct_attributes(db_session):
    session = db_session
    await seed_users(session)  # <-- seed inside this test's transaction

    admin = (
        await session.execute(select(User).where(User.email == "admin@example.com"))
    ).scalar_one()
    assert admin.name == "Ada Admin"
    assert admin.role == "admin"
    assert admin.organisation is None
    assert admin.is_active is True
    assert admin.password_hash

    ops1 = (
        await session.execute(select(User).where(User.email == "ops1@example.com"))
    ).scalar_one()
    assert ops1.name == "Olu Operator"
    assert ops1.role == "operator"
    assert ops1.organisation is None

    client_a = (
        await session.execute(select(User).where(User.email == "client-a@example.com"))
    ).scalar_one()
    assert client_a.name == "Acme Robotics"
    assert client_a.role == "client"
    assert client_a.organisation == "Acme Robotics"

    client_b = (
        await session.execute(select(User).where(User.email == "client-b@example.com"))
    ).scalar_one()
    assert client_b.name == "Beta Labs"
    assert client_b.role == "client"
    assert client_b.organisation == "Beta Labs"
