from __future__ import annotations

import logging

from django.apps import AppConfig

logger: logging.Logger = logging.getLogger(__name__)


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = "Notifications"

    def ready(self) -> None:
        logger.info(
            "Push notifications use Expo Push API — "
            "no Firebase credentials required."
        )
