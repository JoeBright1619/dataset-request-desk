"""HTTP endpoint tests for request creation, reading, and visibility scoping."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.core.security import hash_password
from app.db.session import get_session
from app.main import app
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
        email=f"req-{role}-{uuid4()}@example.com",
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


@pytest.mark.asyncio
async def test_only_clients_can_create_requests(db_session):
    client_user = await create_user(db_session, "client", name="Acme Client")
    operator_user = await create_user(db_session, "operator", name="Operator User")
    admin_user = await create_user(db_session, "admin", name="Admin User")

    client = await client_for_session(db_session)
    try:
        client_tok = await access_token(client, client_user)
        op_tok = await access_token(client, operator_user)
        admin_tok = await access_token(client, admin_user)

        deadline = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        payload = {
            "task_name": "pick_cups",
            "episodes_requested": 100,
            "deadline": deadline,
            "notes": "Urgent request",
        }

        # Operator forbidden
        op_res = await client.post(
            "/api/v1/requests",
            json=payload,
            headers={"Authorization": f"Bearer {op_tok}"},
        )
        assert op_res.status_code == 403
        assert op_res.json()["error"]["code"] == "FORBIDDEN"

        # Admin forbidden
        admin_res = await client.post(
            "/api/v1/requests",
            json=payload,
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert admin_res.status_code == 403
        assert admin_res.json()["error"]["code"] == "FORBIDDEN"

        # Client allowed
        client_res = await client.post(
            "/api/v1/requests",
            json=payload,
            headers={"Authorization": f"Bearer {client_tok}"},
        )
        assert client_res.status_code == 201
        body = client_res.json()
        assert body["task_name"] == "pick_cups"
        assert body["episodes_requested"] == 100
        assert body["episodes_assigned"] == 0
        assert body["status"] == "submitted"
        assert body["client_name"] == "Acme Client"
        assert body["client_id"] == str(client_user.id)

        # Verify status history logged in DB
        repo = RequestRepository(db_session)
        history = await repo.list_history(body["id"])
        assert len(history) == 1
        assert history[0].previous_status is None
        assert history[0].new_status == "submitted"
        assert history[0].changed_by == client_user.id
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_request_validation_error_on_past_deadline(db_session):
    client_user = await create_user(db_session, "client")
    client = await client_for_session(db_session)
    try:
        client_tok = await access_token(client, client_user)
        past_deadline = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        payload = {
            "task_name": "pick_cups",
            "episodes_requested": 100,
            "deadline": past_deadline,
        }

        res = await client.post(
            "/api/v1/requests",
            json=payload,
            headers={"Authorization": f"Bearer {client_tok}"},
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_request_visibility_scoping_and_404_not_found(db_session):
    client1 = await create_user(db_session, "client", name="Client One")
    client2 = await create_user(db_session, "client", name="Client Two")
    operator = await create_user(db_session, "operator", name="Operator User")

    client = await client_for_session(db_session)
    try:
        c1_tok = await access_token(client, client1)
        c2_tok = await access_token(client, client2)
        op_tok = await access_token(client, operator)

        deadline = (datetime.now(UTC) + timedelta(days=3)).isoformat()

        # Client 1 creates a request
        c1_res = await client.post(
            "/api/v1/requests",
            json={
                "task_name": "task_1",
                "episodes_requested": 10,
                "deadline": deadline,
            },
            headers={"Authorization": f"Bearer {c1_tok}"},
        )
        assert c1_res.status_code == 201
        req1_id = c1_res.json()["id"]

        # Client 2 creates a request
        c2_res = await client.post(
            "/api/v1/requests",
            json={
                "task_name": "task_2",
                "episodes_requested": 20,
                "deadline": deadline,
            },
            headers={"Authorization": f"Bearer {c2_tok}"},
        )
        assert c2_res.status_code == 201
        req2_id = c2_res.json()["id"]

        # Client 1 gets own request -> 200
        get_c1_own = await client.get(
            f"/api/v1/requests/{req1_id}",
            headers={"Authorization": f"Bearer {c1_tok}"},
        )
        assert get_c1_own.status_code == 200
        assert get_c1_own.json()["task_name"] == "task_1"

        # Client 1 attempts to get Client 2's request -> 404 NOT_FOUND (IDOR avoidance)
        get_c1_other = await client.get(
            f"/api/v1/requests/{req2_id}",
            headers={"Authorization": f"Bearer {c1_tok}"},
        )
        assert get_c1_other.status_code == 404
        assert get_c1_other.json()["error"]["code"] == "NOT_FOUND"

        # Operator gets both requests -> 200
        get_op_1 = await client.get(
            f"/api/v1/requests/{req1_id}",
            headers={"Authorization": f"Bearer {op_tok}"},
        )
        assert get_op_1.status_code == 200

        get_op_2 = await client.get(
            f"/api/v1/requests/{req2_id}",
            headers={"Authorization": f"Bearer {op_tok}"},
        )
        assert get_op_2.status_code == 200

        # Listing for Client 1 returns only Client 1's request
        c1_list = await client.get(
            "/api/v1/requests",
            headers={"Authorization": f"Bearer {c1_tok}"},
        )
        assert c1_list.status_code == 200
        c1_items = c1_list.json()["items"]
        assert len(c1_items) == 1
        assert c1_items[0]["id"] == req1_id

        # Listing for Operator returns both
        op_list = await client.get(
            "/api/v1/requests",
            headers={"Authorization": f"Bearer {op_tok}"},
        )
        assert op_list.status_code == 200
        op_items = op_list.json()["items"]
        assert len(op_items) >= 2
        op_item_ids = {item["id"] for item in op_items}
        assert req1_id in op_item_ids
        assert req2_id in op_item_ids
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
