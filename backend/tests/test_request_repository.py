"""Unit and integration tests for RequestRepository."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.models.assignment import Assignment
from app.models.episode import Episode
from app.models.request import Request
from app.models.user import User
from app.repositories.request_repository import RequestFilters, RequestRepository


async def create_user(db_session, role: str, name: str = "Test User") -> User:
    user = User(
        email=f"user-{role}-{uuid4()}@example.com",
        password_hash="hashed_pw",
        name=name,
        role=role,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def create_request(
    db_session,
    client: User,
    task_name: str = "pick_cups",
    status: str = "submitted",
    created_at: datetime | None = None,
    episodes_requested: int = 10,
) -> Request:
    now = datetime.now(UTC)
    req = Request(
        client_id=client.id,
        task_name=task_name,
        episodes_requested=episodes_requested,
        deadline=now + timedelta(days=7),
        notes="Some notes",
        status=status,
    )
    if created_at is not None:
        req.created_at = created_at
    db_session.add(req)
    return req


async def create_assignment(
    db_session, request: Request, user: User, released: bool = False
) -> Assignment:
    episode = Episode(
        episode_id=f"ep-{uuid4()}",
        robot_id="arm-01",
        task_name=request.task_name,
        recorded_at=datetime.now(UTC),
        duration_seconds=10.0,
        quality="good",
    )
    db_session.add(episode)
    await db_session.flush()

    assignment = Assignment(
        request_id=request.id,
        episode_id=episode.id,
        assigned_by=user.id,
        released_at=datetime.now(UTC) if released else None,
    )
    db_session.add(assignment)
    await db_session.flush()
    return assignment


@pytest.mark.asyncio
async def test_request_repository_create_and_get(db_session):
    client = await create_user(db_session, "client", name="Acme Robotics")
    repo = RequestRepository(db_session)

    req = Request(
        client_id=client.id,
        task_name="pick_cups",
        episodes_requested=50,
        deadline=datetime.now(UTC) + timedelta(days=3),
        notes="High priority",
        status="submitted",
    )
    created = await repo.create(req)
    assert created.id is not None
    assert created.status == "submitted"

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.task_name == "pick_cups"

    details = await repo.get_details_by_id(created.id)
    assert details is not None
    assert details.request.id == created.id
    assert details.client_name == "Acme Robotics"
    assert details.episodes_assigned == 0


@pytest.mark.asyncio
async def test_request_repository_get_details_with_assignments(db_session):
    client = await create_user(db_session, "client", name="Beta Corp")
    operator = await create_user(db_session, "operator")
    repo = RequestRepository(db_session)

    req = await create_request(db_session, client)
    await create_assignment(db_session, req, operator, released=False)
    await create_assignment(db_session, req, operator, released=False)
    await create_assignment(db_session, req, operator, released=True)

    details = await repo.get_details_by_id(req.id)
    assert details is not None
    assert details.episodes_assigned == 2

    count = await repo.count_active_assignments(req.id)
    assert count == 2


@pytest.mark.asyncio
async def test_request_repository_list_and_cursor_pagination(db_session):
    client1 = await create_user(db_session, "client", name="Client One")
    client2 = await create_user(db_session, "client", name="Client Two")
    repo = RequestRepository(db_session)

    now = datetime.now(UTC).replace(microsecond=0)
    req1 = await create_request(db_session, client1, task_name="task_a", created_at=now)
    req2 = await create_request(
        db_session, client1, task_name="task_a", created_at=now - timedelta(minutes=1)
    )
    await create_request(
        db_session, client2, task_name="task_b", created_at=now - timedelta(minutes=2)
    )

    page1 = await repo.list(RequestFilters(client_id=client1.id), cursor=None, limit=1)
    assert len(page1.items) == 1
    assert page1.items[0].request.id == req1.id
    assert page1.has_more is True
    assert page1.has_prev is False
    assert page1.next_cursor is not None

    page2 = await repo.list(
        RequestFilters(client_id=client1.id), cursor=page1.next_cursor, limit=1
    )
    assert len(page2.items) == 1
    assert page2.items[0].request.id == req2.id
    assert page2.has_more is False
    assert page2.has_prev is True
    assert page2.prev_cursor is not None

    prev_page = await repo.list(
        RequestFilters(client_id=client1.id), cursor=page2.prev_cursor, limit=1
    )
    assert len(prev_page.items) == 1
    assert prev_page.items[0].request.id == req1.id


@pytest.mark.asyncio
async def test_request_repository_update_status_and_history(db_session):
    client = await create_user(db_session, "client")
    operator = await create_user(db_session, "operator")
    repo = RequestRepository(db_session)

    req = await create_request(db_session, client, status="submitted")

    delivered_time = datetime.now(UTC)
    updated = await repo.update_status(
        req, new_status="delivered", delivered_at=delivered_time
    )
    assert updated.status == "delivered"
    assert updated.delivered_at == delivered_time

    history = await repo.append_history(
        request_id=req.id,
        previous_status="submitted",
        new_status="delivered",
        changed_by=operator.id,
        reason="QA passed",
    )
    assert history.id is not None
    assert history.reason == "QA passed"

    history_list = await repo.list_history(req.id)
    assert len(history_list) == 1
    assert history_list[0].previous_status == "submitted"
    assert history_list[0].new_status == "delivered"
    assert history_list[0].changed_by == operator.id
