"""Tests for accounts app models: User, FollowRelationship, BlockRelationship, OTPToken."""

from __future__ import annotations

import datetime

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import (
    BlockRelationship,
    FollowRelationship,
    OTPToken,
    User,
)
from conftest import (
    BlockRelationshipFactory,
    FollowRelationshipFactory,
    OTPTokenFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestCustomUserManager:
    """Tests for CustomUserManager.create_user and create_superuser."""

    def test_create_user_with_valid_data(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="TestPass1!",
            full_name="John Doe",
            date_of_birth=datetime.date(1995, 6, 15),
            gender="male",
            country="US",
        )
        assert user.email == "test@example.com"
        assert user.full_name == "John Doe"
        assert user.check_password("TestPass1!")
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_create_user_normalizes_email(self):
        user = User.objects.create_user(
            email="Test@EXAMPLE.COM",
            password="TestPass1!",
            full_name="Jane Doe",
            date_of_birth=datetime.date(1995, 6, 15),
            gender="female",
            country="US",
        )
        assert user.email == "Test@example.com"

    def test_create_user_without_email_raises_value_error(self):
        with pytest.raises(ValueError, match="Email field is required"):
            User.objects.create_user(
                email="",
                password="TestPass1!",
                full_name="No Email",
                date_of_birth=datetime.date(1995, 6, 15),
                gender="male",
                country="US",
            )

    def test_create_user_without_password_sets_unusable(self):
        user = User.objects.create_user(
            email="nopass@example.com",
            password=None,
            full_name="No Password",
            date_of_birth=datetime.date(1995, 6, 15),
            gender="male",
            country="US",
        )
        assert user.has_usable_password() is False

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPass1!",
            full_name="Admin User",
            date_of_birth=datetime.date(1990, 1, 1),
            gender="male",
            country="US",
        )
        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.is_active is True

    def test_create_superuser_is_staff_false_raises(self):
        with pytest.raises(ValueError, match="is_staff=True"):
            User.objects.create_superuser(
                email="admin2@example.com",
                password="AdminPass1!",
                full_name="Admin",
                date_of_birth=datetime.date(1990, 1, 1),
                gender="male",
                country="US",
                is_staff=False,
            )

    def test_create_superuser_is_superuser_false_raises(self):
        with pytest.raises(ValueError, match="is_superuser=True"):
            User.objects.create_superuser(
                email="admin3@example.com",
                password="AdminPass1!",
                full_name="Admin",
                date_of_birth=datetime.date(1990, 1, 1),
                gender="male",
                country="US",
                is_superuser=False,
            )

    def test_duplicate_email_raises_integrity_error(self):
        User.objects.create_user(
            email="dup@example.com",
            password="TestPass1!",
            full_name="First",
            date_of_birth=datetime.date(1995, 1, 1),
            gender="male",
            country="US",
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email="dup@example.com",
                password="TestPass1!",
                full_name="Second",
                date_of_birth=datetime.date(1995, 1, 1),
                gender="male",
                country="US",
            )


@pytest.mark.django_db
class TestUserModel:
    """Tests for the User model fields, properties, and constraints."""

    def test_str_representation(self):
        user = UserFactory(full_name="Alice Smith", email="alice@test.com")
        assert str(user) == "Alice Smith (alice@test.com)"

    def test_username_field_is_email(self):
        assert User.USERNAME_FIELD == "email"

    def test_required_fields(self):
        assert "full_name" in User.REQUIRED_FIELDS
        assert "date_of_birth" in User.REQUIRED_FIELDS
        assert "gender" in User.REQUIRED_FIELDS

    def test_default_values(self):
        user = UserFactory()
        assert user.preferred_language == "en"
        assert user.is_active is True
        assert user.is_staff is False
        assert user.bio == ""
        assert user.phone_number == ""

    def test_age_property(self):
        today = timezone.now().date()
        dob = today.replace(year=today.year - 25)
        user = UserFactory(date_of_birth=dob)
        assert user.age == 25

    def test_age_property_birthday_not_yet(self):
        """Test age when birthday has not occurred this year yet."""
        today = timezone.now().date()
        future_day = today + datetime.timedelta(days=30)
        dob = future_day.replace(year=future_day.year - 25)
        user = UserFactory(date_of_birth=dob)
        assert user.age == 24

    def test_gender_choices(self):
        choices = [c[0] for c in User.Gender.choices]
        assert "male" in choices
        assert "female" in choices
        assert "prefer_not_to_say" in choices

    def test_uuid_primary_key(self):
        user = UserFactory()
        assert user.pk is not None
        assert len(str(user.pk)) == 36

    def test_ordering_by_date_joined_desc(self):
        assert User._meta.ordering == ["-date_joined"]


@pytest.mark.django_db
class TestFollowRelationshipModel:
    """Tests for the FollowRelationship model constraints and behavior."""

    def test_create_follow(self):
        rel = FollowRelationshipFactory()
        assert rel.follower != rel.following

    def test_str_representation(self):
        rel = FollowRelationshipFactory()
        expected = f"{rel.follower} \u2192 {rel.following}"
        assert str(rel) == expected

    def test_unique_follow_constraint(self):
        user_a = UserFactory()
        user_b = UserFactory()
        FollowRelationshipFactory(follower=user_a, following=user_b)
        with pytest.raises(IntegrityError):
            FollowRelationshipFactory(follower=user_a, following=user_b)

    def test_self_follow_constraint(self):
        user = UserFactory()
        with pytest.raises(IntegrityError):
            FollowRelationship.objects.create(
                follower=user, following=user,
            )

    def test_ordering_by_created_at_desc(self):
        assert FollowRelationship._meta.ordering == ["-created_at"]

    def test_related_names(self):
        user_a = UserFactory()
        user_b = UserFactory()
        FollowRelationshipFactory(follower=user_a, following=user_b)

        assert user_a.following_relationships.count() == 1
        assert user_b.follower_relationships.count() == 1

    def test_cascade_delete_follower(self):
        rel = FollowRelationshipFactory()
        follower_id = rel.follower.id
        rel.follower.delete()
        assert FollowRelationship.objects.filter(follower_id=follower_id).count() == 0

    def test_cascade_delete_following(self):
        rel = FollowRelationshipFactory()
        following_id = rel.following.id
        rel.following.delete()
        assert FollowRelationship.objects.filter(following_id=following_id).count() == 0


