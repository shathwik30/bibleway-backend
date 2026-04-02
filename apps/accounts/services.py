from __future__ import annotations
import logging
from typing import Any
from uuid import UUID
from django.conf import settings
from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from apps.common.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

from apps.common.services import BaseService, BaseUserScopedService
from apps.common.utils import generate_otp, get_otp_expiry, hash_otp, verify_otp
from .models import BlockRelationship, FollowRelationship, OTPToken, User

logger: logging.Logger = logging.getLogger(__name__)


def _get_active_user(user_id: UUID) -> User:
    """Retrieve an active user or raise NotFoundError."""

    try:
        return User.objects.get(pk=user_id, is_active=True)

    except User.DoesNotExist:
        raise NotFoundError(detail="User not found.")


def _check_not_blocked(user_a: User, user_b: User) -> None:
    """Raise ForbiddenError if either user has blocked the other."""

    if BlockRelationship.objects.filter(
        Q(blocker=user_a, blocked=user_b) | Q(blocker=user_b, blocked=user_a)
    ).exists():
        raise ForbiddenError(detail="This action is not allowed.")


class OTPService(BaseService[OTPToken]):
    """Handles OTP creation, verification, and invalidation."""

    model = OTPToken

    def create_otp(self, user: User, purpose: str) -> str:
        """Create a new OTP token and return the plain-text code.
        Invalidates any existing unused OTPs for the same user/purpose first.
        """
        self.invalidate_user_otps(user=user, purpose=purpose)
        plain_code: str = generate_otp()
        OTPToken.objects.create(
            user=user,
            hashed_code=hash_otp(plain_code),
            purpose=purpose,
            expires_at=get_otp_expiry(minutes=10),
        )

        return plain_code

    def verify_otp(self, user: User, plain_code: str, purpose: str) -> OTPToken:
        """Verify an OTP code. Returns the token on success.
        Raises BadRequestError if the code is invalid, expired, or max attempts reached.
        Uses select_for_update to prevent TOCTOU race conditions.
        """
        error_detail: str | None = None

        with transaction.atomic():
            token: OTPToken | None = (
                OTPToken.objects.select_for_update()
                .filter(user=user, purpose=purpose, used=False)
                .order_by("-created_at")
                .first()
            )

            if token is None:
                error_detail = "No active OTP found. Please request a new one."

            elif token.is_expired:
                error_detail = "OTP has expired. Please request a new one."

            elif token.is_max_attempts:
                error_detail = (
                    "Maximum verification attempts exceeded. Please request a new OTP."
                )

            elif not verify_otp(plain_code, token.hashed_code):
                token.attempts += 1
                token.save(update_fields=["attempts"])
                remaining: int = max(OTPToken.MAX_ATTEMPTS - token.attempts, 0)
                error_detail = f"Invalid OTP code. {remaining} attempt(s) remaining."

            else:
                token.used = True
                token.save(update_fields=["used"])

        if error_detail is not None:
            raise BadRequestError(detail=error_detail)

        return token

    def invalidate_user_otps(self, user: User, purpose: str) -> int:
        """Mark all unused OTPs for the given user and purpose as used."""

        return OTPToken.objects.filter(
            user=user,
            purpose=purpose,
            used=False,
        ).update(used=True)


