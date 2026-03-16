from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.common.models import CreatedAtModel, UUIDModel
from apps.common.validators import validate_bio_length

from .managers import CustomUserManager


def profile_photo_upload_path(instance, filename):
    return f"profiles/{instance.id}/{filename}"


class User(AbstractBaseUser, PermissionsMixin, UUIDModel):
    """Custom user model. Email is the immutable primary identifier."""

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        PREFER_NOT_TO_SAY = "prefer_not_to_say", "Prefer Not to Say"

    class AccountVisibility(models.TextChoices):
        PUBLIC = "public", "Public"
        PRIVATE = "private", "Private"

    # ── Core fields ─────────────────────────────────────────────
    email = models.EmailField(
        unique=True,
        max_length=255,
        help_text="Immutable primary identifier. Cannot be changed after registration.",
    )
    full_name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20, choices=Gender.choices)
    preferred_language = models.CharField(
        max_length=10,
        default="en",
        help_text="ISO 639-1 language code (e.g., en, es, fr, pt, hi, ar, sw).",
    )
    country = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True, default="")

    # ── Profile fields ──────────────────────────────────────────
    profile_photo = models.ImageField(
        upload_to=profile_photo_upload_path,
        blank=True,
        default="",
    )
    bio = models.CharField(
        max_length=250,
        blank=True,
        default="",
        validators=[validate_bio_length],
    )
    account_visibility = models.CharField(
        max_length=10,
        choices=AccountVisibility.choices,
        default=AccountVisibility.PUBLIC,
    )
    hide_followers_list = models.BooleanField(default=False)

    # ── Django auth fields ──────────────────────────────────────
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name", "date_of_birth", "gender"]

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["country"]),
            models.Index(fields=["preferred_language"]),
            models.Index(fields=["date_of_birth"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    @property
    def age(self):
        today = timezone.now().date()
        born = self.date_of_birth
        return today.year - born.year - (
            (today.month, today.day) < (born.month, born.day)
        )


class FollowRelationship(CreatedAtModel):
    """Asymmetric follow. Pending status if target account is private."""

    class Status(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        PENDING = "pending", "Pending"

    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="following_relationships",
    )
    following = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="follower_relationships",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACCEPTED,
    )

    class Meta:
        verbose_name = "follow relationship"
        verbose_name_plural = "follow relationships"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "following"],
                name="unique_follow_relationship",
            ),
            models.CheckConstraint(
                condition=~models.Q(follower=models.F("following")),
                name="prevent_self_follow",
            ),
        ]
        indexes = [
            models.Index(fields=["follower", "status"]),
            models.Index(fields=["following", "status"]),
        ]

    def __str__(self):
        return f"{self.follower} → {self.following} ({self.status})"


class BlockRelationship(CreatedAtModel):
    """Block relationship. Blocking is immediate and silent."""

    blocker = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blocking_relationships",
    )
    blocked = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blocked_by_relationships",
    )

    class Meta:
        verbose_name = "block relationship"
        verbose_name_plural = "block relationships"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["blocker", "blocked"],
                name="unique_block_relationship",
            ),
            models.CheckConstraint(
                condition=~models.Q(blocker=models.F("blocked")),
                name="prevent_self_block",
            ),
        ]
        indexes = [
            models.Index(fields=["blocker"]),
            models.Index(fields=["blocked"]),
        ]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"


class OTPToken(CreatedAtModel):
    """Time-limited OTP for email verification and password reset."""

    MAX_ATTEMPTS = 5

    class Purpose(models.TextChoices):
        REGISTER = "register", "Register"
        PASSWORD_RESET = "password_reset", "Password Reset"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="otp_tokens",
    )
    hashed_code = models.CharField(max_length=128)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "OTP token"
        verbose_name_plural = "OTP tokens"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "purpose", "used"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"OTP for {self.user.email} ({self.purpose})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_max_attempts(self):
        return self.attempts >= self.MAX_ATTEMPTS
