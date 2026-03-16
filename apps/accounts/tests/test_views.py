"""Tests for accounts app API views (all endpoints under /api/v1/accounts/)."""

from __future__ import annotations

import datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.test.utils import override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import (
    BlockRelationship,
    FollowRelationship,
    OTPToken,
    User,
)
from apps.accounts.services import OTPService
from conftest import (
    BlockRelationshipFactory,
    FollowRelationshipFactory,
    UserFactory,
)


# ────────────────────────────────────────────────────────────────
# URL helpers (avoid module-level reverse() which triggers debug_toolbar import)
# ────────────────────────────────────────────────────────────────

REGISTER_URL = "/api/v1/accounts/register/"
LOGIN_URL = "/api/v1/accounts/login/"
LOGOUT_URL = "/api/v1/accounts/logout/"
TOKEN_REFRESH_URL = "/api/v1/accounts/token/refresh/"
VERIFY_EMAIL_URL = "/api/v1/accounts/verify-email/"
RESEND_OTP_URL = "/api/v1/accounts/auth/resend-otp/"
PASSWORD_RESET_URL = "/api/v1/accounts/password-reset/"
PASSWORD_RESET_CONFIRM_URL = "/api/v1/accounts/password-reset/confirm/"
CHANGE_PASSWORD_URL = "/api/v1/accounts/change-password/"
PROFILE_URL = "/api/v1/accounts/profile/"
USER_SEARCH_URL = "/api/v1/accounts/users/search/"
FOLLOW_REQUESTS_URL = "/api/v1/accounts/follow-requests/"
BLOCKED_USERS_URL = "/api/v1/accounts/blocked-users/"
PRIVACY_URL = "/api/v1/accounts/privacy/"


def user_detail_url(user_id):
    return f"/api/v1/accounts/users/{user_id}/"


def follow_url(user_id):
    return f"/api/v1/accounts/users/{user_id}/follow/"


def followers_url(user_id):
    return f"/api/v1/accounts/users/{user_id}/followers/"


def following_url(user_id):
    return f"/api/v1/accounts/users/{user_id}/following/"


def follow_request_url(user_id):
    return f"/api/v1/accounts/follow-requests/{user_id}/"


def block_url(user_id):
    return f"/api/v1/accounts/users/{user_id}/block/"


VALID_REGISTRATION_DATA = {
    "email": "newuser@example.com",
    "password": "TestPass1!",
    "full_name": "New User",
    "date_of_birth": "1995-06-15",
    "gender": "male",
    "country": "US",
}


def _get_results(response):
    """Extract results list from a paginated or non-paginated response."""
    data = response.data
    # Paginated: {"message": "...", "data": {"count": N, "results": [...]}}
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        return data["data"].get("results", [])
    # Non-paginated: {"message": "...", "data": [...]}
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        return data["data"]
    return []


# ────────────────────────────────────────────────────────────────
# Disable per-view throttling for all tests in this module
# ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _disable_throttling():
    """Patch throttle classes to always allow requests in tests."""
    with patch(
        "apps.common.throttles.AuthRateThrottle.allow_request", return_value=True
    ), patch(
        "apps.common.throttles.OTPRateThrottle.allow_request", return_value=True
    ):
        yield


