"""Tests for accounts app services: OTPService, UserService, AuthService, FollowService, BlockService."""

from __future__ import annotations
import datetime
from unittest.mock import patch
from uuid import uuid4
import pytest
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.models import (
    BlockRelationship,
    FollowRelationship,
    OTPToken,
)

from apps.accounts.services import (
    AuthService,
    BlockService,
    FollowService,
    OTPService,
    UserService,
)

from apps.common.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

from conftest import (
    BlockRelationshipFactory,
    FollowRelationshipFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestOTPService:
    """Tests for OTPService: create_otp, verify_otp, invalidate_user_otps."""

    def setup_method(self):
        self.service = OTPService()

    def test_create_otp_returns_6_digit_code(self):
        user = UserFactory()
        code = self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)
        assert len(code) == 6
        assert code.isdigit()

    def test_create_otp_creates_token_in_db(self):
        user = UserFactory()
        self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)
        assert OTPToken.objects.filter(
            user=user, purpose="register", used=False
        ).exists()

    def test_create_otp_invalidates_previous_otps(self):
        user = UserFactory()
        self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)
        self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)
        unused = OTPToken.objects.filter(user=user, purpose="register", used=False)
        assert unused.count() == 1

    def test_verify_otp_success(self):
        user = UserFactory()
        code = self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)
        token = self.service.verify_otp(
            user=user, plain_code=code, purpose=OTPToken.Purpose.REGISTER
        )
        assert token.used is True

    def test_verify_otp_invalid_code(self):
        user = UserFactory()
        self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)

        with pytest.raises(BadRequestError, match="Invalid OTP code"):
            self.service.verify_otp(
                user=user, plain_code="000000", purpose=OTPToken.Purpose.REGISTER
            )

    def test_verify_otp_increments_attempts_on_failure(self):
        """Failed OTP attempts must persist so rate limits are enforceable."""
        user = UserFactory()
        self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)

        with pytest.raises(BadRequestError, match="Invalid OTP code"):
            self.service.verify_otp(
                user=user, plain_code="000000", purpose=OTPToken.Purpose.REGISTER
            )

        token = OTPToken.objects.get(user=user, purpose="register", used=False)
        assert token.attempts == 1

    def test_verify_otp_shows_remaining_attempts(self):
        user = UserFactory()
        self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)

        with pytest.raises(BadRequestError, match="4 attempt\\(s\\) remaining"):
            self.service.verify_otp(
                user=user, plain_code="000000", purpose=OTPToken.Purpose.REGISTER
            )

    def test_verify_otp_max_attempts_exceeded(self):
        user = UserFactory()
        code = self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)
        OTPToken.objects.filter(user=user, purpose="register", used=False).update(
            attempts=OTPToken.MAX_ATTEMPTS
        )

        with pytest.raises(BadRequestError, match="Maximum verification attempts"):
            self.service.verify_otp(
                user=user, plain_code=code, purpose=OTPToken.Purpose.REGISTER
            )

    def test_verify_otp_locks_after_final_failed_attempt(self):
        user = UserFactory()
        code = self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)
        OTPToken.objects.filter(user=user, purpose="register", used=False).update(
            attempts=OTPToken.MAX_ATTEMPTS - 1
        )

        with pytest.raises(BadRequestError, match="0 attempt\\(s\\) remaining"):
            self.service.verify_otp(
                user=user, plain_code="000000", purpose=OTPToken.Purpose.REGISTER
            )

        with pytest.raises(BadRequestError, match="Maximum verification attempts"):
            self.service.verify_otp(
                user=user, plain_code=code, purpose=OTPToken.Purpose.REGISTER
            )

    def test_verify_otp_expired(self):
        user = UserFactory()
        code = self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)
        OTPToken.objects.filter(user=user, purpose="register", used=False).update(
            expires_at=timezone.now() - datetime.timedelta(minutes=1)
        )

        with pytest.raises(BadRequestError, match="OTP has expired"):
            self.service.verify_otp(
                user=user, plain_code=code, purpose=OTPToken.Purpose.REGISTER
            )

    def test_verify_otp_no_active_token(self):
        user = UserFactory()

        with pytest.raises(BadRequestError, match="No active OTP found"):
            self.service.verify_otp(
                user=user, plain_code="123456", purpose=OTPToken.Purpose.REGISTER
            )

    def test_invalidate_user_otps(self):
        user = UserFactory()
        self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)
        self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)
        unused = OTPToken.objects.filter(user=user, purpose="register", used=False)
        assert unused.count() == 1
        count = self.service.invalidate_user_otps(
            user=user, purpose=OTPToken.Purpose.REGISTER
        )
        assert count == 1
        unused = OTPToken.objects.filter(user=user, purpose="register", used=False)
        assert unused.count() == 0

    def test_verify_otp_different_purpose_not_found(self):
        user = UserFactory()
        self.service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)

        with pytest.raises(BadRequestError, match="No active OTP found"):
            self.service.verify_otp(
                user=user, plain_code="123456", purpose=OTPToken.Purpose.PASSWORD_RESET
            )


