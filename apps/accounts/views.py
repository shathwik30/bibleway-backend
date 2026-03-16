from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.pagination import StandardPageNumberPagination
from apps.common.permissions import IsNotBlocked
from apps.common.throttles import AuthRateThrottle, OTPRateThrottle
from apps.common.views import BaseAPIView

from apps.common.exceptions import ForbiddenError

from .serializers import (
    BlockRelationshipSerializer,
    ChangePasswordSerializer,
    FollowRelationshipSerializer,
    OTPVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PrivacySettingsSerializer,
    ResendOTPSerializer,
    UserListSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
    UserUpdateSerializer,
)
from .services import AuthService, BlockService, FollowService, UserService


# ── Registration & Authentication ────────────────────────────────────


class UserRegistrationView(BaseAPIView):
    """POST /api/v1/accounts/register/ — Create a new user account."""

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._user_service = UserService()

    def post(self, request: Request) -> Response:
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self._user_service.register_user(
            validated_data=serializer.validated_data
        )
        return self.created_response(
            data=UserProfileSerializer(user).data,
            message="Registration successful. Please verify your email.",
        )


class UserLoginView(BaseAPIView):
    """POST /api/v1/accounts/login/ — Authenticate and return JWT tokens."""

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens: dict[str, str] = self._auth_service.login(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        return self.success_response(data=tokens, message="Login successful.")


class UserLogoutView(BaseAPIView):
    """POST /api/v1/accounts/logout/ — Blacklist the refresh token."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        refresh_token: str | None = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"message": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self._auth_service.logout(refresh_token_str=refresh_token)
        return self.success_response(message="Logged out successfully.")


class TokenRefreshView(BaseAPIView):
    """POST /api/v1/accounts/token/refresh/ — Refresh JWT access token."""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        refresh_token: str | None = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"message": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tokens: dict[str, str] = self._auth_service.refresh_token(
            refresh_token_str=refresh_token
        )
        return self.success_response(data=tokens, message="Token refreshed.")


# ── Email Verification ───────────────────────────────────────────────


class EmailVerificationView(BaseAPIView):
    """POST /api/v1/accounts/verify-email/ — Verify email with OTP."""

    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self._auth_service.verify_email_otp(
            email=serializer.validated_data["email"],
            otp_code=serializer.validated_data["otp_code"],
        )
        return self.success_response(
            data=UserProfileSerializer(user).data,
            message="Email verified successfully.",
        )


# ── Password Management ─────────────────────────────────────────────


class PasswordResetRequestView(BaseAPIView):
    """POST /api/v1/accounts/password-reset/ — Request a password reset OTP."""

    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._auth_service.request_password_reset(
            email=serializer.validated_data["email"]
        )
        return self.success_response(
            message="If an account exists with this email, a reset code has been sent."
        )


class PasswordResetConfirmView(BaseAPIView):
    """POST /api/v1/accounts/password-reset/confirm/ — Confirm reset with OTP."""

    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
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
    """POST /api/v1/accounts/change-password/ — Change password (authenticated)."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_service = AuthService()

    def post(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._auth_service.change_password(
            user=request.user,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )
        return self.success_response(message="Password changed successfully.")


# ── User Profile ─────────────────────────────────────────────────────


class UserProfileView(BaseAPIView):
    """
    GET  /api/v1/accounts/profile/ — Retrieve own profile.
    PUT  /api/v1/accounts/profile/ — Full update own profile.
    PATCH /api/v1/accounts/profile/ — Partial update own profile.
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._user_service = UserService()

    def get(self, request: Request) -> Response:
        from django.core.cache import cache

        cache_key = f"profile_resp:{request.user.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return self.success_response(data=cached)

        user = self._user_service.get_profile(user_id=request.user.id)
        data = UserProfileSerializer(user).data
        cache.set(cache_key, data, timeout=60)
        return self.success_response(data=data)

    def put(self, request: Request) -> Response:
        return self._update(request, partial=False)

    def patch(self, request: Request) -> Response:
        return self._update(request, partial=True)

    def _update(self, request: Request, partial: bool) -> Response:
        from django.core.cache import cache

        serializer = UserUpdateSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        user = self._user_service.update_profile(
            user=request.user,
            validated_data=serializer.validated_data,
        )
        cache.delete(f"profile_resp:{request.user.id}")
        return self.success_response(
            data=UserProfileSerializer(user).data,
            message="Profile updated successfully.",
        )


class UserDetailView(BaseAPIView):
    """GET /api/v1/accounts/users/<user_id>/ — View another user's profile."""

    permission_classes = [IsAuthenticated, IsNotBlocked]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._user_service = UserService()

    def get_target_user_id(self) -> UUID | None:
        """Used by IsNotBlocked permission."""
        return self.kwargs.get("user_id")

    def get(self, request: Request, user_id: UUID) -> Response:
        user = self._user_service.get_profile(user_id=user_id)
        serializer = UserProfileSerializer(
            user, context={"user": request.user}
        )
        return self.success_response(data=serializer.data)


class UserSearchView(BaseAPIView):
    """GET /api/v1/accounts/users/search/?q=...&country=... — Search users."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._user_service = UserService()

    def get(self, request: Request) -> Response:
        query: str = request.query_params.get("q", "").strip()
        country: str | None = request.query_params.get("country")

        queryset = self._user_service.search_users(query=query, country=country)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)

        if page is not None:
            serializer = UserListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = UserListSerializer(queryset, many=True)
        return self.success_response(data=serializer.data)


# ── Follow Management ────────────────────────────────────────────────


class FollowView(BaseAPIView):
    """
    POST   /api/v1/accounts/users/<user_id>/follow/ — Follow a user.
    DELETE /api/v1/accounts/users/<user_id>/follow/ — Unfollow a user.
    """

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
        message: str = (
            "Follow request sent."
            if relationship.status == "pending"
            else "Followed successfully."
        )
        return self.created_response(
            data=FollowRelationshipSerializer(relationship).data,
            message=message,
        )

    def delete(self, request: Request, user_id: UUID) -> Response:
        self._follow_service.unfollow_user(
            follower=request.user,
            target_id=user_id,
        )
        return self.no_content_response()


class FollowRequestView(BaseAPIView):
    """
    POST   /api/v1/accounts/follow-requests/<user_id>/ — Accept a follow request.
    DELETE /api/v1/accounts/follow-requests/<user_id>/ — Reject a follow request.
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._follow_service = FollowService()

    def post(self, request: Request, user_id: UUID) -> Response:
        relationship = self._follow_service.accept_follow_request(
            user=request.user,
            follower_id=user_id,
        )
        return self.success_response(
            data=FollowRelationshipSerializer(relationship).data,
            message="Follow request accepted.",
        )

    def delete(self, request: Request, user_id: UUID) -> Response:
        self._follow_service.reject_follow_request(
            user=request.user,
            follower_id=user_id,
        )
        return self.no_content_response()


class FollowersListView(BaseAPIView):
    """GET /api/v1/accounts/users/<user_id>/followers/ — List a user's followers."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._follow_service = FollowService()
        self._user_service = UserService()

    def get(self, request: Request, user_id: UUID) -> Response:
        if user_id != request.user.id:
            target = self._user_service.get_profile(user_id=user_id)
            if target.hide_followers_list:
                raise ForbiddenError(detail="This user's followers list is private.")
        queryset = self._follow_service.get_followers(user_id=user_id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)

        if page is not None:
            serializer = FollowRelationshipSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = FollowRelationshipSerializer(queryset, many=True)
        return self.success_response(data=serializer.data)


class FollowingListView(BaseAPIView):
    """GET /api/v1/accounts/users/<user_id>/following/ — List who a user follows."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._follow_service = FollowService()

    def get(self, request: Request, user_id: UUID) -> Response:
        queryset = self._follow_service.get_following(user_id=user_id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)

        if page is not None:
            serializer = FollowRelationshipSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = FollowRelationshipSerializer(queryset, many=True)
        return self.success_response(data=serializer.data)


# ── Block Management ─────────────────────────────────────────────────


class BlockView(BaseAPIView):
    """
    POST   /api/v1/accounts/users/<user_id>/block/ — Block a user.
    DELETE /api/v1/accounts/users/<user_id>/block/ — Unblock a user.
    """

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
    """GET /api/v1/accounts/blocked-users/ — List all blocked users."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._block_service = BlockService()

    def get(self, request: Request) -> Response:
        queryset = self._block_service.get_blocked_users(user_id=request.user.id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)

        if page is not None:
            serializer = BlockRelationshipSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = BlockRelationshipSerializer(queryset, many=True)
        return self.success_response(data=serializer.data)


# ── Privacy Settings ─────────────────────────────────────────────────


class PrivacySettingsView(BaseAPIView):
    """
    GET /api/v1/accounts/privacy/ — Retrieve privacy settings.
    PUT /api/v1/accounts/privacy/ — Update privacy settings.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        data: dict[str, Any] = {
            "account_visibility": request.user.account_visibility,
            "hide_followers_list": request.user.hide_followers_list,
        }
        return self.success_response(data=data)

    def put(self, request: Request) -> Response:
        serializer = PrivacySettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        updated_fields: list[str] = []

        if "account_visibility" in serializer.validated_data:
            user.account_visibility = serializer.validated_data["account_visibility"]
            updated_fields.append("account_visibility")

        if "hide_followers_list" in serializer.validated_data:
            user.hide_followers_list = serializer.validated_data["hide_followers_list"]
            updated_fields.append("hide_followers_list")

        if updated_fields:
            user.save(update_fields=updated_fields)

        data: dict[str, Any] = {
            "account_visibility": user.account_visibility,
            "hide_followers_list": user.hide_followers_list,
        }
        return self.success_response(
            data=data,
            message="Privacy settings updated.",
        )


# ── Resend OTP ──────────────────────────────────────────────────────


class ResendOTPView(BaseAPIView):
    """POST /api/v1/accounts/auth/resend-otp/ — Resend verification OTP."""

    permission_classes = [AllowAny]
    throttle_classes = [OTPRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._user_service = UserService()

    def post(self, request: Request) -> Response:
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._user_service.resend_verification_otp(
            email=serializer.validated_data["email"]
        )
        return self.success_response(
            message="If an unverified account exists, a new OTP has been sent."
        )


# ── Pending Follow Requests ─────────────────────────────────────────


class PendingFollowRequestsListView(BaseAPIView):
    """GET /api/v1/accounts/follow-requests/ — List pending follow requests."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._follow_service = FollowService()

    def get(self, request: Request) -> Response:
        queryset = self._follow_service.get_pending_requests(user_id=request.user.id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)

        if page is not None:
            serializer = FollowRelationshipSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = FollowRelationshipSerializer(queryset, many=True)
        return self.success_response(data=serializer.data)
