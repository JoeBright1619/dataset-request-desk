"""
Tests for configuration fail-fast behavior.

Verifies that missing required environment variables cause startup failure.
"""

import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_missing_database_url_raises():
    """Test that missing DATABASE_URL causes validation failure."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,  # Don't load from file
            jwt_secret="test",
            cors_origins="*",
            # database_url intentionally missing
        )

    errors = exc_info.value.errors()
    assert any("database_url" in str(error.get("loc", [])) for error in errors)


def test_missing_jwt_secret_raises():
    """Test that missing JWT_SECRET causes validation failure."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://test",
            cors_origins="*",
            # jwt_secret intentionally missing
        )

    errors = exc_info.value.errors()
    assert any("jwt_secret" in str(error.get("loc", [])) for error in errors)


def test_missing_cors_origins_raises():
    """Test that missing CORS_ORIGINS causes validation failure."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="postgresql://test",
            jwt_secret="test",
            # cors_origins intentionally missing
        )

    errors = exc_info.value.errors()
    assert any("cors_origins" in str(error.get("loc", [])) for error in errors)


def test_empty_database_url_raises():
    """Test that empty DATABASE_URL causes validation failure."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            database_url="",  # Empty string should fail min_length
            jwt_secret="test",
            cors_origins="*",
        )

    errors = exc_info.value.errors()
    assert len(errors) > 0


def test_valid_config_succeeds():
    """Test that valid configuration loads successfully."""
    settings = Settings(
        _env_file=None,
        database_url="postgresql://test:test@localhost/test",
        jwt_secret="test_secret_key",
        cors_origins="*",
    )

    assert settings.database_url == "postgresql://test:test@localhost/test"
    assert settings.jwt_secret == "test_secret_key"
    assert settings.cors_origins == "*"
