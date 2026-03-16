from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_push_notification(self, user_id, title, body, data=None):
    """Send push notification via FCM."""
    try:
        from firebase_admin import messaging

        from apps.notifications.models import DevicePushToken

        tokens = list(
            DevicePushToken.objects.filter(
                user_id=user_id, is_active=True
            ).values_list("token", flat=True)
        )

        if not tokens:
            return

        for token in tokens:
            try:
                message = messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data=data or {},
                    token=token,
                )
                messaging.send(message)
            except messaging.UnregisteredError:
                DevicePushToken.objects.filter(token=token).update(is_active=False)
                logger.info(
                    "Deactivated unregistered FCM token for user=%s", user_id
                )
            except Exception as e:
                logger.warning("Failed to send push to token: %s", e)
    except Exception as e:
        logger.error("Push notification task failed: %s", e)
        raise self.retry(exc=e)
