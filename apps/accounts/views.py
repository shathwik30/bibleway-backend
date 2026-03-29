from __future__ import annotations

from typing import Any
from uuid import UUID

from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.exceptions import BadRequestError

from apps.common.pagination import StandardPageNumberPagination
from apps.common.permissions import IsNotBlocked
from apps.common.throttles import AuthRateThrottle, OTPRateThrottle
from apps.common.views import BaseAPIView

from .models import User
from .serializers import (
    BlockRelationshipSerializer,
    ChangePasswordSerializer,
    FollowRelationshipSerializer,
    GoogleAuthSerializer,
    OTPVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ResendOTPSerializer,
    UserListSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
    UserUpdateSerializer,
)
from .services import AuthService, BlockService, FollowService, UserService


class UserRegistrationView(BaseAPIView):
    """POST /api/v1/accounts/register/"""

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._user_service = UserService()

    def post(self, request: Request) -> Response:
        serializer: UserRegistrationSerializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user: User = self._user_service.register_user(
            validated_data=serializer.validated_data
        )
        return self.created_response(
            data=UserProfileSerializer(user).data,
            message="Registration successful. Please verify your email.",
        )


class UserLoginView(BaseAPIView):
    """POST /api/v1/accounts/login/"""

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        serializer: UserLoginSerializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens: dict[str, str] = self._auth_service.login(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        return self.success_response(data=tokens, message="Login successful.")


class GoogleAuthView(BaseAPIView):
    """POST /api/v1/accounts/google-auth/"""

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        serializer: GoogleAuthSerializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result: dict[str, Any] = self._auth_service.google_auth(
            validated_data=serializer.validated_data,
        )
        if result.get("is_new_user") and "google_user" in result:
            return self.success_response(
                data=result,
                message="Additional profile information required.",
                status_code=status.HTTP_202_ACCEPTED,
            )
        return self.success_response(data=result, message="Google authentication successful.")


class UserLogoutView(BaseAPIView):
    """POST /api/v1/accounts/logout/"""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        refresh_token: str | None = request.data.get("refresh")
        if not refresh_token:
            raise BadRequestError(detail="Refresh token is required.")
        self._auth_service.logout(refresh_token_str=refresh_token)
        return self.success_response(message="Logged out successfully.")


class TokenRefreshView(BaseAPIView):
    """POST /api/v1/accounts/token/refresh/"""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        refresh_token: str | None = request.data.get("refresh")
        if not refresh_token:
            raise BadRequestError(detail="Refresh token is required.")
        tokens: dict[str, str] = self._auth_service.refresh_token(
            refresh_token_str=refresh_token
        )
        return self.success_response(data=tokens, message="Token refreshed.")


class EmailVerificationView(BaseAPIView):
    """POST /api/v1/accounts/verify-email/"""

    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        serializer: OTPVerifySerializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user: User = self._auth_service.verify_email_otp(
            email=serializer.validated_data["email"],
            otp_code=serializer.validated_data["otp_code"],
        )
        return self.success_response(
            data=UserProfileSerializer(user).data,
            message="Email verified successfully.",
        )


class PasswordResetRequestView(BaseAPIView):
    """POST /api/v1/accounts/password-reset/"""

    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        serializer: PasswordResetRequestSerializer = PasswordResetRequestSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        self._auth_service.request_password_reset(
            email=serializer.validated_data["email"]
        )
        return self.success_response(
            message="If an account exists with this email, a reset code has been sent."
        )


class PasswordResetConfirmView(BaseAPIView):
    """POST /api/v1/accounts/password-reset/confirm/"""

    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        serializer: PasswordResetConfirmSerializer = PasswordResetConfirmSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        self._auth_service.confirm_password_reset(
            email=serializer.validated_data["email"],
            otp_code=serializer.validated_data["otp_code"],
            new_password=serializer.validated_data["new_password"],
        )
        return self.success_response(
            message="Password reset successful. Please log in with your new password."
        )


class ChangePasswordView(BaseAPIView):
    """POST /api/v1/accounts/change-password/"""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        serializer: ChangePasswordSerializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._auth_service.change_password(
            user=request.user,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )
        return self.success_response(message="Password changed successfully.")


class UserProfileView(BaseAPIView):
    """GET / PUT / PATCH /api/v1/accounts/profile/"""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._user_service = UserService()

    def get(self, request: Request) -> Response:
        cache_key: str = f"profile_resp:{request.user.id}"
        cached: dict[str, Any] | None = cache.get(cache_key)
        if cached is not None:
            return self.success_response(data=cached)

        user: User = self._user_service.get_profile(user_id=request.user.id)
        data: dict[str, Any] = UserProfileSerializer(user, context={"user": request.user}).data
        cache.set(cache_key, data, timeout=60)
        return self.success_response(data=data)

    def put(self, request: Request) -> Response:
        return self._update(request, partial=False)

    def patch(self, request: Request) -> Response:
        return self._update(request, partial=True)

    def _update(self, request: Request, partial: bool) -> Response:
        serializer: UserUpdateSerializer = UserUpdateSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self._user_service.update_profile(
            user=request.user,
            validated_data=serializer.validated_data,
        )
        cache.delete(f"profile_resp:{request.user.id}")
        user: User = self._user_service.get_profile(user_id=request.user.id)
        return self.success_response(
            data=UserProfileSerializer(user, context={"user": request.user}).data,
            message="Profile updated successfully.",
        )


class UserDetailView(BaseAPIView):
    """GET /api/v1/accounts/users/<user_id>/"""

    permission_classes = [IsAuthenticated, IsNotBlocked]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._user_service = UserService()

    def get_target_user_id(self) -> UUID | None:
        return self.kwargs.get("user_id")

    def get(self, request: Request, user_id: UUID) -> Response:
        user: User = self._user_service.get_profile(user_id=user_id)
        return self.success_response(
            data=UserProfileSerializer(user, context={"user": request.user}).data,
        )


class UserSearchView(BaseAPIView):
    """GET /api/v1/accounts/users/search/?q=...&country=..."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._user_service = UserService()

    def get(self, request: Request) -> Response:
        query: str = request.query_params.get("q", "").strip()
        country: str | None = request.query_params.get("country")
        queryset = self._user_service.search_users(query=query, country=country)
        return self.paginated_response(queryset, UserListSerializer, request)


class FollowView(BaseAPIView):
    """POST / DELETE /api/v1/accounts/users/<user_id>/follow/"""

    permission_classes = [IsAuthenticated, IsNotBlocked]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._follow_service = FollowService()

    def get_target_user_id(self) -> UUID | None:
        return self.kwargs.get("user_id")

    def post(self, request: Request, user_id: UUID) -> Response:
        relationship = self._follow_service.follow_user(
            follower=request.user,
            target_id=user_id,
        )
        return self.created_response(
            data=FollowRelationshipSerializer(relationship).data,
            message="Followed successfully.",
        )

    def delete(self, request: Request, user_id: UUID) -> Response:
        self._follow_service.unfollow_user(
            follower=request.user,
            target_id=user_id,
        )
        return self.no_content_response()


class FollowersListView(BaseAPIView):
    """GET /api/v1/accounts/users/<user_id>/followers/"""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._follow_service = FollowService()

    def get(self, request: Request, user_id: UUID) -> Response:
        queryset = self._follow_service.get_followers(user_id=user_id)
        return self.paginated_response(queryset, FollowRelationshipSerializer, request)


class FollowingListView(BaseAPIView):
    """GET /api/v1/accounts/users/<user_id>/following/"""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._follow_service = FollowService()

    def get(self, request: Request, user_id: UUID) -> Response:
        queryset = self._follow_service.get_following(user_id=user_id)
        return self.paginated_response(queryset, FollowRelationshipSerializer, request)


class BlockView(BaseAPIView):
    """POST / DELETE /api/v1/accounts/users/<user_id>/block/"""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._block_service = BlockService()

    def post(self, request: Request, user_id: UUID) -> Response:
        relationship = self._block_service.block_user(
            blocker=request.user,
            target_id=user_id,
        )
        return self.created_response(
            data=BlockRelationshipSerializer(relationship).data,
            message="User blocked successfully.",
        )

    def delete(self, request: Request, user_id: UUID) -> Response:
        self._block_service.unblock_user(
            blocker=request.user,
            target_id=user_id,
        )
        return self.no_content_response()


class BlockedUsersListView(BaseAPIView):
    """GET /api/v1/accounts/blocked-users/"""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._block_service = BlockService()

    def get(self, request: Request) -> Response:
        queryset = self._block_service.get_blocked_users(user_id=request.user.id)
        return self.paginated_response(queryset, BlockRelationshipSerializer, request)


class ResendOTPView(BaseAPIView):
    """POST /api/v1/accounts/auth/resend-otp/"""

    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._user_service = UserService()

    def post(self, request: Request) -> Response:
        serializer: ResendOTPSerializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._user_service.resend_verification_otp(
            email=serializer.validated_data["email"]
        )
        return self.success_response(
            message="If an unverified account exists, a new OTP has been sent."
        )