@pytest.mark.django_db
class TestUserService:
    """Tests for UserService: register, profile, update, search."""

    def setup_method(self):
        self.service = UserService()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_register_user_success(self, mock_send_email):
        data = {
            "email": "new@example.com",
            "password": "TestPass1!",
            "full_name": "New User",
            "date_of_birth": datetime.date(1995, 6, 15),
            "gender": "male",
            "country": "US",
        }
        user = self.service.register_user(validated_data=data)
        assert user.email == "new@example.com"
        assert user.full_name == "New User"
        assert user.check_password("TestPass1!")
        assert user.is_email_verified is False
        mock_send_email.assert_called_once()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_register_user_creates_otp(self, mock_send_email):
        data = {
            "email": "otp@example.com",
            "password": "TestPass1!",
            "full_name": "OTP User",
            "date_of_birth": datetime.date(1995, 6, 15),
            "gender": "female",
            "country": "UK",
        }
        user = self.service.register_user(validated_data=data)
        assert OTPToken.objects.filter(user=user, purpose="register").exists()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_register_user_duplicate_email_raises_conflict(self, mock_send_email):
        UserFactory(email="existing@example.com")
        data = {
            "email": "existing@example.com",
            "password": "TestPass1!",
            "full_name": "Duplicate",
            "date_of_birth": datetime.date(1995, 6, 15),
            "gender": "male",
            "country": "US",
        }

        with pytest.raises(ConflictError, match="already exists"):
            self.service.register_user(validated_data=data)

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_register_user_email_case_insensitive(self, mock_send_email):
        UserFactory(email="case@example.com")
        data = {
            "email": "CASE@example.com",
            "password": "TestPass1!",
            "full_name": "Case Test",
            "date_of_birth": datetime.date(1995, 6, 15),
            "gender": "male",
            "country": "US",
        }

        with pytest.raises(ConflictError, match="already exists"):
            self.service.register_user(validated_data=data)

    def test_get_profile_existing_user(self):
        user = UserFactory()
        profile = self.service.get_profile(user_id=user.id)
        assert profile.id == user.id
        assert profile.full_name == user.full_name

    def test_get_profile_annotated_counts(self):
        user = UserFactory()
        profile = self.service.get_profile(user_id=user.id)
        assert hasattr(profile, "follower_count")
        assert hasattr(profile, "following_count")
        assert profile.follower_count == 0
        assert profile.following_count == 0

    def test_get_profile_nonexistent_user(self):
        with pytest.raises(NotFoundError, match="not found"):
            self.service.get_profile(user_id=uuid4())

    def test_get_profile_inactive_user(self):
        user = UserFactory(is_active=False)

        with pytest.raises(NotFoundError):
            self.service.get_profile(user_id=user.id)

    def test_update_profile_allowed_fields(self):
        user = UserFactory()
        updated = self.service.update_profile(
            user=user,
            validated_data={"full_name": "Updated Name", "bio": "New bio"},
        )
        assert updated.full_name == "Updated Name"
        assert updated.bio == "New bio"

    def test_update_profile_email_immutable(self):
        user = UserFactory(email="orig@test.com")
        updated = self.service.update_profile(
            user=user,
            validated_data={"email": "changed@test.com", "full_name": "Changed"},
        )
        assert updated.email == "orig@test.com"
        assert updated.full_name == "Changed"

    def test_update_profile_no_valid_fields_raises(self):
        user = UserFactory()

        with pytest.raises(BadRequestError, match="No valid fields"):
            self.service.update_profile(
                user=user,
                validated_data={"email": "changed@test.com"},
            )

    def test_update_profile_disallowed_field_ignored(self):
        user = UserFactory()
        updated = self.service.update_profile(
            user=user,
            validated_data={
                "full_name": "Valid",
                "is_staff": True,
            },
        )
        assert updated.full_name == "Valid"
        assert updated.is_staff is False

    def test_search_users_by_name(self):
        UserFactory(full_name="Alice Wonder", is_email_verified=True)
        UserFactory(full_name="Bob Builder", is_email_verified=True)
        results = self.service.search_users(query="Alice")
        assert results.count() == 1
        assert results.first().full_name == "Alice Wonder"

    def test_search_users_case_insensitive(self):
        UserFactory(full_name="Alice Wonder", is_email_verified=True)
        results = self.service.search_users(query="alice")
        assert results.count() == 1

    def test_search_users_by_country(self):
        UserFactory(full_name="US User", country="US", is_email_verified=True)
        UserFactory(full_name="UK User", country="UK", is_email_verified=True)
        results = self.service.search_users(query="", country="US")
        assert results.count() == 1
        assert results.first().country == "US"

    def test_search_users_excludes_unverified(self):
        UserFactory(full_name="Unverified", is_email_verified=False)
        results = self.service.search_users(query="Unverified")
        assert results.count() == 0

    def test_search_users_excludes_inactive(self):
        UserFactory(full_name="Inactive", is_active=False, is_email_verified=True)
        results = self.service.search_users(query="Inactive")
        assert results.count() == 0

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_resend_verification_otp_for_unverified_user(self, mock_send):
        user = UserFactory(is_email_verified=False)
        self.service.resend_verification_otp(email=user.email)
        mock_send.assert_called_once()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_resend_verification_otp_silent_for_verified_user(self, mock_send):
        user = UserFactory(is_email_verified=True)
        self.service.resend_verification_otp(email=user.email)
        mock_send.assert_not_called()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_resend_verification_otp_silent_for_nonexistent_email(self, mock_send):
        self.service.resend_verification_otp(email="ghost@example.com")
        mock_send.assert_not_called()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_resend_verification_otp_silent_for_inactive_user(self, mock_send):
        user = UserFactory(is_active=False, is_email_verified=False)
        self.service.resend_verification_otp(email=user.email)
        mock_send.assert_not_called()


