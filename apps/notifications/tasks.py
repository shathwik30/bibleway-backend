from __future__ import annotations

import logging

import requests
from celery import shared_task

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_push_notification(self, user_id, title, body, data=None):
    """Send push notification via Expo Push Notification service.

    Expo push tokens (``ExponentPushToken[...]``) are obtained by the
    mobile client via ``Notifications.getExpoPushTokenAsync()`` and stored
    in ``DevicePushToken``.  This task fans-out one HTTP request per
    active token through Expo's REST API.
    """
    try:
        from apps.notifications.models import DevicePushToken

        tokens = list(
            DevicePushToken.objects.filter(
                user_id=user_id, is_active=True
            ).values_list("token", flat=True)
        )

        if not tokens:
            return

        messages = [
            {
                "to": token,
                "title": title,
                "body": body,
                "data": data or {},
                "sound": "default",
            }
            for token in tokens
        ]

        response = requests.post(
            EXPO_PUSH_URL,
            json=messages,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()

        result = response.json()
        tickets = result.get("data", [])
        for ticket, token in zip(tickets, tokens):
            if ticket.get("status") == "error":
                detail = ticket.get("details", {})
                error_type = detail.get("error")
                if error_type == "DeviceNotRegistered":
                    DevicePushToken.objects.filter(token=token).update(
                        is_active=False
                    )
                    logger.info(
                        "Deactivated unregistered push token for user=%s",
                        user_id,
                    )
                else:
                    logger.warning(
                        "Push ticket error for user=%s: %s - %s",
                        user_id,
                        error_type,
                        ticket.get("message", ""),
                    )

    except requests.HTTPError as e:
        if e.response is not None and 400 <= e.response.status_code < 500:
            logger.error("Push notification permanent failure (%s): %s", e.response.status_code, e)
            return
        logger.error("Push notification server error: %s", e)
        raise self.retry(exc=e)
    except requests.RequestException as e:
        logger.error("Push notification network error: %s", e)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error("Push notification task failed: %s", e)
        raise self.retry(exc=e)
