"""Tests for request state machine transitions, preconditions,
permissions, and concurrency."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.core.security import hash_password
from app.db.session import get_session
from app.main import app
from app.models.assignment import Assignment
from app.models.episode import Episode
from app.models.request import Request
from app.models.user import User
from app.repositories.request_repository import RequestRepository
from httpx import ASGITransport, AsyncClient


async def client_for_session(db_session) -> AsyncClient:
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def create_user(db_session, role: str, name: str = "Test User") -> User:
    user = User(
        email=f"workflow-{role}-{uuid4()}@example.com",
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


async def create_request(
    db_session,
    client_user: User,
    *,
    status: str = "submitted",
    episodes_requested: int = 2,
) -> Request:
    repo = RequestRepository(db_session)
    deadline = datetime.now(UTC) + timedelta(days=5)
    req = Request(
        client_id=client_user.id,
        task_name="reach_target",
        episodes_requested=episodes_requested,
        deadline=deadline,
        notes="Workflow test request",
        status=status,
    )
    created = await repo.create(req)
    await repo.append_history(
        request_id=created.id,
        previous_status=None,
        new_status=status,
        changed_by=client_user.id,
    )
    return created


async def assign_episodes(
    db_session, request: Request, operator: User, count: int
) -> None:
    for _ in range(count):
        ep = Episode(
            episode_id=f"ep-{uuid4()}",
            robot_id="arm-01",
            task_name=request.task_name,
            recorded_at=datetime.now(UTC),
            duration_seconds=12.0,
            quality="good",
        )
        db_session.add(ep)
        await db_session.flush()

        assignment = Assignment(
            request_id=request.id,
            episode_id=ep.id,
            assigned_by=operator.id,
            released_at=None,
        )
        db_session.add(assignment)
    await db_session.flush()


@pytest.mark.asyncio
async def test_full_successful_request_lifecycle(db_session):
    client_user = await create_user(db_session, "client", name="Client User")
    operator_user = await create_user(db_session, "operator", name="Operator User")

    client = await client_for_session(db_session)
    try:
        client_tok = await access_token(client, client_user)
        op_tok = await access_token(client, operator_user)

        # 1. Client creates request (starts submitted)
        req = await create_request(db_session, client_user, episodes_requested=2)

        # 2. Operator transitions submitted -> in_progress
        res1 = await client.post(
            f"/api/v1/requests/{req.id}/status",
            json={"status": "in_progress", "reason": "Operator picked up ticket"},
            headers={"Authorization": f"Bearer {op_tok}"},
        )
        assert res1.status_code == 200
        assert res1.json()["status"] == "in_progress"

        # 3. Try to deliver with insufficient episodes (0 assigned, 2 requested) -> 409
        res_fail_deliver = await client.post(
            f"/api/v1/requests/{req.id}/status",
            json={"status": "delivered"},
            headers={"Authorization": f"Bearer {op_tok}"},
        )
        assert res_fail_deliver.status_code == 409
        assert res_fail_deliver.json()["error"]["code"] == "INSUFFICIENT_EPISODES"

        # Assign required episodes
        await assign_episodes(db_session, req, operator_user, count=2)

        # 4. Operator transitions in_progress -> delivered
        res2 = await client.post(
            f"/api/v1/requests/{req.id}/status",
            json={"status": "delivered", "reason": "Data collection complete"},
            headers={"Authorization": f"Bearer {op_tok}"},
        )
        assert res2.status_code == 200
        assert res2.json()["status"] == "delivered"
        assert res2.json()["delivered_at"] is not None

        # 5. Client transitions delivered -> accepted (terminal)
        res3 = await client.post(
            f"/api/v1/requests/{req.id}/status",
            json={"status": "accepted", "reason": "Approved by client QA"},
            headers={"Authorization": f"Bearer {client_tok}"},
        )
        assert res3.status_code == 200
        assert res3.json()["status"] == "accepted"

        # 6. Accepted is terminal -> any further transition
        # returns 409 INVALID_STATUS_TRANSITION
        res_terminal = await client.post(
            f"/api/v1/requests/{req.id}/status",
            json={"status": "in_progress"},
            headers={"Authorization": f"Bearer {op_tok}"},
        )
        assert res_terminal.status_code == 409
        assert res_terminal.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"

        # Verify history rows in repository
        repo = RequestRepository(db_session)
        history = await repo.list_history(req.id)
        statuses = [(h.previous_status, h.new_status, h.reason) for h in history]
        assert (None, "submitted", None) in statuses
        assert ("submitted", "in_progress", "Operator picked up ticket") in statuses
        assert ("in_progress", "delivered", "Data collection complete") in statuses
        assert ("delivered", "accepted", "Approved by client QA") in statuses
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_rejection_and_rework_workflow(db_session):
    client_user = await create_user(db_session, "client", name="Client User")
    operator_user = await create_user(db_session, "operator", name="Operator User")

    client = await client_for_session(db_session)
    try:
        client_tok = await access_token(client, client_user)
        op_tok = await access_token(client, operator_user)

        req = await create_request(
            db_session, client_user, status="delivered", episodes_requested=1
        )

        # Client rejects delivered request
        res_reject = await client.post(
            f"/api/v1/requests/{req.id}/status",
            json={"status": "rejected", "reason": "Missing metadata in episodes"},
            headers={"Authorization": f"Bearer {client_tok}"},
        )
        assert res_reject.status_code == 200
        assert res_reject.json()["status"] == "rejected"

        # Operator moves rejected -> in_progress
        res_rework = await client.post(
            f"/api/v1/requests/{req.id}/status",
            json={"status": "in_progress", "reason": "Fixing metadata"},
            headers={"Authorization": f"Bearer {op_tok}"},
        )
        assert res_rework.status_code == 200
        assert res_rework.json()["status"] == "in_progress"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_role_and_ownership_enforcement(db_session):
    client1 = await create_user(db_session, "client", name="Client One")
    client2 = await create_user(db_session, "client", name="Client Two")
    operator = await create_user(db_session, "operator", name="Operator User")

    client = await client_for_session(db_session)
    try:
        c1_tok = await access_token(client, client1)
        c2_tok = await access_token(client, client2)
        op_tok = await access_token(client, operator)

        req1 = await create_request(
            db_session, client1, status="delivered", episodes_requested=1
        )

        # Operator cannot accept delivered request (only client owner can) -> 403
        res_op_accept = await client.post(
            f"/api/v1/requests/{req1.id}/status",
            json={"status": "accepted"},
            headers={"Authorization": f"Bearer {op_tok}"},
        )
        assert res_op_accept.status_code == 403
        assert res_op_accept.json()["error"]["code"] == "FORBIDDEN"

        # Client cannot move submitted -> in_progress (only operator/admin can) -> 403
        req_sub = await create_request(db_session, client1, status="submitted")
        res_client_inprog = await client.post(
            f"/api/v1/requests/{req_sub.id}/status",
            json={"status": "in_progress"},
            headers={"Authorization": f"Bearer {c1_tok}"},
        )
        assert res_client_inprog.status_code == 403
        assert res_client_inprog.json()["error"]["code"] == "FORBIDDEN"

        # Client 2 trying to update Client 1's request -> 404 NOT_FOUND (IDOR avoidance)
        res_c2_other = await client.post(
            f"/api/v1/requests/{req1.id}/status",
            json={"status": "accepted"},
            headers={"Authorization": f"Bearer {c2_tok}"},
        )
        assert res_c2_other.status_code == 404
        assert res_c2_other.json()["error"]["code"] == "NOT_FOUND"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