class UserService(BaseService[User]):
    """Handles user registration, profile retrieval, and updates."""

    model = User

    def __init__(self) -> None:
        self._otp_service = OTPService()

    def get_queryset(self) -> QuerySet[User]:
        return super().get_queryset().filter(is_active=True)

    @transaction.atomic
    def register_user(self, validated_data: dict[str, Any]) -> User:
        """Register a new user, create an OTP, and trigger the verification email task."""
        email: str = validated_data["email"]

        if User.objects.filter(email__iexact=email).exists():
            raise ConflictError(detail="A user with this email already exists.")

        password: str = validated_data.pop("password")

        try:
            user: User = User.objects.create_user(
                email=email,
                password=password,
                **{k: v for k, v in validated_data.items() if k != "email"},
            )

        except IntegrityError:
            raise ConflictError(detail="A user with this email already exists.")

        plain_code: str = self._otp_service.create_otp(
            user=user,
            purpose=OTPToken.Purpose.REGISTER,
        )
        self._send_otp_email(user=user, code=plain_code, purpose="registration")

        return user

    def get_profile(self, user_id: UUID) -> User:
        """Retrieve a user profile by ID.
        Counts (follower_count, following_count, post_count, prayer_count)
        are stored directly on the User model and kept in sync via signals,
        so no subquery annotations are needed.
        """

        try:
            return self.get_queryset().get(pk=user_id)

        except User.DoesNotExist:
            raise NotFoundError(detail=f"User with id '{user_id}' not found.")

    def update_profile(self, user: User, validated_data: dict[str, Any]) -> User:
        """Update mutable profile fields. Email is immutable."""
        validated_data.pop("email", None)
        allowed_fields: set[str] = {
            "full_name",
            "bio",
            "profile_photo",
            "preferred_language",
            "country",
            "phone_number",
            "date_of_birth",
        }
        update_data: dict[str, Any] = {
            k: v for k, v in validated_data.items() if k in allowed_fields
        }

        if not update_data:
            raise BadRequestError(detail="No valid fields provided for update.")

        for field, value in update_data.items():
            setattr(user, field, value)

        user.full_clean()
        user.save(update_fields=list(update_data.keys()))

        return user

    def search_users(self, query: str, country: str | None = None) -> QuerySet[User]:
        """Search active, verified users by name. Optionally filter by country."""
        qs: QuerySet[User] = self.get_queryset().filter(is_email_verified=True)

        if query:
            qs = qs.filter(full_name__icontains=query)

        if country:
            qs = qs.filter(country__iexact=country)

        return qs

    def resend_verification_otp(self, email: str) -> None:
        """Resend email verification OTP for unverified users."""

        try:
            user: User = User.objects.get(email__iexact=email, is_active=True)

        except User.DoesNotExist:
            return

        if user.is_email_verified:
            return

        plain_code: str = self._otp_service.create_otp(
            user=user,
            purpose=OTPToken.Purpose.REGISTER,
        )
        self._send_otp_email(user=user, code=plain_code, purpose="registration")

    @staticmethod
    def _send_otp_email(user: User, code: str, purpose: str) -> None:
        """Dispatch the OTP email asynchronously via Celery."""
        _dispatch_otp_email(user=user, code=code, purpose=purpose)


def _dispatch_otp_email(user: User, code: str, purpose: str) -> None:
    """Send OTP email via Celery task. Logs and swallows failures."""

    try:
        from .tasks import send_otp_email_task

        send_otp_email_task.delay(
            user_email=user.email,
            user_name=user.full_name,
            otp_code=code,
            purpose=purpose,
        )

    except Exception:
        logger.exception("Failed to dispatch OTP email task for %s", user.email)