# ────────────────────────────────────────────────────────────────
# Registration
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRegistrationView:
    """POST /api/v1/accounts/register/"""

    @patch("apps.accounts.services.UserService._send_otp_email")
    def test_register_success(self, mock_send, api_client):
        response = api_client.post(REGISTER_URL, VALID_REGISTRATION_DATA, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"] == "Registration successful. Please verify your email."
        assert response.data["data"]["email"] == "newuser@example.com"
        assert User.objects.filter(email="newuser@example.com").exists()
        mock_send.assert_called_once()

    @patch("apps.accounts.services.UserService._send_otp_email")
    def test_register_creates_otp(self, mock_send, api_client):
        api_client.post(REGISTER_URL, VALID_REGISTRATION_DATA, format="json")
        user = User.objects.get(email="newuser@example.com")
        assert OTPToken.objects.filter(user=user, purpose="register").exists()

    @patch("apps.accounts.services.UserService._send_otp_email")
    def test_register_duplicate_email(self, mock_send, api_client):
        UserFactory(email="newuser@example.com")
        response = api_client.post(REGISTER_URL, VALID_REGISTRATION_DATA, format="json")
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_register_missing_fields(self, api_client):
        response = api_client.post(REGISTER_URL, {"email": "only@test.com"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_invalid_email(self, api_client):
        data = {**VALID_REGISTRATION_DATA, "email": "not-an-email"}
        response = api_client.post(REGISTER_URL, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_weak_password_no_uppercase(self, api_client):
        data = {**VALID_REGISTRATION_DATA, "password": "testpass1!"}
        response = api_client.post(REGISTER_URL, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_weak_password_no_lowercase(self, api_client):
        data = {**VALID_REGISTRATION_DATA, "password": "TESTPASS1!"}
        response = api_client.post(REGISTER_URL, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_weak_password_no_number(self, api_client):
        data = {**VALID_REGISTRATION_DATA, "password": "TestPass!"}
        response = api_client.post(REGISTER_URL, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_weak_password_no_special_char(self, api_client):
        data = {**VALID_REGISTRATION_DATA, "password": "TestPass1"}
        response = api_client.post(REGISTER_URL, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_password_too_short(self, api_client):
        data = {**VALID_REGISTRATION_DATA, "password": "Tp1!"}
        response = api_client.post(REGISTER_URL, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_invalid_gender(self, api_client):
        data = {**VALID_REGISTRATION_DATA, "gender": "unknown"}
        response = api_client.post(REGISTER_URL, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.accounts.services.UserService._send_otp_email")
    def test_register_email_lowered(self, mock_send, api_client):
        data = {**VALID_REGISTRATION_DATA, "email": "UPPER@EXAMPLE.COM"}
        response = api_client.post(REGISTER_URL, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        # The serializer lower()+strip()s the email
        assert User.objects.filter(email__icontains="upper@example.com").exists()


# ────────────────────────────────────────────────────────────────
# Login
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLoginView:
    """POST /api/v1/accounts/login/"""

    def test_login_success(self, api_client):
        user = UserFactory(is_email_verified=True)
        response = api_client.post(
            LOGIN_URL,
            {"email": user.email, "password": "TestPass1!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Login successful."
        assert "access" in response.data["data"]
        assert "refresh" in response.data["data"]
        assert "user_id" in response.data["data"]

    def test_login_invalid_password(self, api_client):
        user = UserFactory(is_email_verified=True)
        response = api_client.post(
            LOGIN_URL,
            {"email": user.email, "password": "WrongPassword1!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid email or password" in response.data["message"]

    def test_login_nonexistent_email(self, api_client):
        response = api_client.post(
            LOGIN_URL,
            {"email": "ghost@test.com", "password": "TestPass1!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_unverified_email(self, api_client):
        user = UserFactory(is_email_verified=False)
        response = api_client.post(
            LOGIN_URL,
            {"email": user.email, "password": "TestPass1!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "verify your email" in response.data["message"]

    def test_login_missing_fields(self, api_client):
        response = api_client.post(LOGIN_URL, {"email": "only@test.com"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_empty_body(self, api_client):
        response = api_client.post(LOGIN_URL, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ────────────────────────────────────────────────────────────────
# Logout
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLogoutView:
    """POST /api/v1/accounts/logout/"""

    def test_logout_success(self, auth_client, user):
        refresh = RefreshToken.for_user(user)
        response = auth_client.post(
            LOGOUT_URL, {"refresh": str(refresh)}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert "Logged out" in response.data["message"]

    def test_logout_missing_refresh_token(self, auth_client):
        response = auth_client.post(LOGOUT_URL, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Refresh token is required" in response.data["message"]

    def test_logout_invalid_refresh_token(self, auth_client):
        response = auth_client.post(
            LOGOUT_URL, {"refresh": "invalid-token"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout_requires_authentication(self, api_client):
        response = api_client.post(
            LOGOUT_URL, {"refresh": "some-token"}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_blacklists_token(self, auth_client, user):
        refresh = RefreshToken.for_user(user)
        auth_client.post(LOGOUT_URL, {"refresh": str(refresh)}, format="json")

        # Using the same token again should fail
        response = auth_client.post(
            LOGOUT_URL, {"refresh": str(refresh)}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ────────────────────────────────────────────────────────────────
# Token Refresh
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTokenRefreshView:
    """POST /api/v1/accounts/token/refresh/"""

    def test_refresh_success(self, api_client, user):
        refresh = RefreshToken.for_user(user)
        response = api_client.post(
            TOKEN_REFRESH_URL, {"refresh": str(refresh)}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data["data"]
        assert "refresh" in response.data["data"]
        assert response.data["message"] == "Token refreshed."

    def test_refresh_missing_token(self, api_client):
        response = api_client.post(TOKEN_REFRESH_URL, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Refresh token is required" in response.data["message"]

    def test_refresh_invalid_token(self, api_client):
        response = api_client.post(
            TOKEN_REFRESH_URL, {"refresh": "invalid-token"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ────────────────────────────────────────────────────────────────
# Email Verification
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEmailVerificationView:
    """POST /api/v1/accounts/verify-email/"""

    def test_verify_email_success(self, api_client):
        user = UserFactory(is_email_verified=False)
        otp_service = OTPService()
        code = otp_service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)

        response = api_client.post(
            VERIFY_EMAIL_URL,
            {"email": user.email, "otp_code": code},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "Email verified" in response.data["message"]

        user.refresh_from_db()
        assert user.is_email_verified is True

    def test_verify_email_invalid_otp(self, api_client):
        user = UserFactory(is_email_verified=False)
        otp_service = OTPService()
        otp_service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)

        response = api_client.post(
            VERIFY_EMAIL_URL,
            {"email": user.email, "otp_code": "000000"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_email_already_verified(self, api_client):
        user = UserFactory(is_email_verified=True)
        response = api_client.post(
            VERIFY_EMAIL_URL,
            {"email": user.email, "otp_code": "123456"},
            format="json",
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_verify_email_nonexistent_user(self, api_client):
        response = api_client.post(
            VERIFY_EMAIL_URL,
            {"email": "ghost@example.com", "otp_code": "123456"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_verify_email_invalid_otp_format(self, api_client):
        response = api_client.post(
            VERIFY_EMAIL_URL,
            {"email": "test@example.com", "otp_code": "abc"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_email_missing_fields(self, api_client):
        response = api_client.post(VERIFY_EMAIL_URL, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ────────────────────────────────────────────────────────────────
# Resend OTP
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestResendOTPView:
    """POST /api/v1/accounts/auth/resend-otp/"""

    @patch("apps.accounts.services.UserService._send_otp_email")
    def test_resend_otp_unverified_user(self, mock_send, api_client):
        user = UserFactory(is_email_verified=False)
        response = api_client.post(
            RESEND_OTP_URL, {"email": user.email}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_called_once()

    @patch("apps.accounts.services.UserService._send_otp_email")
    def test_resend_otp_verified_user_silent(self, mock_send, api_client):
        user = UserFactory(is_email_verified=True)
        response = api_client.post(
            RESEND_OTP_URL, {"email": user.email}, format="json"
        )
        # Should return 200 to prevent user enumeration
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_not_called()

    @patch("apps.accounts.services.UserService._send_otp_email")
    def test_resend_otp_nonexistent_email_silent(self, mock_send, api_client):
        response = api_client.post(
            RESEND_OTP_URL, {"email": "ghost@example.com"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_not_called()


# ────────────────────────────────────────────────────────────────
# Password Reset Request
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPasswordResetRequestView:
    """POST /api/v1/accounts/password-reset/"""

    @patch("apps.accounts.services.UserService._send_otp_email")
    def test_request_password_reset_success(self, mock_send, api_client):
        user = UserFactory(is_email_verified=True)
        response = api_client.post(
            PASSWORD_RESET_URL, {"email": user.email}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert "reset code has been sent" in response.data["message"]
        mock_send.assert_called_once()

    @patch("apps.accounts.services.UserService._send_otp_email")
    def test_request_password_reset_nonexistent_email(self, mock_send, api_client):
        response = api_client.post(
            PASSWORD_RESET_URL, {"email": "ghost@example.com"}, format="json"
        )
        # Should return 200 to prevent enumeration
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_not_called()

    def test_request_password_reset_invalid_email(self, api_client):
        response = api_client.post(
            PASSWORD_RESET_URL, {"email": "not-an-email"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ────────────────────────────────────────────────────────────────
# Password Reset Confirm
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPasswordResetConfirmView:
    """POST /api/v1/accounts/password-reset/confirm/"""

    def test_confirm_password_reset_success(self, api_client):
        user = UserFactory(is_email_verified=True)
        otp_service = OTPService()
        code = otp_service.create_otp(
            user=user, purpose=OTPToken.Purpose.PASSWORD_RESET
        )

        response = api_client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {
                "email": user.email,
                "otp_code": code,
                "new_password": "NewPass1!",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "Password reset successful" in response.data["message"]

        user.refresh_from_db()
        assert user.check_password("NewPass1!")

    def test_confirm_password_reset_invalid_otp(self, api_client):
        user = UserFactory(is_email_verified=True)
        otp_service = OTPService()
        otp_service.create_otp(user=user, purpose=OTPToken.Purpose.PASSWORD_RESET)

        response = api_client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {
                "email": user.email,
                "otp_code": "000000",
                "new_password": "NewPass1!",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_password_reset_weak_password(self, api_client):
        response = api_client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {
                "email": "test@example.com",
                "otp_code": "123456",
                "new_password": "weak",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_password_reset_nonexistent_user(self, api_client):
        response = api_client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {
                "email": "ghost@example.com",
                "otp_code": "123456",
                "new_password": "NewPass1!",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ────────────────────────────────────────────────────────────────
# Change Password
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestChangePasswordView:
    """POST /api/v1/accounts/change-password/"""

    def test_change_password_success(self, auth_client, user):
        response = auth_client.post(
            CHANGE_PASSWORD_URL,
            {"old_password": "TestPass1!", "new_password": "NewPass1!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "Password changed" in response.data["message"]

        user.refresh_from_db()
        assert user.check_password("NewPass1!")

    def test_change_password_wrong_old(self, auth_client):
        response = auth_client.post(
            CHANGE_PASSWORD_URL,
            {"old_password": "WrongPass1!", "new_password": "NewPass1!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Current password is incorrect" in response.data["message"]

    def test_change_password_weak_new(self, auth_client):
        response = auth_client.post(
            CHANGE_PASSWORD_URL,
            {"old_password": "TestPass1!", "new_password": "weak"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_password_unauthenticated(self, api_client):
        response = api_client.post(
            CHANGE_PASSWORD_URL,
            {"old_password": "TestPass1!", "new_password": "NewPass1!"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_change_password_missing_fields(self, auth_client):
        response = auth_client.post(CHANGE_PASSWORD_URL, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ────────────────────────────────────────────────────────────────
# Profile (GET/PUT/PATCH)
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestProfileView:
    """GET/PUT/PATCH /api/v1/accounts/profile/"""

    def test_get_profile(self, auth_client, user):
        response = auth_client.get(PROFILE_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["id"] == str(user.id)
        assert data["email"] == user.email
        assert data["full_name"] == user.full_name

    def test_get_profile_unauthenticated(self, api_client):
        response = api_client.get(PROFILE_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_profile_has_counts(self, auth_client):
        response = auth_client.get(PROFILE_URL)
        data = response.data["data"]
        assert "follower_count" in data
        assert "following_count" in data
        assert "post_count" in data
        assert "prayer_count" in data

    def test_patch_profile_name(self, auth_client, user):
        response = auth_client.patch(
            PROFILE_URL, {"full_name": "Updated Name"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["full_name"] == "Updated Name"
        assert "Profile updated" in response.data["message"]

    def test_patch_profile_bio(self, auth_client):
        response = auth_client.patch(
            PROFILE_URL, {"bio": "Hello world"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["bio"] == "Hello world"

    def test_patch_profile_multiple_fields(self, auth_client):
        response = auth_client.patch(
            PROFILE_URL,
            {"full_name": "Multi Update", "country": "UK", "bio": "New bio"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["full_name"] == "Multi Update"
        assert data["country"] == "UK"
        assert data["bio"] == "New bio"

    def test_put_profile(self, auth_client):
        response = auth_client.put(
            PROFILE_URL,
            {
                "full_name": "Full Update",
                "bio": "Full bio",
                "preferred_language": "es",
                "country": "ES",
                "phone_number": "+34111222333",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["full_name"] == "Full Update"

    def test_patch_profile_email_immutable(self, auth_client, user):
        original_email = user.email
        response = auth_client.patch(
            PROFILE_URL,
            {"email": "newemail@test.com", "full_name": "Valid Update"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        # Email should not change
        assert response.data["data"]["email"] == original_email

    def test_patch_profile_no_valid_fields(self, auth_client):
        response = auth_client.patch(
            PROFILE_URL, {"email": "newemail@test.com"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ────────────────────────────────────────────────────────────────
# User Detail (viewing another user's profile)
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserDetailView:
    """GET /api/v1/accounts/users/<user_id>/"""

    def test_view_other_user_profile(self, auth_client, user2):
        response = auth_client.get(user_detail_url(user2.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(user2.id)

    def test_view_nonexistent_user(self, auth_client):
        response = auth_client.get(user_detail_url(uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_view_blocked_user_denied(self, auth_client, user, user2):
        BlockRelationshipFactory(blocker=user2, blocked=user)
        response = auth_client.get(user_detail_url(user2.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_view_user_you_blocked_denied(self, auth_client, user, user2):
        BlockRelationshipFactory(blocker=user, blocked=user2)
        response = auth_client.get(user_detail_url(user2.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_view_unauthenticated(self, api_client, user):
        response = api_client.get(user_detail_url(user.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ────────────────────────────────────────────────────────────────
# User Search
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserSearchView:
    """GET /api/v1/accounts/users/search/?q=&country="""

    def test_search_by_name(self, auth_client):
        UserFactory(full_name="Alice Wonder", is_email_verified=True)
        UserFactory(full_name="Bob Builder", is_email_verified=True)

        response = auth_client.get(USER_SEARCH_URL, {"q": "Alice"})
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        assert len(results) == 1

    def test_search_by_country(self, auth_client):
        UserFactory(full_name="US Person", country="US", is_email_verified=True)
        UserFactory(full_name="UK Person", country="UK", is_email_verified=True)

        response = auth_client.get(USER_SEARCH_URL, {"q": "", "country": "US"})
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        # May include the auth user if they are from US
        us_results = [r for r in results if r.get("full_name") == "US Person"]
        assert len(us_results) == 1

    def test_search_case_insensitive(self, auth_client):
        UserFactory(full_name="Alice Wonder", is_email_verified=True)
        response = auth_client.get(USER_SEARCH_URL, {"q": "alice"})
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        assert len(results) == 1

    def test_search_excludes_unverified(self, auth_client):
        UserFactory(full_name="Unverified Person", is_email_verified=False)
        response = auth_client.get(USER_SEARCH_URL, {"q": "Unverified"})
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        assert len(results) == 0

    def test_search_empty_query(self, auth_client):
        """Empty query returns all verified users."""
        response = auth_client.get(USER_SEARCH_URL, {"q": ""})
        assert response.status_code == status.HTTP_200_OK

    def test_search_unauthenticated(self, api_client):
        response = api_client.get(USER_SEARCH_URL, {"q": "test"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_search_no_results(self, auth_client):
        response = auth_client.get(USER_SEARCH_URL, {"q": "ZZZZZZZZZZZ"})
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        assert len(results) == 0


# ────────────────────────────────────────────────────────────────
# Follow / Unfollow
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFollowView:
    """POST/DELETE /api/v1/accounts/users/<user_id>/follow/"""

    def test_follow_public_user(self, auth_client, user2):
        response = auth_client.post(follow_url(user2.id))
        assert response.status_code == status.HTTP_201_CREATED
        assert "Followed successfully" in response.data["message"]
        assert response.data["data"]["status"] == "accepted"

    def test_follow_private_user_pending(self, auth_client):
        private_user = UserFactory(account_visibility="private")
        response = auth_client.post(follow_url(private_user.id))
        assert response.status_code == status.HTTP_201_CREATED
        assert "Follow request sent" in response.data["message"]
        assert response.data["data"]["status"] == "pending"

    def test_follow_self_rejected(self, auth_client, user):
        response = auth_client.post(follow_url(user.id))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot follow yourself" in response.data["message"]

    def test_double_follow_conflict(self, auth_client, user, user2):
        auth_client.post(follow_url(user2.id))
        response = auth_client.post(follow_url(user2.id))
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_follow_nonexistent_user(self, auth_client):
        response = auth_client.post(follow_url(uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_follow_blocked_user_forbidden(self, auth_client, user, user2):
        BlockRelationshipFactory(blocker=user2, blocked=user)
        response = auth_client.post(follow_url(user2.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unfollow_success(self, auth_client, user, user2):
        FollowRelationshipFactory(follower=user, following=user2, status="accepted")
        response = auth_client.delete(follow_url(user2.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not FollowRelationship.objects.filter(
            follower=user, following=user2
        ).exists()

    def test_unfollow_not_following(self, auth_client, user2):
        response = auth_client.delete(follow_url(user2.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_follow_unauthenticated(self, api_client, user):
        response = api_client.post(follow_url(user.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ────────────────────────────────────────────────────────────────
# Follow Requests (Accept / Reject)
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFollowRequestView:
    """POST/DELETE /api/v1/accounts/follow-requests/<user_id>/"""

    def test_accept_follow_request(self, auth_client, user, user2):
        FollowRelationshipFactory(follower=user2, following=user, status="pending")

        response = auth_client.post(follow_request_url(user2.id))
        assert response.status_code == status.HTTP_200_OK
        assert "Follow request accepted" in response.data["message"]
        assert response.data["data"]["status"] == "accepted"

    def test_accept_nonexistent_request(self, auth_client):
        response = auth_client.post(follow_request_url(uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_reject_follow_request(self, auth_client, user, user2):
        FollowRelationshipFactory(follower=user2, following=user, status="pending")

        response = auth_client.delete(follow_request_url(user2.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not FollowRelationship.objects.filter(
            follower=user2, following=user
        ).exists()

    def test_reject_nonexistent_request(self, auth_client):
        response = auth_client.delete(follow_request_url(uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ────────────────────────────────────────────────────────────────
# Pending Follow Requests List
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPendingFollowRequestsListView:
    """GET /api/v1/accounts/follow-requests/"""

    def test_list_pending_requests(self, auth_client, user):
        requester1 = UserFactory()
        requester2 = UserFactory()
        FollowRelationshipFactory(follower=requester1, following=user, status="pending")
        FollowRelationshipFactory(follower=requester2, following=user, status="pending")
        # Accepted should not appear
        FollowRelationshipFactory(
            follower=UserFactory(), following=user, status="accepted"
        )

        response = auth_client.get(FOLLOW_REQUESTS_URL)
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        assert len(results) == 2

    def test_list_pending_requests_empty(self, auth_client):
        response = auth_client.get(FOLLOW_REQUESTS_URL)
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        assert len(results) == 0

    def test_list_pending_requests_unauthenticated(self, api_client):
        response = api_client.get(FOLLOW_REQUESTS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ────────────────────────────────────────────────────────────────
# Followers List
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFollowersListView:
    """GET /api/v1/accounts/users/<user_id>/followers/"""

    def test_list_followers(self, auth_client, user):
        follower1 = UserFactory()
        follower2 = UserFactory()
        FollowRelationshipFactory(follower=follower1, following=user, status="accepted")
        FollowRelationshipFactory(follower=follower2, following=user, status="accepted")
        # Pending should not appear
        FollowRelationshipFactory(
            follower=UserFactory(), following=user, status="pending"
        )

        response = auth_client.get(followers_url(user.id))
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        assert len(results) == 2

    def test_list_own_followers_even_with_hidden_list(self, auth_client, user):
        """User can see their own followers even if hide_followers_list is True."""
        user.hide_followers_list = True
        user.save(update_fields=["hide_followers_list"])
        FollowRelationshipFactory(
            follower=UserFactory(), following=user, status="accepted"
        )

        response = auth_client.get(followers_url(user.id))
        assert response.status_code == status.HTTP_200_OK

    def test_list_other_user_hidden_followers_forbidden(self, auth_client, user2):
        user2.hide_followers_list = True
        user2.save(update_fields=["hide_followers_list"])

        response = auth_client.get(followers_url(user2.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_other_user_public_followers(self, auth_client, user2):
        follower = UserFactory()
        FollowRelationshipFactory(
            follower=follower, following=user2, status="accepted"
        )

        response = auth_client.get(followers_url(user2.id))
        assert response.status_code == status.HTTP_200_OK


# ────────────────────────────────────────────────────────────────
# Following List
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFollowingListView:
    """GET /api/v1/accounts/users/<user_id>/following/"""

    def test_list_following(self, auth_client, user):
        target1 = UserFactory()
        target2 = UserFactory()
        FollowRelationshipFactory(follower=user, following=target1, status="accepted")
        FollowRelationshipFactory(follower=user, following=target2, status="accepted")
        # Pending should not appear
        FollowRelationshipFactory(
            follower=user, following=UserFactory(), status="pending"
        )

        response = auth_client.get(following_url(user.id))
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        assert len(results) == 2

    def test_list_following_other_user(self, auth_client, user2):
        target = UserFactory()
        FollowRelationshipFactory(
            follower=user2, following=target, status="accepted"
        )

        response = auth_client.get(following_url(user2.id))
        assert response.status_code == status.HTTP_200_OK


# ────────────────────────────────────────────────────────────────
# Block / Unblock
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBlockView:
    """POST/DELETE /api/v1/accounts/users/<user_id>/block/"""

    def test_block_user_success(self, auth_client, user, user2):
        response = auth_client.post(block_url(user2.id))
        assert response.status_code == status.HTTP_201_CREATED
        assert "User blocked" in response.data["message"]
        assert BlockRelationship.objects.filter(
            blocker=user, blocked=user2
        ).exists()

    def test_block_self_rejected(self, auth_client, user):
        response = auth_client.post(block_url(user.id))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot block yourself" in response.data["message"]

    def test_double_block_conflict(self, auth_client, user, user2):
        auth_client.post(block_url(user2.id))
        response = auth_client.post(block_url(user2.id))
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_block_nonexistent_user(self, auth_client):
        response = auth_client.post(block_url(uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_block_removes_follow_relationships(self, auth_client, user, user2):
        FollowRelationshipFactory(follower=user, following=user2, status="accepted")
        FollowRelationshipFactory(follower=user2, following=user, status="accepted")

        auth_client.post(block_url(user2.id))

        assert not FollowRelationship.objects.filter(
            follower=user, following=user2
        ).exists()
        assert not FollowRelationship.objects.filter(
            follower=user2, following=user
        ).exists()

    def test_unblock_success(self, auth_client, user, user2):
        BlockRelationshipFactory(blocker=user, blocked=user2)
        response = auth_client.delete(block_url(user2.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not BlockRelationship.objects.filter(
            blocker=user, blocked=user2
        ).exists()

    def test_unblock_not_blocked(self, auth_client, user2):
        response = auth_client.delete(block_url(user2.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_block_unauthenticated(self, api_client, user):
        response = api_client.post(block_url(user.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ────────────────────────────────────────────────────────────────
# Blocked Users List
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBlockedUsersListView:
    """GET /api/v1/accounts/blocked-users/"""

    def test_list_blocked_users(self, auth_client, user):
        target1 = UserFactory()
        target2 = UserFactory()
        BlockRelationshipFactory(blocker=user, blocked=target1)
        BlockRelationshipFactory(blocker=user, blocked=target2)

        response = auth_client.get(BLOCKED_USERS_URL)
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        assert len(results) == 2

    def test_list_blocked_users_empty(self, auth_client):
        response = auth_client.get(BLOCKED_USERS_URL)
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        assert len(results) == 0

    def test_list_blocked_users_does_not_include_blocked_by(self, auth_client, user):
        """Only users I blocked, not users who blocked me."""
        other = UserFactory()
        BlockRelationshipFactory(blocker=other, blocked=user)

        response = auth_client.get(BLOCKED_USERS_URL)
        results = _get_results(response)
        assert len(results) == 0

    def test_list_blocked_users_unauthenticated(self, api_client):
        response = api_client.get(BLOCKED_USERS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ────────────────────────────────────────────────────────────────
# Privacy Settings
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPrivacySettingsView:
    """GET/PUT /api/v1/accounts/privacy/"""

    def test_get_privacy_settings(self, auth_client, user):
        response = auth_client.get(PRIVACY_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["account_visibility"] == "public"
        assert data["hide_followers_list"] is False

    def test_update_privacy_to_private(self, auth_client, user):
        response = auth_client.put(
            PRIVACY_URL,
            {"account_visibility": "private", "hide_followers_list": True},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["account_visibility"] == "private"
        assert response.data["data"]["hide_followers_list"] is True
        assert "Privacy settings updated" in response.data["message"]

        user.refresh_from_db()
        assert user.account_visibility == "private"
        assert user.hide_followers_list is True

    def test_update_only_visibility(self, auth_client, user):
        response = auth_client.put(
            PRIVACY_URL, {"account_visibility": "private"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["account_visibility"] == "private"

    def test_update_only_hide_followers(self, auth_client, user):
        response = auth_client.put(
            PRIVACY_URL, {"hide_followers_list": True}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["hide_followers_list"] is True

    def test_update_back_to_public(self, auth_client, user):
        user.account_visibility = "private"
        user.save(update_fields=["account_visibility"])

        response = auth_client.put(
            PRIVACY_URL, {"account_visibility": "public"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["account_visibility"] == "public"

    def test_invalid_visibility_value(self, auth_client):
        response = auth_client.put(
            PRIVACY_URL, {"account_visibility": "invisible"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_privacy_unauthenticated(self, api_client):
        response = api_client.get(PRIVACY_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ────────────────────────────────────────────────────────────────
# Response envelope format
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestResponseEnvelope:
    """Verify that all responses follow the {message, data} envelope format."""

    def test_success_response_has_envelope(self, auth_client):
        response = auth_client.get(PROFILE_URL)
        assert "message" in response.data
        assert "data" in response.data

    @patch("apps.accounts.services.UserService._send_otp_email")
    def test_created_response_has_envelope(self, mock_send, api_client):
        response = api_client.post(REGISTER_URL, VALID_REGISTRATION_DATA, format="json")
        assert "message" in response.data
        assert "data" in response.data

    def test_error_response_has_envelope(self, api_client):
        response = api_client.post(LOGIN_URL, {}, format="json")
        assert "message" in response.data

    def test_no_content_response_has_no_body(self, auth_client, user, user2):
        FollowRelationshipFactory(follower=user, following=user2, status="accepted")
        response = auth_client.delete(follow_url(user2.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.data is None


# ────────────────────────────────────────────────────────────────
# Cross-feature integration tests
# ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCrossFeatureIntegration:
    """Integration tests spanning multiple features."""

    @patch("apps.accounts.services.UserService._send_otp_email")
    def test_full_registration_and_verification_flow(self, mock_send, api_client):
        """Register -> get OTP -> verify email -> login."""
        # 1. Register
        reg_resp = api_client.post(
            REGISTER_URL, VALID_REGISTRATION_DATA, format="json"
        )
        assert reg_resp.status_code == status.HTTP_201_CREATED

        # 2. Get the OTP from DB
        user = User.objects.get(email="newuser@example.com")
        otp_token = OTPToken.objects.filter(
            user=user, purpose="register", used=False
        ).first()
        assert otp_token is not None

        # We need the plain code - create a new one we know
        otp_service = OTPService()
        code = otp_service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)

        # 3. Verify email
        verify_resp = api_client.post(
            VERIFY_EMAIL_URL,
            {"email": user.email, "otp_code": code},
            format="json",
        )
        assert verify_resp.status_code == status.HTTP_200_OK

        # 4. Login
        login_resp = api_client.post(
            LOGIN_URL,
            {"email": user.email, "password": "TestPass1!"},
            format="json",
        )
        assert login_resp.status_code == status.HTTP_200_OK
        assert "access" in login_resp.data["data"]

    def test_follow_then_block_removes_relationship(self, auth_client, user, user2):
        """Following a user then blocking them should remove the follow."""
        auth_client.post(follow_url(user2.id))
        assert FollowRelationship.objects.filter(
            follower=user, following=user2
        ).exists()

        auth_client.post(block_url(user2.id))

        assert not FollowRelationship.objects.filter(
            follower=user, following=user2
        ).exists()

    def test_blocked_user_cannot_follow(self, auth_client, user, user2):
        """After being blocked, user cannot follow the blocker."""
        BlockRelationshipFactory(blocker=user2, blocked=user)
        response = auth_client.post(follow_url(user2.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_password_reset_then_login_with_new_password(self, api_client):
        """Request password reset -> verify OTP -> login with new password."""
        user = UserFactory(is_email_verified=True)
        otp_service = OTPService()
        code = otp_service.create_otp(
            user=user, purpose=OTPToken.Purpose.PASSWORD_RESET
        )

        api_client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {
                "email": user.email,
                "otp_code": code,
                "new_password": "BrandNew1!",
            },
            format="json",
        )

        response = api_client.post(
            LOGIN_URL,
            {"email": user.email, "password": "BrandNew1!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_private_account_follow_accept_flow(self, auth_client, user):
        """Follow private user -> pending -> accept -> appears in followers."""
        private_user = UserFactory(account_visibility="private")

        # Follow creates pending request
        resp = auth_client.post(follow_url(private_user.id))
        assert resp.data["data"]["status"] == "pending"

        # Accept from private user's side
        private_client = APIClient()
        refresh = RefreshToken.for_user(private_user)
        private_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}"
        )
        accept_resp = private_client.post(follow_request_url(user.id))
        assert accept_resp.data["data"]["status"] == "accepted"

        # Verify user is now in followers list
        followers_resp = auth_client.get(followers_url(private_user.id))
        results = _get_results(followers_resp)
        follower_ids = [r["follower"]["id"] for r in results]
        assert str(user.id) in follower_ids