@pytest.mark.django_db
class TestAuthService:
    """Tests for AuthService: login, logout, token refresh, password, email verify."""

    def setup_method(self):
        self.service = AuthService()

    def test_login_success(self):
        user = UserFactory(is_email_verified=True)
        tokens = self.service.login(email=user.email, password="TestPass1!")
        assert "access" in tokens
        assert "refresh" in tokens
        assert "user_id" in tokens
        assert tokens["user_id"] == str(user.id)

    def test_login_invalid_password(self):
        user = UserFactory(is_email_verified=True)

        with pytest.raises(BadRequestError, match="Invalid email or password"):
            self.service.login(email=user.email, password="WrongPassword1!")

    def test_login_nonexistent_email(self):
        with pytest.raises(BadRequestError, match="Invalid email or password"):
            self.service.login(email="ghost@test.com", password="Whatever1!")

    def test_login_unverified_email(self):
        user = UserFactory(is_email_verified=False)

        with pytest.raises(BadRequestError, match="verify your email"):
            self.service.login(email=user.email, password="TestPass1!")

    def test_login_inactive_account(self):
        user = UserFactory(is_active=False, is_email_verified=True)

        with pytest.raises(BadRequestError, match="Invalid email or password"):
            self.service.login(email=user.email, password="TestPass1!")

    def test_refresh_token_success(self):
        user = UserFactory()
        refresh = RefreshToken.for_user(user)
        tokens = self.service.refresh_token(str(refresh))
        assert "access" in tokens
        assert "refresh" in tokens

    def test_refresh_token_invalid(self):
        with pytest.raises(BadRequestError, match="Invalid or expired refresh token"):
            self.service.refresh_token("invalid-token-string")

    def test_logout_success(self):
        user = UserFactory()
        refresh = RefreshToken.for_user(user)
        self.service.logout(str(refresh))

        with pytest.raises(BadRequestError, match="Invalid refresh token"):
            self.service.logout(str(refresh))

    def test_logout_invalid_token(self):
        with pytest.raises(BadRequestError, match="Invalid refresh token"):
            self.service.logout("invalid-token")

    def test_verify_email_otp_success(self):
        user = UserFactory(is_email_verified=False)
        otp_service = OTPService()
        code = otp_service.create_otp(user=user, purpose=OTPToken.Purpose.REGISTER)
        verified_user = self.service.verify_email_otp(email=user.email, otp_code=code)
        assert verified_user.is_email_verified is True

    def test_verify_email_already_verified_raises_conflict(self):
        user = UserFactory(is_email_verified=True)

        with pytest.raises(ConflictError, match="already verified"):
            self.service.verify_email_otp(email=user.email, otp_code="123456")

    def test_verify_email_nonexistent_user_raises(self):
        with pytest.raises(NotFoundError, match="No active account"):
            self.service.verify_email_otp(email="ghost@example.com", otp_code="123456")

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_request_password_reset_sends_otp(self, mock_send):
        user = UserFactory(is_email_verified=True)
        self.service.request_password_reset(email=user.email)
        mock_send.assert_called_once()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_request_password_reset_nonexistent_email_silent(self, mock_send):
        self.service.request_password_reset(email="ghost@example.com")
        mock_send.assert_not_called()

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_confirm_password_reset_success(self, mock_send):
        user = UserFactory(is_email_verified=True)
        otp_service = OTPService()
        code = otp_service.create_otp(
            user=user, purpose=OTPToken.Purpose.PASSWORD_RESET
        )
        self.service.confirm_password_reset(
            email=user.email, otp_code=code, new_password="NewPass1!"
        )
        user.refresh_from_db()
        assert user.check_password("NewPass1!")

    @patch("apps.accounts.services._dispatch_otp_email")
    def test_confirm_password_reset_invalidates_sessions(self, mock_send):
        user = UserFactory(is_email_verified=True)
        refresh = RefreshToken.for_user(user)
        otp_service = OTPService()
        code = otp_service.create_otp(
            user=user, purpose=OTPToken.Purpose.PASSWORD_RESET
        )
        self.service.confirm_password_reset(
            email=user.email, otp_code=code, new_password="NewPass1!"
        )

        with pytest.raises(BadRequestError):
            self.service.refresh_token(str(refresh))

    def test_change_password_success(self):
        user = UserFactory()
        self.service.change_password(
            user=user, old_password="TestPass1!", new_password="NewPass1!"
        )
        user.refresh_from_db()
        assert user.check_password("NewPass1!")

    def test_change_password_wrong_old_password(self):
        user = UserFactory()

        with pytest.raises(BadRequestError, match="Current password is incorrect"):
            self.service.change_password(
                user=user, old_password="WrongPass1!", new_password="NewPass1!"
            )

    def test_change_password_invalidates_sessions(self):
        user = UserFactory()
        refresh = RefreshToken.for_user(user)
        self.service.change_password(
            user=user, old_password="TestPass1!", new_password="NewPass1!"
        )

        with pytest.raises(BadRequestError):
            self.service.refresh_token(str(refresh))


