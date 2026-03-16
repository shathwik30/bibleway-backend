from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import CreatedAtModel, TimeStampedModel


class AdminRole(TimeStampedModel):
    """Role-based access control for admin users.

    Each admin staff user is assigned exactly one role that determines
    which admin modules they can access.
    """

    class RoleType(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super Admin"
        CONTENT_ADMIN = "content_admin", "Content Admin"
        MODERATION_ADMIN = "moderation_admin", "Moderation Admin"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_role",
    )
    role = models.CharField(
        max_length=20,
        choices=RoleType.choices,
        default=RoleType.CONTENT_ADMIN,
    )

    class Meta:
        verbose_name = "admin role"
        verbose_name_plural = "admin roles"

    def __str__(self) -> str:
        return f"{self.user.full_name} — {self.get_role_display()}"


class AdminLog(CreatedAtModel):
    """Audit trail of all admin actions."""

    class ActionType(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        SUSPEND = "suspend", "Suspend"
        UNSUSPEND = "unsuspend", "Unsuspend"
        WARN = "warn", "Warn"
        DISMISS_REPORT = "dismiss_report", "Dismiss Report"
        REMOVE_CONTENT = "remove_content", "Remove Content"
        BROADCAST = "broadcast", "Broadcast"
        ROLE_CHANGE = "role_change", "Role Change"

    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_logs",
    )
    action = models.CharField(max_length=30, choices=ActionType.choices)
    target_model = models.CharField(
        max_length=100,
        help_text="e.g. 'accounts.User', 'social.Post'",
    )
    target_id = models.CharField(
        max_length=255,
        help_text="Primary key of the affected object.",
    )
    detail = models.TextField(
        blank=True,
        default="",
        help_text="Human-readable description of what was done.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Snapshot of changed fields or extra context.",
    )

    class Meta:
        verbose_name = "admin log"
        verbose_name_plural = "admin logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["admin_user", "-created_at"]),
            models.Index(fields=["action"]),
            models.Index(fields=["target_model", "target_id"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.admin_user.full_name} — {self.action} "
            f"{self.target_model}:{self.target_id}"
        )


class BoostTier(TimeStampedModel):
    """Admin-configurable pricing tiers for post boosts."""

    name = models.CharField(max_length=100)
    apple_product_id = models.CharField(max_length=100, unique=True)
    google_product_id = models.CharField(max_length=100, unique=True)
    duration_days = models.PositiveSmallIntegerField()
    display_price = models.CharField(
        max_length=20,
        help_text="Display string e.g. '$5.00'",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "boost tier"
        verbose_name_plural = "boost tiers"
        ordering = ["duration_days"]

    def __str__(self) -> str:
        return f"{self.name} — {self.duration_days} days ({self.display_price})"
