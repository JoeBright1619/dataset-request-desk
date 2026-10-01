"""Tests for password and JWT security primitives."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from app.core.config import settings
from app.core.security import (
    ACCESS_TOKEN_LIFETIME,
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    password = "a secure password"

    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("incorrect password", password_hash)


def test_access_token_decodes_with_expected_claims() -> None:
    user_id = uuid4()

    token = create_access_token(user_id, "operator")
    claims = decode_access_token(token)

    assert claims["sub"] == str(user_id)
    assert claims["role"] == "operator"
    assert isinstance(claims["iat"], int)
    assert isinstance(claims["exp"], int)
    assert claims["exp"] - claims["iat"] == int(ACCESS_TOKEN_LIFETIME.total_seconds())


def test_expired_access_token_is_rejected() -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "role": "client",
            "iat": now - timedelta(minutes=31),
            "exp": now - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )

    try:
        decode_access_token(token)
    except jwt.ExpiredSignatureError:
        pass
    else:
        raise AssertionError("Expired access token was accepted")
