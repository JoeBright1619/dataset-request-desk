"""Refresh-token rotation and reuse-revocation tests."""

import pytest
from app.core.errors import AuthenticationRequiredError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.auth_service import AuthService, hash_refresh_token
from sqlalchemy import select


async def create_user(db_session) -> User:
    user = User(
        email="refresh-token-user@example.com",
        password_hash="not-used-by-this-test",
        name="Refresh Token User",
        role="operator",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_refresh_rotation_marks_old_token_used_and_issues_new_one(db_session):
    user = await create_user(db_session)
    service = AuthService(db_session)

    issued = await service.issue_tokens(user)
    refreshed = await service.refresh(issued.refresh_token)

    assert refreshed.refresh_token != issued.refresh_token
    old_token = (
        await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(issued.refresh_token)
            )
        )
    ).scalar_one()
    new_token = (
        await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(refreshed.refresh_token)
            )
        )
    ).scalar_one()
    assert old_token.used_at is not None
    assert old_token.family_id == new_token.family_id
    assert old_token.token_hash != issued.refresh_token
    assert new_token.used_at is None


@pytest.mark.asyncio
async def test_reusing_a_token_revokes_its_entire_family(db_session):
    user = await create_user(db_session)
    service = AuthService(db_session)

    issued = await service.issue_tokens(user)
    rotated = await service.refresh(issued.refresh_token)
    family_id = (
        await db_session.execute(
            select(RefreshToken.family_id).where(
                RefreshToken.token_hash == hash_refresh_token(rotated.refresh_token)
            )
        )
    ).scalar_one()

    with pytest.raises(AuthenticationRequiredError):
        await service.refresh(issued.refresh_token)

    tokens = (
        (
            await db_session.execute(
                select(RefreshToken).where(RefreshToken.family_id == family_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(tokens) == 2
    assert all(token.revoked_at is not None for token in tokens)

    with pytest.raises(AuthenticationRequiredError):
        await service.refresh(rotated.refresh_token)
