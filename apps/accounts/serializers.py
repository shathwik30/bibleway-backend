from __future__ import annotations

from django.core.validators import RegexValidator
from rest_framework import serializers

from apps.common.serializers import BaseModelSerializer

from .models import BlockRelationship, FollowRelationship, User
from .validators import validate_password_strength


# ── Validators ─────────────────────────────────────────────────────────

otp_digit_validator = RegexValidator(
    regex=r"^\d{6}$",
    message="OTP code must be exactly 6 digits.",
)


# ── Registration & Login ─────────────────────────────────────────────


class UserRegistrationSerializer(serializers.Serializer):
    """Validates registration input. Password must meet strength requirements."""

    email = serializers.EmailField(max_length=255)
    password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    full_name = serializers.CharField(max_length=150)
    date_of_birth = serializers.DateField()
    gender = serializers.ChoiceField(choices=User.Gender.choices)
    preferred_language = serializers.CharField(max_length=10, default="en")
    country = serializers.CharField(max_length=100)
    phone_number = serializers.CharField(max_length=20, required=False, default="")

    def validate_password(self, value: str) -> str:
        validate_password_strength(value)
        return value

    def validate_email(self, value: str) -> str:
        return value.lower().strip()


class UserLoginSerializer(serializers.Serializer):
    """Validates login credentials."""

    email = serializers.EmailField(max_length=255)
    password = serializers.CharField(write_only=True)


# ── User Profile ─────────────────────────────────────────────────────


class UserProfileSerializer(BaseModelSerializer):
    """Context-aware profile serializer.

    When viewing own profile: all fields including PII.
    When viewing another user's profile: PII fields excluded.
    """

    age = serializers.IntegerField(read_only=True)
    follower_count = serializers.IntegerField(read_only=True, default=0)
    following_count = serializers.IntegerField(read_only=True, default=0)
    post_count = serializers.IntegerField(read_only=True, default=0)
    prayer_count = serializers.IntegerField(read_only=True, default=0)

    PRIVATE_FIELDS = {"email", "phone_number", "date_of_birth", "is_email_verified"}

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "date_of_birth",
            "gender",
            "preferred_language",
            "country",
            "phone_number",
            "profile_photo",
            "bio",
            "account_visibility",
            "hide_followers_list",
            "is_email_verified",
            "date_joined",
            "age",
            "follower_count",
            "following_count",
            "post_count",
            "prayer_count",
        ]
        read_only_fields = fields

    def get_fields(self):
        fields = super().get_fields()
        request_user = self.context.get("user")
        if request_user and hasattr(self, "instance") and self.instance:
            viewing_own = (
                not isinstance(self.instance, list)
                and request_user.id == self.instance.id
            )
            if not viewing_own:
                for field_name in self.PRIVATE_FIELDS:
                    fields.pop(field_name, None)
        return fields


class UserUpdateSerializer(serializers.Serializer):
    """Writable fields for profile updates. Email is excluded (immutable)."""

    full_name = serializers.CharField(max_length=150, required=False)
    bio = serializers.CharField(max_length=250, required=False, allow_blank=True)
    profile_photo = serializers.ImageField(required=False, allow_null=True)
    preferred_language = serializers.CharField(max_length=10, required=False)
    country = serializers.CharField(max_length=100, required=False)
    phone_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )


class UserListSerializer(BaseModelSerializer):
    """Minimal user representation for lists and search results."""

    class Meta:
        model = User
        fields = ["id", "full_name", "profile_photo", "bio"]
        read_only_fields = fields


# ── Follow Relationships ─────────────────────────────────────────────


class FollowRelationshipSerializer(BaseModelSerializer):
    """Serializer for follow relationships with nested user data."""

    follower = UserListSerializer(read_only=True)
    following = UserListSerializer(read_only=True)

    class Meta:
        model = FollowRelationship
        fields = ["id", "follower", "following", "status", "created_at"]
        read_only_fields = fields


# ── Block Relationships ──────────────────────────────────────────────


class BlockRelationshipSerializer(BaseModelSerializer):
    """Serializer for block relationships."""

    blocked = UserListSerializer(read_only=True)

    class Meta:
        model = BlockRelationship
        fields = ["id", "blocked", "created_at"]
        read_only_fields = fields


# ── OTP & Password ──────────────────────────────────────────────────


class OTPVerifySerializer(serializers.Serializer):
    """Validates OTP verification input."""

    email = serializers.EmailField(max_length=255)
    otp_code = serializers.CharField(
        min_length=6, max_length=6, validators=[otp_digit_validator]
    )


class PasswordResetRequestSerializer(serializers.Serializer):
    """Validates password reset request — email only."""

    email = serializers.EmailField(max_length=255)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Validates password reset confirmation with OTP and new password."""

    email = serializers.EmailField(max_length=255)
    otp_code = serializers.CharField(
        min_length=6, max_length=6, validators=[otp_digit_validator]
    )
    new_password = serializers.CharField(write_only=True, min_length=8, max_length=128)

    def validate_new_password(self, value: str) -> str:
        validate_password_strength(value)
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Validates password change for authenticated users."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8, max_length=128)

    def validate_new_password(self, value: str) -> str:
        validate_password_strength(value)
        return value


class PrivacySettingsSerializer(serializers.Serializer):
    """Validates privacy settings update."""

    account_visibility = serializers.ChoiceField(
        choices=User.AccountVisibility.choices, required=False
    )
    hide_followers_list = serializers.BooleanField(required=False)


class ResendOTPSerializer(serializers.Serializer):
    """Validates resend OTP request."""

    email = serializers.EmailField(max_length=255)