@pytest.mark.django_db
class TestBlockRelationshipModel:
    """Tests for the BlockRelationship model constraints and behavior."""

    def test_create_block(self):
        rel = BlockRelationshipFactory()
        assert rel.blocker is not None
        assert rel.blocked is not None
        assert rel.blocker != rel.blocked

    def test_str_representation(self):
        rel = BlockRelationshipFactory()
        assert str(rel) == f"{rel.blocker} blocked {rel.blocked}"

    def test_unique_block_constraint(self):
        user_a = UserFactory()
        user_b = UserFactory()
        BlockRelationshipFactory(blocker=user_a, blocked=user_b)
        with pytest.raises(IntegrityError):
            BlockRelationshipFactory(blocker=user_a, blocked=user_b)

    def test_self_block_constraint(self):
        user = UserFactory()
        with pytest.raises(IntegrityError):
            BlockRelationship.objects.create(blocker=user, blocked=user)

    def test_ordering_by_created_at_desc(self):
        assert BlockRelationship._meta.ordering == ["-created_at"]

    def test_related_names(self):
        user_a = UserFactory()
        user_b = UserFactory()
        BlockRelationshipFactory(blocker=user_a, blocked=user_b)

        assert user_a.blocking_relationships.count() == 1
        assert user_b.blocked_by_relationships.count() == 1

    def test_blocking_removes_follow_relationships_via_signal(self):
        """Test the post_save signal removes follows when a block is created."""
        user_a = UserFactory()
        user_b = UserFactory()
        FollowRelationshipFactory(follower=user_a, following=user_b)
        FollowRelationshipFactory(follower=user_b, following=user_a)

        assert FollowRelationship.objects.filter(
            follower=user_a, following=user_b
        ).exists()

        BlockRelationshipFactory(blocker=user_a, blocked=user_b)

        assert not FollowRelationship.objects.filter(
            follower=user_a, following=user_b
        ).exists()
        assert not FollowRelationship.objects.filter(
            follower=user_b, following=user_a
        ).exists()

    def test_cascade_delete_blocker(self):
        rel = BlockRelationshipFactory()
        blocker_id = rel.blocker.id
        rel.blocker.delete()
        assert BlockRelationship.objects.filter(blocker_id=blocker_id).count() == 0

    def test_asymmetric_block_allowed(self):
        """User A blocks B does not prevent B from blocking A."""
        user_a = UserFactory()
        user_b = UserFactory()
        BlockRelationshipFactory(blocker=user_a, blocked=user_b)
        BlockRelationshipFactory(blocker=user_b, blocked=user_a)
        assert BlockRelationship.objects.count() == 2


@pytest.mark.django_db
class TestOTPTokenModel:
    """Tests for the OTPToken model fields and properties."""

    def test_create_otp_token(self):
        otp = OTPTokenFactory()
        assert otp.used is False
        assert otp.attempts == 0
        assert otp.purpose == "register"

    def test_str_representation(self):
        otp = OTPTokenFactory()
        assert str(otp) == f"OTP for {otp.user.email} ({otp.purpose})"

    def test_purpose_choices(self):
        choices = [c[0] for c in OTPToken.Purpose.choices]
        assert "register" in choices
        assert "password_reset" in choices

    def test_is_expired_false_when_valid(self):
        otp = OTPTokenFactory(
            expires_at=timezone.now() + datetime.timedelta(minutes=10)
        )
        assert otp.is_expired is False

    def test_is_expired_true_when_past(self):
        otp = OTPTokenFactory(
            expires_at=timezone.now() - datetime.timedelta(minutes=1)
        )
        assert otp.is_expired is True

    def test_is_max_attempts_false_when_below(self):
        otp = OTPTokenFactory(attempts=4)
        assert otp.is_max_attempts is False

    def test_is_max_attempts_true_when_at_limit(self):
        otp = OTPTokenFactory(attempts=5)
        assert otp.is_max_attempts is True

    def test_is_max_attempts_true_when_above_limit(self):
        otp = OTPTokenFactory(attempts=10)
        assert otp.is_max_attempts is True

    def test_max_attempts_constant(self):
        assert OTPToken.MAX_ATTEMPTS == 5

    def test_ordering_by_created_at_desc(self):
        assert OTPToken._meta.ordering == ["-created_at"]

    def test_cascade_delete_user(self):
        otp = OTPTokenFactory()
        user_id = otp.user.id
        otp.user.delete()
        assert OTPToken.objects.filter(user_id=user_id).count() == 0

    def test_multiple_otps_per_user(self):
        user = UserFactory()
        OTPTokenFactory(user=user, purpose="register")
        OTPTokenFactory(user=user, purpose="password_reset")
        assert OTPToken.objects.filter(user=user).count() == 2
