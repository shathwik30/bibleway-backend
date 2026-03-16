from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from django.core.cache import cache
from django.db.models import QuerySet

from apps.common.exceptions import ForbiddenError, NotFoundError
from apps.common.services import BaseService

from .models import DevicePushToken, Notification

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NotificationService
# ---------------------------------------------------------------------------


class NotificationService(BaseService[Notification]):
    """Business logic for in-app notifications."""

    model = Notification

    def get_queryset(self) -> QuerySet[Notification]:
        return super().get_queryset().select_related("sender")

    def create_notification(
        self,
        *,
        recipient_id: UUID,
        sender_id: UUID | None,
        notification_type: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> Notification:
        """Create a new notification for a user.

        After persisting the notification, a Celery task is dispatched
        to deliver it via FCM push notification.
        """
        notification = Notification.objects.create(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
        )
        cache.delete(f"unread_count:{recipient_id}")
        logger.info(
            "Notification created: type=%s recipient=%s",
            notification_type,
            recipient_id,
        )

        # Dispatch FCM push notification asynchronously
        try:
            from apps.notifications.tasks import send_push_notification

            send_push_notification.delay(
                user_id=str(recipient_id),
                title=title,
                body=body,
                data={k: str(v) for k, v in (data or {}).items()},
            )
        except Exception:
            logger.warning(
                "Failed to dispatch push notification task for recipient=%s",
                recipient_id,
                exc_info=True,
            )

        return notification

    def list_user_notifications(
        self,
        *,
        user_id: UUID,
    ) -> QuerySet[Notification]:
        """Return all notifications for a user, newest first."""
        return self.get_queryset().filter(recipient_id=user_id)

    def mark_as_read(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> Notification:
        """Mark a single notification as read."""
        try:
            notification = self.get_queryset().get(
                pk=notification_id, recipient_id=user_id
            )
        except Notification.DoesNotExist:
            raise NotFoundError(
                detail=f"Notification with id '{notification_id}' not found."
            )
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        cache.delete(f"unread_count:{user_id}")
        return notification

    def mark_all_as_read(self, *, user_id: UUID) -> int:
        """Mark all unread notifications for a user as read.

        Returns the number of notifications updated.
        """
        count = (
            Notification.objects.filter(recipient_id=user_id, is_read=False)
            .update(is_read=True)
        )
        cache.delete(f"unread_count:{user_id}")
        return count

    def get_unread_count(self, *, user_id: UUID) -> int:
        """Return the count of unread notifications for a user.

        Cached for 30 seconds; invalidated on create / mark-read.
        """
        cache_key = f"unread_count:{user_id}"
        count = cache.get(cache_key)
        if count is not None:
            return count
        count = Notification.objects.filter(
            recipient_id=user_id, is_read=False
        ).count()
        cache.set(cache_key, count, timeout=30)
        return count

    def delete_notification(
        self,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> None:
        """Delete a notification. Only the recipient may delete."""
        try:
            notification = Notification.objects.get(pk=notification_id)
        except Notification.DoesNotExist:
            raise NotFoundError(
                detail=f"Notification with id '{notification_id}' not found."
            )
        if notification.recipient_id != user_id:
            raise ForbiddenError(
                detail="You can only delete your own notifications."
            )
        was_unread = not notification.is_read
        notification.delete()
        if was_unread:
            cache.delete(f"unread_count:{user_id}")


# ---------------------------------------------------------------------------
# DevicePushTokenService
# ---------------------------------------------------------------------------


class DevicePushTokenService(BaseService[DevicePushToken]):
    """Business logic for managing FCM/APNs device push tokens."""

    model = DevicePushToken

    def register_token(
        self,
        *,
        user_id: UUID,
        token: str,
        platform: str,
    ) -> DevicePushToken:
        """Register or update a device push token (upsert).

        If the token already exists for a different user, it is reassigned
        to the current user (device changed hands / re-login). Reassignment
        events are logged at warning level for auditing.
        """
        # Check if token exists and belongs to a different user (reassignment)
        existing = DevicePushToken.objects.filter(token=token).first()
        if existing is not None and existing.user_id != user_id:
            logger.warning(
                "Device token reassigned: token=%s...%s from user=%s to user=%s",
                token[:8],
                token[-4:],
                existing.user_id,
                user_id,
            )

        device_token, created = DevicePushToken.objects.update_or_create(
            token=token,
            defaults={
                "user_id": user_id,
                "platform": platform,
                "is_active": True,
            },
        )
        action = "registered" if created else "updated"
        logger.info(
            "Device token %s: user=%s platform=%s",
            action,
            user_id,
            platform,
        )
        return device_token

    def deactivate_token(self, *, token: str) -> None:
        """Deactivate a push token (e.g., on logout or invalid token)."""
        updated = DevicePushToken.objects.filter(token=token).update(is_active=False)
        if updated == 0:
            raise NotFoundError(detail="Device token not found.")

    def get_active_tokens(self, *, user_id: UUID) -> QuerySet[DevicePushToken]:
        """Return all active push tokens for a user."""
        return self.get_queryset().filter(user_id=user_id, is_active=True)
