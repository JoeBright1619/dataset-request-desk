"""
Tests for error envelope shape and handling.

Verifies that both AppError and Pydantic validation errors produce
the documented error envelope structure.
"""

from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.main import app
from fastapi.testclient import TestClient
from pydantic import BaseModel

client = TestClient(app)


def test_app_error_basic_envelope():
    """Test that AppError produces the documented error envelope."""

    @app.get("/test-not-found")
    def test_not_found():
        raise NotFoundError("Test resource not found")

    response = client.get("/test-not-found")

    assert response.status_code == 404
    data = response.json()

    # Verify envelope structure per docs/API.md §0.4
    assert "error" in data
    error = data["error"]
    assert "code" in error
    assert "message" in error
    assert error["code"] == "NOT_FOUND"
    assert error["message"] == "Test resource not found"
    assert "field" not in error  # NotFoundError doesn't have a field


def test_app_error_with_field():
    """Test that AppError with field includes it in the envelope."""

    @app.get("/test-validation-with-field")
    def test_validation():
        raise ValidationError("Invalid input", field="username")

    response = client.get("/test-validation-with-field")

    assert response.status_code == 422
    data = response.json()

    assert "error" in data
    error = data["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Invalid input"
    assert error["field"] == "username"


def test_forbidden_error_envelope():
    """Test ForbiddenError produces correct envelope."""

    @app.get("/test-forbidden")
    def test_forbidden():
        raise ForbiddenError("Access denied")

    response = client.get("/test-forbidden")

    assert response.status_code == 403
    data = response.json()

    assert "error" in data
    error = data["error"]
    assert error["code"] == "FORBIDDEN"
    assert error["message"] == "Access denied"


def test_pydantic_validation_error_envelope():
    """Test that Pydantic validation errors match the error envelope."""

    class TestRequest(BaseModel):
        required_field: str
        number_field: int

    @app.post("/test-pydantic-validation")
    def test_pydantic(data: TestRequest):
        return {"received": data.model_dump()}

    # Send invalid data (wrong type)
    response = client.post(
        "/test-pydantic-validation",
        json={"required_field": "test", "number_field": "not_a_number"},
    )

    assert response.status_code == 422
    data = response.json()

    # Verify envelope structure
    assert "error" in data
    error = data["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Request validation failed"
    assert "field" in error  # Should identify the problematic field


def test_pydantic_missing_field_error():
    """Test Pydantic error for missing required field."""

    class TestRequest(BaseModel):
        required_field: str

    @app.post("/test-pydantic-missing")
    def test_missing(data: TestRequest):
        return {"received": data.model_dump()}

    # Send data without required field
    response = client.post("/test-pydantic-missing", json={})

    assert response.status_code == 422
    data = response.json()

    assert "error" in data
    error = data["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Request validation failed"
    assert "field" in error


def test_no_stack_traces_in_responses():
    """Test that stack traces never appear in error responses."""
    # AppError responses should never include stack traces
    response = client.get("/test-not-found")

    response_text = response.text

    # Ensure no stack trace keywords appear
    assert "Traceback" not in response_text
    assert "raise " not in response_text
    assert ".py" not in response_text or '".py"' in response_text


def test_exception_handler_registered():
    """Test that removing the exception handler breaks the envelope."""
    # This test verifies that our custom handler is actually in use
    # by checking that a known AppError produces the expected envelope

    @app.get("/test-handler-check")
    def test_handler():
        raise NotFoundError("Handler test")

    response = client.get("/test-handler-check")

    # If the handler is registered, we get our envelope
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"

    # If handler was NOT registered, FastAPI would return a different format
    # (typically with "detail" key instead of "error")
    assert "detail" not in data
