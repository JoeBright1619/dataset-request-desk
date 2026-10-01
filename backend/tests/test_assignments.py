"""Tests for assignment repository, service, and endpoints."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.core.security import hash_password
from app.db.session import get_session
from app.main import app
from app.models.episode import Episode
from app.models.request import Request
from app.models.user import User
from app.repositories.assignment_repository import (
    AssignmentRepository,
)
from httpx import ASGITransport, AsyncClient

# ── helpers ──────────────────────────────────────────────


async def _create_user(
    db_session, role: str = "operator", name: str = "Test User"
) -> User:
    user = User(
        email=f"asgn-{role}-{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("correct-password"),
        name=name,
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _create_episode(
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
        recorded_at=(recorded_at or datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)),
        duration_seconds=120,
    )
    db_session.add(episode)
    await db_session.flush()
    return episode


async def _create_request(
    db_session,
    client_user: User,
    status: str = "in_progress",
    episodes_requested: int = 5,
) -> Request:
    req = Request(
        client_id=client_user.id,
        task_name="pick_cup",
        episodes_requested=episodes_requested,
        deadline=datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
        status=status,
    )
    db_session.add(req)
    await db_session.flush()
    return req


async def _client_for_session(db_session) -> AsyncClient:
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )


async def _access_token(client: AsyncClient, user: User) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "correct-password",
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── repository-level tests ──────────────────────────────


@pytest.mark.asyncio
async def test_repo_batch_success_and_rejections(db_session):
    client_user = await _create_user(db_session, role="client")
    operator = await _create_user(db_session, role="operator")
    req = await _create_request(db_session, client_user)

    ep1 = await _create_episode(db_session, "ep_good_1")
    ep2 = await _create_episode(db_session, "ep_usable_2", quality="usable")
    ep3 = await _create_episode(db_session, "ep_bad_3", quality="bad")

    repo = AssignmentRepository(db_session)

    # Mixed batch: good, usable, bad, not_found, duplicate
    result = await repo.assign_batch(
        request_id=req.id,
        episode_ids=[
            ep1.episode_id,
            ep2.episode_id,
            ep3.episode_id,
            "ep_non_existent",
            ep1.episode_id,
        ],
        user_id=operator.id,
    )

    assert result.assigned == ["ep_good_1", "ep_usable_2"]
    rej = {r.episode_id: r.reason for r in result.rejected}
    assert rej["ep_bad_3"] == "invalid_quality"
    assert rej["ep_non_existent"] == "not_found"
    assert rej["ep_good_1"] == "already_assigned"

    # Cross-request collision via partial unique index
    req2 = await _create_request(db_session, client_user)
    r2 = await repo.assign_batch(
        request_id=req2.id,
        episode_ids=["ep_good_1"],
        user_id=operator.id,
    )
    assert r2.assigned == []
    assert r2.rejected[0].reason == "already_assigned"


@pytest.mark.asyncio
async def test_repo_release_and_reassign(db_session):
    client_user = await _create_user(db_session, role="client")
    operator = await _create_user(db_session, role="operator")
    req1 = await _create_request(db_session, client_user)
    req2 = await _create_request(db_session, client_user)
    ep = await _create_episode(db_session, "ep_rel")

    repo = AssignmentRepository(db_session)
    res = await repo.assign_batch(req1.id, [ep.episode_id], operator.id)
    assert res.assigned == [ep.episode_id]

    assert await repo.release(req1.id, ep.episode_id) is True
    assert await repo.release(req1.id, ep.episode_id) is False

    res2 = await repo.assign_batch(req2.id, [ep.episode_id], operator.id)
    assert res2.assigned == [ep.episode_id]


@pytest.mark.asyncio
async def test_repo_list_pagination(db_session):
    client_user = await _create_user(db_session, role="client")
    operator = await _create_user(db_session, role="operator")
    req = await _create_request(db_session, client_user)

    eps = []
    for i in range(5):
        ep = await _create_episode(
            db_session,
            f"ep_pg_{i:03d}",
            recorded_at=datetime(2026, 1, 1, 10, i, 0, tzinfo=UTC),
        )
        eps.append(ep)

    repo = AssignmentRepository(db_session)
    await repo.assign_batch(req.id, [e.episode_id for e in eps], operator.id)

    p1 = await repo.list_active_by_request_id(req.id, cursor=None, limit=2)
    assert len(p1.items) == 2
    assert p1.has_more is True

    p2 = await repo.list_active_by_request_id(req.id, cursor=p1.next_cursor, limit=2)
    assert len(p2.items) == 2
    assert p2.has_prev is True

    ids1 = {i.episode_domain_id for i in p1.items}
    ids2 = {i.episode_domain_id for i in p2.items}
    assert ids1.isdisjoint(ids2)


# ── endpoint-level tests ────────────────────────────────


@pytest.mark.asyncio
async def test_batch_assign_endpoint_success(db_session):
    """POST returns assigned/rejected with counts."""
    cli = await _create_user(db_session, "client", "Acme")
    op = await _create_user(db_session, "operator", "Op")
    req = await _create_request(db_session, cli, episodes_requested=10)
    ep1 = await _create_episode(db_session, "ep_e_1")
    ep2 = await _create_episode(db_session, "ep_e_bad", quality="bad")
    ep3 = await _create_episode(db_session, "ep_e_3")

    client = await _client_for_session(db_session)
    try:
        tok = await _access_token(client, op)
        url = f"/api/v1/requests/{req.id}/assignments"

        resp = await client.post(
            url,
            json={
                "episode_ids": [
                    ep1.episode_id,
                    ep2.episode_id,
                    ep3.episode_id,
                    "no_such_ep",
                ],
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["request_id"] == str(req.id)
        assert set(body["assigned"]) == {
            ep1.episode_id,
            ep3.episode_id,
        }
        rej = {r["episode_id"]: r["reason"] for r in body["rejected"]}
        assert rej[ep2.episode_id] == "invalid_quality"
        assert rej["no_such_ep"] == "not_found"
        assert body["episodes_requested"] == 10
        assert body["episodes_assigned"] == 2
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_client_cannot_assign(db_session):
    """Clients get 403 FORBIDDEN on POST."""
    cli = await _create_user(db_session, "client", "Acme")
    req = await _create_request(db_session, cli)
    ep = await _create_episode(db_session, "ep_cli")

    client = await _client_for_session(db_session)
    try:
        tok = await _access_token(client, cli)
        resp = await client.post(
            f"/api/v1/requests/{req.id}/assignments",
            json={"episode_ids": [ep.episode_id]},
            headers=_auth(tok),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_assign_wrong_status_409(db_session):
    """Assigning to a delivered request returns 409."""
    cli = await _create_user(db_session, "client", "Acme")
    op = await _create_user(db_session, "operator", "Op")
    req = await _create_request(db_session, cli, status="delivered")
    ep = await _create_episode(db_session, "ep_ws")

    client = await _client_for_session(db_session)
    try:
        tok = await _access_token(client, op)
        resp = await client.post(
            f"/api/v1/requests/{req.id}/assignments",
            json={"episode_ids": [ep.episode_id]},
            headers=_auth(tok),
        )
        assert resp.status_code == 409
        body = resp.json()["error"]
        assert body["code"] == "INVALID_STATUS_TRANSITION"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
