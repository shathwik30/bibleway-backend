"""Tests for apps.common.exceptions — custom_exception_handler wrapping."""

from __future__ import annotations

from unittest.mock import MagicMock

from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from apps.common.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    custom_exception_handler,
)


def _make_context():
    """Return a minimal DRF exception-handler context dict."""
    view = MagicMock()
    view.__class__.__name__ = "TestView"
    return {"view": view, "request": MagicMock()}


# ---------------------------------------------------------------------------
# String detail
# ---------------------------------------------------------------------------


class TestStringDetail:
    def test_wraps_not_found(self):
        exc = NotFound(detail="Resource not found.")
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["message"] == "Resource not found."
        assert response.data["data"] is None

    def test_wraps_permission_denied(self):
        exc = PermissionDenied(detail="No access.")
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["message"] == "No access."

    def test_wraps_authentication_failed(self):
        exc = AuthenticationFailed(detail="Invalid token.")
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["message"] == "Invalid token."


# ---------------------------------------------------------------------------
# Dict-type detail (field validation errors)
# ---------------------------------------------------------------------------


class TestDictDetail:
    def test_dict_detail_extracts_first_value(self):
        exc = ValidationError(detail={"email": ["This field is required."]})
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["message"] == "This field is required."
        assert response.data["data"] is None

    def test_dict_detail_single_string(self):
        exc = ValidationError(detail={"name": "Too long."})
        response = custom_exception_handler(exc, _make_context())
        assert response.data["message"] == "Too long."


# ---------------------------------------------------------------------------
# List-type detail
# ---------------------------------------------------------------------------


class TestListDetail:
    def test_plain_list_detail_extracts_first(self):
        exc = ValidationError(detail=["First error.", "Second error."])
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["message"] == "First error."
        assert response.data["data"] is None

    def test_list_detail_extracts_first(self):
        """When ValidationError is given a list, DRF sets response.data to that list.

        DRF often wraps list errors under ``non_field_errors``. The handler must
        still normalize that response into the standard envelope.
        """
        exc = ValidationError(detail={"non_field_errors": ["First error.", "Second error."]})
        response = custom_exception_handler(exc, _make_context())
        assert response.data["message"] == "First error."

    def test_non_field_errors_empty_list_returns_fallback(self):
        """Dict with empty list value returns the fallback message."""
        exc = ValidationError(detail={"field": []})
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == 400
        assert response.data["message"] == "An error occurred."


# ---------------------------------------------------------------------------
# Custom API exceptions
# ---------------------------------------------------------------------------


class TestCustomExceptions:
    def test_not_found_error(self):
        exc = NotFoundError(detail="Item missing.")
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == 404
        assert response.data["message"] == "Item missing."

    def test_conflict_error(self):
        exc = ConflictError(detail="Duplicate.")
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == 409
        assert response.data["message"] == "Duplicate."

    def test_forbidden_error(self):
        exc = ForbiddenError(detail="Not allowed.")
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == 403
        assert response.data["message"] == "Not allowed."

    def test_bad_request_error(self):
        exc = BadRequestError(detail="Bad input.")
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == 400
        assert response.data["message"] == "Bad input."


# ---------------------------------------------------------------------------
# Unhandled exception (non-DRF)
# ---------------------------------------------------------------------------


class TestUnhandledException:
    def test_returns_500_with_generic_message(self):
        exc = RuntimeError("Something broke")
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["message"] == "An unexpected error occurred."
        assert response.data["data"] is None

    def test_value_error_returns_500(self):
        exc = ValueError("Bad value")
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == 500

    def test_does_not_leak_traceback(self):
        exc = Exception("secret-database-url")
        response = custom_exception_handler(exc, _make_context())
        assert "secret-database-url" not in response.data["message"]