class AuthService:
    """Handles authentication: login, logout, token refresh, password operations."""

    def __init__(self) -> None:
        self._otp_service = OTPService()

    @transaction.atomic
    def google_auth(self, validated_data: dict[str, Any]) -> dict[str, Any]:
        """Authenticate or register via Google Sign-In.
        - Existing user: returns JWT tokens.
        - New user without required fields: returns google profile for frontend completion.
        - New user with required fields: creates user, returns JWT tokens.
        """
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        token: str = validated_data["id_token"]

        try:
            google_info: dict[str, Any] = google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                clock_skew_in_seconds=10,
            )

        except ValueError:
            raise BadRequestError(detail="Invalid Google ID token.")

        allowed_ids: list[str] = settings.GOOGLE_OAUTH_CLIENT_IDS

        if not allowed_ids:
            raise BadRequestError(
                detail="Google Sign-In is not configured on the server."
            )

        if google_info.get("aud") not in allowed_ids:
            raise BadRequestError(detail="Invalid Google ID token audience.")

        email: str = google_info.get("email", "").lower().strip()

        if not email or not google_info.get("email_verified", False):
            raise BadRequestError(detail="Google account email is not verified.")

        existing_user: User | None = User.objects.filter(email__iexact=email).first()

        if existing_user is not None:
            if not existing_user.is_active:
                raise ForbiddenError(detail="This account has been deactivated.")

            logger.info("Google login for existing user=%s", existing_user.id)
            refresh: RefreshToken = RefreshToken.for_user(existing_user)

            return {
                "is_new_user": False,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user_id": str(existing_user.id),
            }

        google_name: str = google_info.get("name", "")
        google_picture: str = google_info.get("picture", "")
        has_required: bool = all(
            k in validated_data for k in ("date_of_birth", "gender", "country")
        )

        if not has_required:
            return {
                "is_new_user": True,
                "google_user": {
                    "email": email,
                    "full_name": google_name,
                    "profile_photo": google_picture,
                },
            }

        full_name: str = validated_data.get("full_name", google_name) or google_name

        if not full_name:
            raise BadRequestError(detail="Full name is required.")

        try:
            user: User = User.objects.create_user(
                email=email,
                password=None,
                full_name=full_name,
                date_of_birth=validated_data["date_of_birth"],
                gender=validated_data["gender"],
                country=validated_data["country"],
                preferred_language=validated_data.get("preferred_language", "en"),
                phone_number=validated_data.get("phone_number", ""),
                is_email_verified=True,
            )

        except IntegrityError:
            raise ConflictError(detail="A user with this email already exists.")

        logger.info("Google registration for new user=%s", user.id)
        refresh = RefreshToken.for_user(user)

        return {
            "is_new_user": False,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user_id": str(user.id),
        }

    def login(self, email: str, password: str) -> dict[str, str]:
        """Validate credentials and return JWT token pair.
        Raises BadRequestError for invalid credentials or unverified email.
        """
        user: User | None = authenticate(email=email, password=password)

        if user is None:
            logger.warning("Failed login attempt for email=%s", email)
            raise BadRequestError(detail="Invalid email or password.")

        if not user.is_active:
            raise ForbiddenError(detail="This account has been deactivated.")

        if not user.is_email_verified:
            raise BadRequestError(
                detail="Please verify your email address before logging in."
            )

        refresh: RefreshToken = RefreshToken.for_user(user)

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user_id": str(user.id),
        }

    def refresh_token(self, refresh_token_str: str) -> dict[str, str]:
        """Generate a new access token from a valid refresh token."""

        try:
            refresh: RefreshToken = RefreshToken(refresh_token_str)

            return {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }

        except TokenError as exc:
            raise BadRequestError(detail=f"Invalid or expired refresh token: {exc}")

    def logout(self, refresh_token_str: str) -> None:
        """Blacklist the refresh token to log out the user."""

        try:
            token: RefreshToken = RefreshToken(refresh_token_str)
            token.blacklist()

        except TokenError as exc:
            raise BadRequestError(detail=f"Invalid refresh token: {exc}")

    def verify_email_otp(self, email: str, otp_code: str) -> User:
        """Verify email via OTP and activate the user."""
        user: User = self._get_user_by_email(email)

        if user.is_email_verified:
            raise ConflictError(detail="Email is already verified.")

        self._otp_service.verify_otp(
            user=user,
            plain_code=otp_code,
            purpose=OTPToken.Purpose.REGISTER,
        )
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        return user

    def request_password_reset(self, email: str) -> None:
        """Generate a password-reset OTP and send it via email.
        Silently returns if the email doesn't exist to prevent user enumeration.
        """

        try:
            user: User = self._get_user_by_email(email)

        except NotFoundError:
            return

        plain_code: str = self._otp_service.create_otp(
            user=user,
            purpose=OTPToken.Purpose.PASSWORD_RESET,
        )
        _dispatch_otp_email(user=user, code=plain_code, purpose="password_reset")

    @transaction.atomic
    def confirm_password_reset(
        self, email: str, otp_code: str, new_password: str
    ) -> User:
        """Verify OTP, set the new password, and invalidate all sessions."""
        user: User = self._get_user_by_email(email)
        self._otp_service.verify_otp(
            user=user,
            plain_code=otp_code,
            purpose=OTPToken.Purpose.PASSWORD_RESET,
        )
        user.set_password(new_password)
        user.save(update_fields=["password"])
        self._invalidate_all_sessions(user=user)

        return user

    def change_password(self, user: User, old_password: str, new_password: str) -> User:
        """Change password for an authenticated user."""

        if not user.check_password(old_password):
            raise BadRequestError(detail="Current password is incorrect.")

        user.set_password(new_password)
        user.save(update_fields=["password"])
        self._invalidate_all_sessions(user=user)

        return user

    def _get_user_by_email(self, email: str) -> User:
        """Retrieve a user by email or raise NotFoundError."""

        try:
            return User.objects.get(email__iexact=email, is_active=True)

        except User.DoesNotExist:
            raise NotFoundError(detail="No active account found with this email.")

    @staticmethod
    def _invalidate_all_sessions(user: User) -> None:
        """Blacklist all outstanding refresh tokens for the user."""
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

        outstanding: QuerySet[OutstandingToken] = OutstandingToken.objects.filter(
            user=user
        )

        for token_record in outstanding:
            try:
                refresh: RefreshToken = RefreshToken(token_record.token)
                refresh.blacklist()

            except TokenError:
                pass


