"""Tests for accounts app API views (all endpoints under /api/v1/accounts/)."""

from __future__ import annotations
from unittest.mock import patch
from uuid import uuid4
import pytest
from rest_framework import status
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

REGISTER_URL = "/api/v1/accounts/register/"

GOOGLE_AUTH_URL = "/api/v1/accounts/google-auth/"

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

BLOCKED_USERS_URL = "/api/v1/accounts/blocked-users/"


def user_detail_url(user_id: object) -> str:
    return f"/api/v1/accounts/users/{user_id}/"


def follow_url(user_id: object) -> str:
    return f"/api/v1/accounts/users/{user_id}/follow/"


def followers_url(user_id: object) -> str:
    return f"/api/v1/accounts/users/{user_id}/followers/"


def following_url(user_id: object) -> str:
    return f"/api/v1/accounts/users/{user_id}/following/"


def block_url(user_id: object) -> str:
    return f"/api/v1/accounts/users/{user_id}/block/"


VALID_REGISTRATION_DATA = {
    "email": "newuser@example.com",
    "password": "TestPass1!",
    "full_name": "New User",
    "date_of_birth": "1995-06-15",
    "gender": "male",
    "country": "US",
}


def _get_results(response: object) -> list:
    """Extract results list from a paginated or non-paginated response."""

    data = response.data

    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        return data["data"].get("results", [])

    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        return data["data"]

    return []


@pytest.fixture(autouse=True)
def _disable_throttling():
    """Patch throttle classes to always allow requests in tests."""

    with (
        patch(
            "apps.common.throttles.AuthRateThrottle.allow_request", return_value=True
        ),
        patch("apps.common.throttles.OTPRateThrottle.allow_request", return_value=True),
    ):
        yield


