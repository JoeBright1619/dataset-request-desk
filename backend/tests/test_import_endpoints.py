"""HTTP and CLI coverage for episode CSV import endpoints."""

from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from app.cli.import_episodes import main as cli_import_main
from app.core.security import hash_password
from app.db.session import get_session
from app.main import app
from app.models.episode import Episode
from app.models.user import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

CSV_HEADER = (
    "episode_id,robot_id,task_name,recorded_at,duration_seconds,operator_name,quality"
)


async def client_for_session(db_session) -> AsyncClient:
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def create_user(db_session, role: str) -> User:
    user = User(
        email=f"import-{role}-{uuid4()}@example.com",
        password_hash=hash_password("correct-password"),
        name=f"Import {role.title()}",
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


@pytest.mark.asyncio
async def test_import_endpoint_happy_path(db_session):
    operator = await create_user(db_session, "operator")
    client = await client_for_session(db_session)
    try:
        token = await access_token(client, operator)
        csv_content = (
            f"{CSV_HEADER}\n"
            "EP-IMP-001,arm-01,pick_cups,2026-01-10T09:00:00Z,42.5,Ada,good\n"
            "EP-IMP-002,arm-02,pick_cups,2026-01-10T10:00:00Z,15.0,Bob,usable\n"
            "EP-IMP-003,arm-03,pick_cups,invalid-date,10.0,Cam,good\n"
        )
        files = {
            "file": (
                "episodes.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = await client.post(
            "/api/v1/episodes/import",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["imported"] == 2
        assert body["skipped_duplicates"] == 0
        assert body["invalid"] == 1
        assert len(body["errors"]) == 1
        assert body["errors"][0]["row"] == 4
        assert body["errors_truncated"] is False

        episodes = (
            (
                await db_session.execute(
                    select(Episode).where(
                        Episode.episode_id.in_(
                            ["EP-IMP-001", "EP-IMP-002", "EP-IMP-003"]
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(episodes) == 2
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_import_endpoint_role_restrictions(db_session):
    client_user = await create_user(db_session, "client")
    client = await client_for_session(db_session)
    try:
        csv_content = (
            f"{CSV_HEADER}\nEP-UNAUTH,arm-01,pick,2026-01-10T09:00:00Z,42.5,,good\n"
        )
        unauth_resp = await client.post(
            "/api/v1/episodes/import",
            files={
                "file": (
                    "episodes.csv",
                    BytesIO(csv_content.encode("utf-8")),
                    "text/csv",
                )
            },
        )
        assert unauth_resp.status_code == 401
        assert unauth_resp.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

        token = await access_token(client, client_user)
        denied_resp = await client.post(
            "/api/v1/episodes/import",
            files={
                "file": (
                    "episodes.csv",
                    BytesIO(csv_content.encode("utf-8")),
                    "text/csv",
                )
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert denied_resp.status_code == 403
        assert denied_resp.json()["error"]["code"] == "FORBIDDEN"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_import_endpoint_missing_file_field(db_session):
    operator = await create_user(db_session, "operator")
    client = await client_for_session(db_session)
    try:
        token = await access_token(client, operator)
        response = await client.post(
            "/api/v1/episodes/import",
            data={"wrong_field": "some_value"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_import_endpoint_corrupted_header(db_session):
    operator = await create_user(db_session, "operator")
    client = await client_for_session(db_session)
    try:
        token = await access_token(client, operator)
        invalid_csv = "bad_col1,bad_col2\n1,2\n"
        response = await client.post(
            "/api/v1/episodes/import",
            files={
                "file": (
                    "episodes.csv",
                    BytesIO(invalid_csv.encode("utf-8")),
                    "text/csv",
                )
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "IMPORT_ERROR"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_import_endpoint_file_too_large(db_session):
    operator = await create_user(db_session, "operator")
    client = await client_for_session(db_session)
    try:
        token = await access_token(client, operator)
        oversized = b"a" * (20 * 1024 * 1024 + 5)
        response = await client.post(
            "/api/v1/episodes/import",
            files={"file": ("large.csv", BytesIO(oversized), "text/csv")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "IMPORT_ERROR"
        assert "20MB" in response.json()["error"]["message"]
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cli_import_episodes_success_and_idempotency(tmp_path, db_session):
    csv_file = tmp_path / "test_episodes.csv"
    csv_file.write_text(
        f"{CSV_HEADER}\n"
        "EP-CLI-001,arm-01,pick_cups,2026-01-10T09:00:00Z,42.5,Ada,good\n"
        "EP-CLI-002,arm-02,pick_cups,2026-01-10T10:00:00Z,15.0,Bob,usable\n",
        encoding="utf-8",
    )

    class MockSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("app.cli.import_episodes.SessionFactory", MockSessionFactory()):
        code_1 = await cli_import_main([str(csv_file)])
        assert code_1 == 0

        # Idempotent second run
        code_2 = await cli_import_main([str(csv_file)])
        assert code_2 == 0


@pytest.mark.asyncio
async def test_cli_import_episodes_handles_errors(tmp_path):
    assert await cli_import_main([]) == 1
    assert await cli_import_main([str(tmp_path / "non_existent.csv")]) == 1