class FollowService(BaseService[FollowRelationship]):
    """Handles follow/unfollow and follower listings."""

    model = FollowRelationship

    @transaction.atomic
    def follow_user(self, follower: User, target_id: UUID) -> FollowRelationship:
        """Follow a user. All follows are immediate."""

        if follower.id == target_id:
            raise BadRequestError(detail="You cannot follow yourself.")

        target: User = _get_active_user(target_id)
        _check_not_blocked(user_a=follower, user_b=target)
        relationship: FollowRelationship
        created: bool
        relationship, created = FollowRelationship.objects.get_or_create(
            follower=follower,
            following=target,
        )

        if not created:
            raise ConflictError(detail="You already follow this user.")

        self._invalidate_profile_caches(follower.id, target_id)
        self._send_follow_notification(follower=follower, target_id=target_id)

        return relationship

    @staticmethod
    def _send_follow_notification(follower: User, target_id: UUID) -> None:
        """Dispatch a follow notification to the target user."""

        try:
            from apps.common.utils import build_notification_data
            from apps.notifications.services import NotificationService

            NotificationService().create_notification(
                recipient_id=target_id,
                sender_id=follower.id,
                notification_type="follow",
                title=f"{follower.full_name} started following you",
                body=f"{follower.full_name} is now following you.",
                data=build_notification_data("follow", user_id=follower.id),
            )

        except Exception:
            logger.warning(
                "Failed to send follow notification from %s to %s",
                follower.id,
                target_id,
                exc_info=True,
            )

    @staticmethod
    def _invalidate_profile_caches(*user_ids: UUID) -> None:
        """Clear cached profile responses so follower counts refresh."""
        from django.core.cache import cache

        for uid in user_ids:
            cache.delete(f"profile_resp:{uid}")

    def unfollow_user(self, follower: User, target_id: UUID) -> None:
        """Remove a follow relationship."""
        deleted_count: int
        deleted_count, _ = FollowRelationship.objects.filter(
            follower=follower,
            following_id=target_id,
        ).delete()

        if deleted_count == 0:
            raise NotFoundError(detail="You are not following this user.")

        self._invalidate_profile_caches(follower.id, target_id)

    def get_followers(self, user_id: UUID) -> QuerySet[FollowRelationship]:
        """Return followers for a user."""

        return FollowRelationship.objects.filter(following_id=user_id).select_related(
            "follower"
        )

    def get_following(self, user_id: UUID) -> QuerySet[FollowRelationship]:
        """Return users that the given user is following."""

        return FollowRelationship.objects.filter(follower_id=user_id).select_related(
            "following"
        )

    def get_follower_count(self, user_id: UUID) -> int:
        """Count followers."""

        return FollowRelationship.objects.filter(following_id=user_id).count()

    def get_following_count(self, user_id: UUID) -> int:
        """Count following."""

        return FollowRelationship.objects.filter(follower_id=user_id).count()


class BlockService(BaseUserScopedService[BlockRelationship]):
    """Handles blocking/unblocking users and querying block status."""

    model = BlockRelationship

    user_field = "blocker"

    @transaction.atomic
    def block_user(self, blocker: User, target_id: UUID) -> BlockRelationship:
        """Block a user. The signal in signals.py handles follow cleanup."""

        if blocker.id == target_id:
            raise BadRequestError(detail="You cannot block yourself.")

        _get_active_user(target_id)
        relationship: BlockRelationship
        created: bool
        relationship, created = BlockRelationship.objects.get_or_create(
            blocker=blocker,
            blocked_id=target_id,
        )

        if not created:
            raise ConflictError(detail="You have already blocked this user.")

        return relationship

    def unblock_user(self, blocker: User, target_id: UUID) -> None:
        """Remove a block relationship."""
        deleted_count: int
        deleted_count, _ = BlockRelationship.objects.filter(
            blocker=blocker,
            blocked_id=target_id,
        ).delete()

        if deleted_count == 0:
            raise NotFoundError(detail="You have not blocked this user.")

    def get_blocked_users(self, user_id: UUID) -> QuerySet[BlockRelationship]:
        """Return all block relationships for a user."""

        return BlockRelationship.objects.filter(blocker_id=user_id).select_related(
            "blocked"
        )

    def is_blocked(self, user_a_id: UUID, user_b_id: UUID) -> bool:
        """Check if either user has blocked the other."""

        return BlockRelationship.objects.filter(
            Q(blocker_id=user_a_id, blocked_id=user_b_id)
            | Q(blocker_id=user_b_id, blocked_id=user_a_id)
        ).exists()