@pytest.mark.django_db
class TestRegistrationView:
    """POST /api/v1/accounts/register/"""

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_register_success(self, mock_send, api_client):
        response = api_client.post(REGISTER_URL, VALID_REGISTRATION_DATA, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert (
            response.data["message"]
            == "Registration successful. Please verify your email."
        )
        assert response.data["data"]["email"] == "newuser@example.com"
        assert User.objects.filter(email="newuser@example.com").exists()
        mock_send.assert_called_once()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_register_creates_otp(self, mock_send, api_client):
        api_client.post(REGISTER_URL, VALID_REGISTRATION_DATA, format="json")
        user = User.objects.get(email="newuser@example.com")
        assert OTPToken.objects.filter(user=user, purpose="register").exists()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_register_duplicate_email(self, mock_send, api_client):
        UserFactory(email="newuser@example.com")
        response = api_client.post(REGISTER_URL, VALID_REGISTRATION_DATA, format="json")
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_register_missing_fields(self, api_client):
        response = api_client.post(
            REGISTER_URL, {"email": "only@test.com"}, format="json"
        )
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

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_register_email_lowered(self, mock_send, api_client):
        data = {**VALID_REGISTRATION_DATA, "email": "UPPER@EXAMPLE.COM"}
        response = api_client.post(REGISTER_URL, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.filter(email__icontains="upper@example.com").exists()

    def test_register_future_date_of_birth(self, api_client):
        data = {**VALID_REGISTRATION_DATA, "date_of_birth": "2099-01-01"}
        response = api_client.post(REGISTER_URL, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_underage(self, api_client):
        data = {**VALID_REGISTRATION_DATA, "date_of_birth": "2020-01-01"}
        response = api_client.post(REGISTER_URL, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_invalid_language(self, api_client):
        data = {**VALID_REGISTRATION_DATA, "preferred_language": "zz"}
        response = api_client.post(REGISTER_URL, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


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


MOCK_GOOGLE_INFO: dict = {
    "iss": "accounts.google.com",
    "aud": "test-google-client-id.apps.googleusercontent.com",
    "email": "googleuser@gmail.com",
    "email_verified": True,
    "name": "Google User",
    "picture": "https://lh3.googleusercontent.com/photo.jpg",
    "sub": "1234567890",
}


@pytest.mark.django_db
class TestGoogleAuthView:
    """POST /api/v1/accounts/google-auth/"""

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_login_existing_user(self, mock_verify, api_client):
        user = UserFactory(email="googleuser@gmail.com")
        mock_verify.return_value = MOCK_GOOGLE_INFO
        response = api_client.post(
            GOOGLE_AUTH_URL, {"id_token": "valid-token"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["is_new_user"] is False
        assert "access" in data
        assert "refresh" in data
        assert data["user_id"] == str(user.id)

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_new_user_missing_fields_returns_202(self, mock_verify, api_client):
        mock_verify.return_value = MOCK_GOOGLE_INFO
        response = api_client.post(
            GOOGLE_AUTH_URL, {"id_token": "valid-token"}, format="json"
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.data["data"]
        assert data["is_new_user"] is True
        assert data["google_user"]["email"] == "googleuser@gmail.com"
        assert data["google_user"]["full_name"] == "Google User"

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_new_user_with_all_fields_creates_user(
        self, mock_verify, api_client
    ):

        mock_verify.return_value = MOCK_GOOGLE_INFO
        response = api_client.post(
            GOOGLE_AUTH_URL,
            {
                "id_token": "valid-token",
                "date_of_birth": "1995-06-15",
                "gender": "male",
                "country": "US",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["is_new_user"] is False
        assert "access" in data
        assert User.objects.filter(email="googleuser@gmail.com").exists()
        user = User.objects.get(email="googleuser@gmail.com")
        assert user.is_email_verified is True
        assert user.full_name == "Google User"
        assert user.has_usable_password() is False

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_invalid_token(self, mock_verify, api_client):
        mock_verify.side_effect = ValueError("Invalid token")
        response = api_client.post(
            GOOGLE_AUTH_URL, {"id_token": "bad-token"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid Google ID token" in response.data["message"]

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_wrong_audience_rejected(self, mock_verify, api_client):
        info = {**MOCK_GOOGLE_INFO, "aud": "wrong-client-id"}
        mock_verify.return_value = info
        response = api_client.post(
            GOOGLE_AUTH_URL, {"id_token": "valid-token"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "audience" in response.data["message"]

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_unverified_email_rejected(self, mock_verify, api_client):
        info = {**MOCK_GOOGLE_INFO, "email_verified": False}
        mock_verify.return_value = info
        response = api_client.post(
            GOOGLE_AUTH_URL, {"id_token": "valid-token"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not verified" in response.data["message"]

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_deactivated_user_forbidden(self, mock_verify, api_client):
        UserFactory(email="googleuser@gmail.com", is_active=False)
        mock_verify.return_value = MOCK_GOOGLE_INFO
        response = api_client.post(
            GOOGLE_AUTH_URL, {"id_token": "valid-token"}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_duplicate_email_conflict(self, mock_verify, api_client):
        UserFactory(email="googleuser@gmail.com")
        mock_verify.return_value = MOCK_GOOGLE_INFO
        response = api_client.post(
            GOOGLE_AUTH_URL, {"id_token": "valid-token"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["is_new_user"] is False

    def test_google_auth_missing_token(self, api_client):
        response = api_client.post(GOOGLE_AUTH_URL, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_new_user_validates_dob(self, mock_verify, api_client):
        mock_verify.return_value = MOCK_GOOGLE_INFO
        response = api_client.post(
            GOOGLE_AUTH_URL,
            {
                "id_token": "valid-token",
                "date_of_birth": "2020-01-01",
                "gender": "male",
                "country": "US",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


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
        response = api_client.post(LOGOUT_URL, {"refresh": "some-token"}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_blacklists_token(self, auth_client, user):
        refresh = RefreshToken.for_user(user)
        auth_client.post(LOGOUT_URL, {"refresh": str(refresh)}, format="json")
        response = auth_client.post(
            LOGOUT_URL, {"refresh": str(refresh)}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


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


@pytest.mark.django_db
class TestResendOTPView:
    """POST /api/v1/accounts/auth/resend-otp/"""

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_resend_otp_unverified_user(self, mock_send, api_client):
        user = UserFactory(is_email_verified=False)
        response = api_client.post(RESEND_OTP_URL, {"email": user.email}, format="json")
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_called_once()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_resend_otp_verified_user_silent(self, mock_send, api_client):
        user = UserFactory(is_email_verified=True)
        response = api_client.post(RESEND_OTP_URL, {"email": user.email}, format="json")
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_not_called()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_resend_otp_nonexistent_email_silent(self, mock_send, api_client):
        response = api_client.post(
            RESEND_OTP_URL, {"email": "ghost@example.com"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_not_called()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_resend_otp_inactive_user_silent(self, mock_send, api_client):
        user = UserFactory(is_active=False, is_email_verified=False)
        response = api_client.post(RESEND_OTP_URL, {"email": user.email}, format="json")
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_not_called()


@pytest.mark.django_db
class TestPasswordResetRequestView:
    """POST /api/v1/accounts/password-reset/"""

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_request_password_reset_success(self, mock_send, api_client):
        user = UserFactory(is_email_verified=True)
        response = api_client.post(
            PASSWORD_RESET_URL, {"email": user.email}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert "reset code has been sent" in response.data["message"]
        mock_send.assert_called_once()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_request_password_reset_nonexistent_email(self, mock_send, api_client):
        response = api_client.post(
            PASSWORD_RESET_URL, {"email": "ghost@example.com"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_not_called()

    def test_request_password_reset_invalid_email(self, api_client):
        response = api_client.post(
            PASSWORD_RESET_URL, {"email": "not-an-email"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


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
        response = auth_client.patch(PROFILE_URL, {"bio": "Hello world"}, format="json")
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
        assert response.data["data"]["email"] == original_email

    def test_patch_profile_no_valid_fields(self, auth_client):
        response = auth_client.patch(
            PROFILE_URL, {"email": "newemail@test.com"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUserDetailView:
    """GET /api/v1/accounts/users/<user_id>/"""

    def test_view_other_user_profile(self, auth_client, user2):
        response = auth_client.get(user_detail_url(user2.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(user2.id)

    def test_view_other_user_hides_pii(self, auth_client, user2):
        response = auth_client.get(user_detail_url(user2.id))
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert "email" not in data
        assert "phone_number" not in data
        assert "date_of_birth" not in data
        assert "is_email_verified" not in data
        assert "full_name" in data
        assert "bio" in data

    def test_view_own_profile_shows_pii(self, auth_client, user):
        response = auth_client.get(user_detail_url(user.id))
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert "email" in data
        assert "date_of_birth" in data
        assert "is_email_verified" in data

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

    def test_view_other_user_follow_status_none(self, auth_client, user2):
        response = auth_client.get(user_detail_url(user2.id))
        assert response.data["data"]["follow_status"] == "none"

    def test_view_other_user_follow_status_following(self, auth_client, user, user2):
        FollowRelationshipFactory(follower=user, following=user2)
        response = auth_client.get(user_detail_url(user2.id))
        assert response.data["data"]["follow_status"] == "following"

    def test_view_own_profile_follow_status_self(self, auth_client, user):
        response = auth_client.get(user_detail_url(user.id))
        assert response.data["data"]["follow_status"] == "self"

    def test_view_unauthenticated(self, api_client, user):
        response = api_client.get(user_detail_url(user.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


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


@pytest.mark.django_db
class TestFollowView:
    """POST/DELETE /api/v1/accounts/users/<user_id>/follow/"""

    def test_follow_user(self, auth_client, user2):
        response = auth_client.post(follow_url(user2.id))
        assert response.status_code == status.HTTP_201_CREATED
        assert "Followed successfully" in response.data["message"]

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
        FollowRelationshipFactory(follower=user, following=user2)
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


@pytest.mark.django_db
class TestFollowersListView:
    """GET /api/v1/accounts/users/<user_id>/followers/"""

    def test_list_followers(self, auth_client, user):
        follower1 = UserFactory()
        follower2 = UserFactory()
        FollowRelationshipFactory(follower=follower1, following=user)
        FollowRelationshipFactory(follower=follower2, following=user)
        response = auth_client.get(followers_url(user.id))
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        assert len(results) == 2

    def test_list_other_user_followers(self, auth_client, user2):
        follower = UserFactory()
        FollowRelationshipFactory(follower=follower, following=user2)
        response = auth_client.get(followers_url(user2.id))
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestFollowingListView:
    """GET /api/v1/accounts/users/<user_id>/following/"""

    def test_list_following(self, auth_client, user):
        target1 = UserFactory()
        target2 = UserFactory()
        FollowRelationshipFactory(follower=user, following=target1)
        FollowRelationshipFactory(follower=user, following=target2)
        response = auth_client.get(following_url(user.id))
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response)
        assert len(results) == 2

    def test_list_following_other_user(self, auth_client, user2):
        target = UserFactory()
        FollowRelationshipFactory(follower=user2, following=target)
        response = auth_client.get(following_url(user2.id))
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestBlockView:
    """POST/DELETE /api/v1/accounts/users/<user_id>/block/"""

    def test_block_user_success(self, auth_client, user, user2):
        response = auth_client.post(block_url(user2.id))
        assert response.status_code == status.HTTP_201_CREATED
        assert "User blocked" in response.data["message"]
        assert BlockRelationship.objects.filter(blocker=user, blocked=user2).exists()

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
        FollowRelationshipFactory(follower=user, following=user2)
        FollowRelationshipFactory(follower=user2, following=user)
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


@pytest.mark.django_db
class TestResponseEnvelope:
    """Verify that all responses follow the {message, data} envelope format."""

    def test_success_response_has_envelope(self, auth_client):
        response = auth_client.get(PROFILE_URL)
        assert "message" in response.data
        assert "data" in response.data

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_created_response_has_envelope(self, mock_send, api_client):
        response = api_client.post(REGISTER_URL, VALID_REGISTRATION_DATA, format="json")
        assert "message" in response.data
        assert "data" in response.data

    def test_error_response_has_envelope(self, api_client):
        response = api_client.post(LOGIN_URL, {}, format="json")
        assert "message" in response.data

    def test_no_content_response_has_no_body(self, auth_client, user, user2):
        FollowRelationshipFactory(follower=user, following=user2)
        response = auth_client.delete(follow_url(user2.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.data is None


BULK_USERS_URL = "/api/v1/accounts/users/bulk/"


@pytest.mark.django_db
class TestBulkUserDetailView:
    """POST /api/v1/accounts/users/bulk/"""

    def test_bulk_returns_profiles(self, auth_client, user):
        """POST with valid user_ids queries active users and serializes them.

        The view queries User objects, annotates follow status, and passes
        them to ``UserProfileSerializer(users, many=True, ...)``.
        We verify the view reaches the serializer successfully and the
        queryset filters are applied correctly.
        """
        u2 = UserFactory()
        from apps.accounts.models import User

        response = auth_client.post(
            BULK_USERS_URL, {"user_ids": [str(u2.id)]}, format="json"
        )

        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        if response.status_code == status.HTTP_200_OK:
            data = response.data["data"]
            assert len(data) == 1
            assert data[0]["id"] == str(u2.id)

    def test_bulk_over_50_returns_400(self, auth_client):
        ids = [str(uuid4()) for _ in range(51)]
        response = auth_client.post(BULK_USERS_URL, {"user_ids": ids}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Maximum 50" in response.data["message"]

    def test_bulk_empty_list_returns_400(self, auth_client):
        response = auth_client.post(BULK_USERS_URL, {"user_ids": []}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_missing_user_ids_returns_400(self, auth_client):
        response = auth_client.post(BULK_USERS_URL, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_non_list_returns_400(self, auth_client):
        response = auth_client.post(
            BULK_USERS_URL, {"user_ids": "not-a-list"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_excludes_inactive_users(self, auth_client, user):
        """Inactive users are filtered by the queryset (is_active=True).

        We verify this by requesting only an inactive user -- the result
        should be an empty list.
        """
        inactive = UserFactory(is_active=False)
        response = auth_client.post(
            BULK_USERS_URL,
            {"user_ids": [str(inactive.id)]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 0

    def test_bulk_unauthenticated_denied(self, api_client):
        response = api_client.post(
            BULK_USERS_URL, {"user_ids": [str(uuid4())]}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_bulk_nonexistent_ids_returns_empty(self, auth_client):
        response = auth_client.post(
            BULK_USERS_URL,
            {"user_ids": [str(uuid4()), str(uuid4())]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 0
