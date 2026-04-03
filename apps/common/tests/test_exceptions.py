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


class TestDictDetail:
    def test_dict_detail_extracts_first_value(self):
        exc = ValidationError(detail={"email": ["This field is required."]})
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["message"] == "This field is required."
        assert response.data["data"] == {"email": ["This field is required."]}

    def test_dict_detail_single_string(self):
        exc = ValidationError(detail={"name": "Too long."})
        response = custom_exception_handler(exc, _make_context())
        assert response.data["message"] == "Too long."


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
        exc = ValidationError(
            detail={"non_field_errors": ["First error.", "Second error."]}
        )
        response = custom_exception_handler(exc, _make_context())
        assert response.data["message"] == "First error."

    def test_non_field_errors_empty_list_returns_fallback(self):
        """Dict with empty list value preserves field errors in data."""
        exc = ValidationError(detail={"field": []})
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == 400
        assert response.data["data"] == {"field": []}


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


class TestErrorEnvelopeFieldDetails:
    """Test that the error envelope preserves field-level details in data."""

    def test_validation_errors_preserve_field_details(self):
        """Multi-field validation errors should appear in data payload."""
        exc = ValidationError(
            detail={
                "email": ["This field is required."],
                "password": ["This field is required."],
            }
        )
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert response.data["message"] == "This field is required."

        assert response.data["data"] is not None
        assert "email" in response.data["data"]
        assert "password" in response.data["data"]

    def test_single_field_error_returns_field_errors_in_data(self):
        """A single-field validation error should include that field in data."""
        exc = ValidationError(detail={"username": ["Too short."]})
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["message"] == "Too short."
        assert response.data["data"] is not None
        assert "username" in response.data["data"]

    def test_non_validation_errors_return_data_null(self):
        """Non-validation errors (e.g. NotFound) should have data: null."""
        exc = NotFound(detail="Page not found.")
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["message"] == "Page not found."
        assert response.data["data"] is None

    def test_custom_bad_request_error_data_null(self):
        """Custom BadRequestError with string detail should have data: null."""
        exc = BadRequestError(detail="Invalid input.")
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["message"] == "Invalid input."
        assert response.data["data"] is None

    def test_permission_denied_data_null(self):
        """PermissionDenied should have data: null."""
        exc = PermissionDenied(detail="Not allowed.")
        response = custom_exception_handler(exc, _make_context())
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["data"] is None
