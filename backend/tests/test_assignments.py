"""Unit and integration tests for AssignmentRepository."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.models.episode import Episode
from app.models.request import Request
from app.models.user import User
from app.repositories.assignment_repository import AssignmentRepository


async def create_user(db_session, role: str = "operator") -> User:
    user = User(
        email=f"user_{uuid4().hex[:8]}@example.com",
        password_hash="dummy_hash",
        name="Test User",
        role=role,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def create_episode(
    db_session,
    episode_id: str,
    quality: str = "good",
    recorded_at: datetime | None = None,
) -> Episode:
    episode = Episode(
        episode_id=episode_id,
        task_name="pick_cup",
        robot_id="arm-1",
        quality=quality,
        recorded_at=recorded_at or datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        duration_seconds=120,
    )
    db_session.add(episode)
    await db_session.flush()
    return episode


async def create_request(db_session, client_user: User) -> Request:
    req = Request(
        client_id=client_user.id,
        task_name="pick_cup",
        episodes_requested=5,
        deadline=datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
        status="in_progress",
    )
    db_session.add(req)
    await db_session.flush()
    return req


@pytest.mark.asyncio
async def test_assign_batch_success_and_rejections(db_session):
    client_user = await create_user(db_session, role="client")
    operator_user = await create_user(db_session, role="operator")
    req = await create_request(db_session, client_user)

    ep_good_1 = await create_episode(db_session, "ep_good_1", quality="good")
    ep_usable_2 = await create_episode(db_session, "ep_usable_2", quality="usable")
    ep_bad_3 = await create_episode(db_session, "ep_bad_3", quality="bad")

    repo = AssignmentRepository(db_session)

    # 1. Batch assign with mixed scenarios: good, usable, bad,
    # not_found, and duplicate within the same batch.
    result = await repo.assign_batch(
        request_id=req.id,
        episode_ids=[
            ep_good_1.episode_id,
            ep_usable_2.episode_id,
            ep_bad_3.episode_id,
            "ep_non_existent",
            ep_good_1.episode_id,  # duplicate in batch
        ],
        user_id=operator_user.id,
    )

    assert result.assigned == ["ep_good_1", "ep_usable_2"]
    rejections = {r.episode_id: r.reason for r in result.rejected}
    assert rejections["ep_bad_3"] == "invalid_quality"
    assert rejections["ep_non_existent"] == "not_found"
    assert rejections["ep_good_1"] == "already_assigned"

    # 2. Attempt assigning already assigned episode in a different request
    req2 = await create_request(db_session, client_user)
    result2 = await repo.assign_batch(
        request_id=req2.id,
        episode_ids=["ep_good_1"],
        user_id=operator_user.id,
    )
    assert result2.assigned == []
    assert len(result2.rejected) == 1
    assert result2.rejected[0].episode_id == "ep_good_1"
    assert result2.rejected[0].reason == "already_assigned"


@pytest.mark.asyncio
async def test_release_and_reassign(db_session):
    client_user = await create_user(db_session, role="client")
    operator_user = await create_user(db_session, role="operator")
    req1 = await create_request(db_session, client_user)
    req2 = await create_request(db_session, client_user)
    ep = await create_episode(db_session, "ep_releasable", quality="good")

    repo = AssignmentRepository(db_session)

    # Assign to req1
    res1 = await repo.assign_batch(
        request_id=req1.id,
        episode_ids=[ep.episode_id],
        user_id=operator_user.id,
    )
    assert res1.assigned == [ep.episode_id]

    # Release from req1
    released = await repo.release(
        req1.id, ep.episode_id, release_reason="Defective item"
    )
    assert released is True

    # Releasing again returns False (no active assignment)
    released_again = await repo.release(req1.id, ep.episode_id)
    assert released_again is False

    # Now assigning to req2 succeeds because active assignment was released
    res2 = await repo.assign_batch(
        request_id=req2.id,
        episode_ids=[ep.episode_id],
        user_id=operator_user.id,
    )
    assert res2.assigned == [ep.episode_id]
    assert res2.rejected == []


@pytest.mark.asyncio
async def test_list_active_assignments_pagination(db_session):
    client_user = await create_user(db_session, role="client")
    operator_user = await create_user(db_session, role="operator")
    req = await create_request(db_session, client_user)

    episodes = []
    for i in range(5):
        ep = await create_episode(
            db_session,
            f"ep_list_{i:03d}",
            quality="good",
            recorded_at=datetime(2026, 1, 1, 10, i, 0, tzinfo=UTC),
        )
        episodes.append(ep)

    repo = AssignmentRepository(db_session)
    await repo.assign_batch(
        request_id=req.id,
        episode_ids=[e.episode_id for e in episodes],
        user_id=operator_user.id,
    )

    # List page 1 (limit 2)
    page1 = await repo.list_active_by_request_id(req.id, cursor=None, limit=2)
    assert len(page1.items) == 2
    assert page1.has_more is True
    assert page1.next_cursor is not None

    # List page 2 using cursor
    page2 = await repo.list_active_by_request_id(
        req.id, cursor=page1.next_cursor, limit=2
    )
    assert len(page2.items) == 2
    assert page2.has_prev is True
    assert page2.has_more is True

    # Check page 1 and page 2 items are mutually exclusive
    page1_ids = [item.episode_domain_id for item in page1.items]
    page2_ids = [item.episode_domain_id for item in page2.items]
    assert set(page1_ids).isdisjoint(set(page2_ids))