@pytest.mark.django_db
class TestFollowService:
    """Tests for FollowService: follow, unfollow, listings, counts."""

    def setup_method(self):
        self.service = FollowService()

    def test_follow_user_accepted(self):
        follower = UserFactory()
        target = UserFactory()
        self.service.follow_user(follower=follower, target_id=target.id)
        assert FollowRelationship.objects.filter(
            follower=follower, following=target
        ).exists()

    def test_follow_self_raises(self):
        user = UserFactory()

        with pytest.raises(BadRequestError, match="cannot follow yourself"):
            self.service.follow_user(follower=user, target_id=user.id)

    def test_follow_nonexistent_user_raises(self):
        user = UserFactory()

        with pytest.raises(NotFoundError, match="User not found"):
            self.service.follow_user(follower=user, target_id=uuid4())

    def test_follow_blocked_user_raises(self):
        follower = UserFactory()
        target = UserFactory()
        BlockRelationshipFactory(blocker=target, blocked=follower)

        with pytest.raises(ForbiddenError, match="not allowed"):
            self.service.follow_user(follower=follower, target_id=target.id)

    def test_follow_user_who_blocked_you_raises(self):
        follower = UserFactory()
        target = UserFactory()
        BlockRelationshipFactory(blocker=follower, blocked=target)

        with pytest.raises(ForbiddenError, match="not allowed"):
            self.service.follow_user(follower=follower, target_id=target.id)

    def test_double_follow_raises_conflict(self):
        follower = UserFactory()
        target = UserFactory()
        self.service.follow_user(follower=follower, target_id=target.id)

        with pytest.raises(ConflictError, match="already follow"):
            self.service.follow_user(follower=follower, target_id=target.id)

    def test_follow_inactive_user_raises(self):
        follower = UserFactory()
        target = UserFactory(is_active=False)

        with pytest.raises(NotFoundError, match="User not found"):
            self.service.follow_user(follower=follower, target_id=target.id)

    def test_unfollow_user_success(self):
        follower = UserFactory()
        target = UserFactory()
        FollowRelationshipFactory(follower=follower, following=target)
        self.service.unfollow_user(follower=follower, target_id=target.id)
        assert not FollowRelationship.objects.filter(
            follower=follower, following=target
        ).exists()

    def test_unfollow_not_following_raises(self):
        follower = UserFactory()
        target = UserFactory()

        with pytest.raises(NotFoundError, match="not following"):
            self.service.unfollow_user(follower=follower, target_id=target.id)

    def test_get_followers(self):
        target = UserFactory()
        follower1 = UserFactory()
        follower2 = UserFactory()
        FollowRelationshipFactory(follower=follower1, following=target)
        FollowRelationshipFactory(follower=follower2, following=target)
        followers = self.service.get_followers(user_id=target.id)
        assert followers.count() == 2

    def test_get_following(self):
        user = UserFactory()
        target1 = UserFactory()
        target2 = UserFactory()
        FollowRelationshipFactory(follower=user, following=target1)
        FollowRelationshipFactory(follower=user, following=target2)
        following = self.service.get_following(user_id=user.id)
        assert following.count() == 2

    def test_get_follower_count(self):
        target = UserFactory()
        follower1 = UserFactory()
        follower2 = UserFactory()
        FollowRelationshipFactory(follower=follower1, following=target)
        FollowRelationshipFactory(follower=follower2, following=target)
        assert self.service.get_follower_count(user_id=target.id) == 2

    def test_get_following_count(self):
        user = UserFactory()
        target1 = UserFactory()
        target2 = UserFactory()
        FollowRelationshipFactory(follower=user, following=target1)
        FollowRelationshipFactory(follower=user, following=target2)
        assert self.service.get_following_count(user_id=user.id) == 2


