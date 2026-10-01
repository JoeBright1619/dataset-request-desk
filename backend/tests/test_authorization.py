"""Tests for service-layer object visibility rules."""

from uuid import uuid4

import pytest
from app.core.errors import NotFoundError
from app.models.user import User
from app.services.authorization import ensure_resource_visible


def user_with_role(role: str) -> User:
    return User(
        id=uuid4(),
        email=f"{role}-{uuid4()}@example.com",
        password_hash="unused",
        name=f"{role.title()} User",
        role=role,
    )


def test_client_can_view_their_own_resource():
    client = user_with_role("client")

    ensure_resource_visible(client.id, client)


def test_client_cannot_view_another_clients_resource():
    client = user_with_role("client")

    with pytest.raises(NotFoundError) as exc_info:
        ensure_resource_visible(uuid4(), client)

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.http_status == 404


@pytest.mark.parametrize("role", ["operator", "admin"])
def test_operational_users_can_view_any_resource(role: str):
    operational_user = user_with_role(role)

    ensure_resource_visible(uuid4(), operational_user)
