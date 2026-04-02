from django.conf import settings
from django.db import models
from apps.common.models import CreatedAtModel, TimeStampedModel


class Notification(CreatedAtModel):
    """In-app notification for social, messaging, and system events."""

    class NotificationType(models.TextChoices):
        FOLLOW = "follow", "Follow"
        REACTION = "reaction", "Reaction"
        COMMENT = "comment", "Comment"
        REPLY = "reply", "Reply"
        SHARE = "share", "Share"
        BOOST_LIVE = "boost_live", "Boost Live"
        BOOST_DIGEST = "boost_digest", "Boost Digest"
        NEW_MESSAGE = "new_message", "New Message"
        MISSED_CALL = "missed_call", "Missed Call"
        PRAYER_COMMENT = "prayer_comment", "Prayer Comment"
        SYSTEM_BROADCAST = "system_broadcast", "System Broadcast"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications_sent",
        help_text="Null for system-generated notifications.",
    )

    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
    )

    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Deep link and contextual data (e.g., post_id, conversation_id).",
    )

    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(fields=["notification_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.notification_type} for {self.recipient.full_name}: {self.title}"


class DevicePushToken(TimeStampedModel):
    """FCM/APNs device token for push notification delivery."""

    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_tokens",
    )

    token = models.TextField(unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "device push token"
        verbose_name_plural = "device push tokens"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"Token for {self.user.full_name} ({self.platform})"