@pytest.mark.django_db
class TestBlockService:
    """Tests for BlockService: block, unblock, blocked list, is_blocked."""

    def setup_method(self):
        self.service = BlockService()

    def test_block_user_success(self):
        blocker = UserFactory()
        target = UserFactory()
        rel = self.service.block_user(blocker=blocker, target_id=target.id)
        assert rel.blocker == blocker
        assert rel.blocked == target

    def test_block_self_raises(self):
        user = UserFactory()

        with pytest.raises(BadRequestError, match="cannot block yourself"):
            self.service.block_user(blocker=user, target_id=user.id)

    def test_block_nonexistent_user_raises(self):
        user = UserFactory()

        with pytest.raises(NotFoundError, match="User not found"):
            self.service.block_user(blocker=user, target_id=uuid4())

    def test_double_block_raises_conflict(self):
        blocker = UserFactory()
        target = UserFactory()
        self.service.block_user(blocker=blocker, target_id=target.id)

        with pytest.raises(ConflictError, match="already blocked"):
            self.service.block_user(blocker=blocker, target_id=target.id)

    def test_block_inactive_user_raises(self):
        blocker = UserFactory()
        target = UserFactory(is_active=False)

        with pytest.raises(NotFoundError, match="User not found"):
            self.service.block_user(blocker=blocker, target_id=target.id)

    def test_unblock_user_success(self):
        blocker = UserFactory()
        target = UserFactory()
        BlockRelationshipFactory(blocker=blocker, blocked=target)
        self.service.unblock_user(blocker=blocker, target_id=target.id)
        assert not BlockRelationship.objects.filter(
            blocker=blocker, blocked=target
        ).exists()

    def test_unblock_not_blocked_raises(self):
        blocker = UserFactory()
        target = UserFactory()

        with pytest.raises(NotFoundError, match="not blocked"):
            self.service.unblock_user(blocker=blocker, target_id=target.id)

    def test_get_blocked_users(self):
        blocker = UserFactory()
        target1 = UserFactory()
        target2 = UserFactory()
        BlockRelationshipFactory(blocker=blocker, blocked=target1)
        BlockRelationshipFactory(blocker=blocker, blocked=target2)
        blocked = self.service.get_blocked_users(user_id=blocker.id)
        assert blocked.count() == 2

    def test_is_blocked_forward(self):
        user_a = UserFactory()
        user_b = UserFactory()
        BlockRelationshipFactory(blocker=user_a, blocked=user_b)
        assert self.service.is_blocked(user_a_id=user_a.id, user_b_id=user_b.id) is True

    def test_is_blocked_reverse(self):
        user_a = UserFactory()
        user_b = UserFactory()
        BlockRelationshipFactory(blocker=user_b, blocked=user_a)
        assert self.service.is_blocked(user_a_id=user_a.id, user_b_id=user_b.id) is True

    def test_is_not_blocked(self):
        user_a = UserFactory()
        user_b = UserFactory()
        assert (
            self.service.is_blocked(user_a_id=user_a.id, user_b_id=user_b.id) is False
        )

    def test_block_removes_follow_relationships(self):
        """Blocking should remove any existing follow relationships (via signal)."""
        blocker = UserFactory()
        target = UserFactory()
        FollowRelationshipFactory(follower=blocker, following=target)
        FollowRelationshipFactory(follower=target, following=blocker)
        self.service.block_user(blocker=blocker, target_id=target.id)
        assert (
            FollowRelationship.objects.filter(
                follower=blocker, following=target
            ).count()
            == 0
        )
        assert (
            FollowRelationship.objects.filter(
                follower=target, following=blocker
            ).count()
            == 0
        )
