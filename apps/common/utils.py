from __future__ import annotations
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure random numeric OTP code."""

    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_otp(otp_code: str) -> str:
    """Hash an OTP code using HMAC-SHA256 with the Django SECRET_KEY."""

    return hmac.new(
        key=settings.SECRET_KEY.encode("utf-8"),
        msg=otp_code.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
    """Verify an OTP against its HMAC hash using constant-time comparison."""

    return hmac.compare_digest(hash_otp(plain_otp), hashed_otp)


def get_otp_expiry(minutes: int = 10) -> datetime:
    """Return a timezone-aware expiry datetime for OTP tokens."""

    return timezone.now() + timedelta(minutes=minutes)


def get_file_extension(file: UploadedFile) -> str:
    """Extract the file extension from an uploaded file."""

    name: str = file.name or ""

    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def sanitize_filename(filename: str) -> str:
    """Strip path traversal characters and unsafe sequences from a filename."""

    import uuid

    name = filename.rsplit("/", 1)[-1]

    name = name.rsplit("\\", 1)[-1]

    name = re.sub(r"[^\w\-.]", "", name)

    name = re.sub(r"\.{2,}", ".", name)

    name = name.lstrip(".")

    if not name:
        return f"{uuid.uuid4().hex}"

    return name


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to a maximum length with ellipsis."""

    if len(text) <= max_length:
        return text

    return text[: max_length - 3] + "..."


def build_notification_data(
    notification_type: str,
    **kwargs: Any,
) -> dict[str, str]:
    """Build a notification data payload for deep linking."""

    data: dict[str, str] = {"type": notification_type}

    for key, value in kwargs.items():
        if value is not None:
            data[key] = str(value)

    return data


def get_blocked_user_ids(user_id: UUID) -> set[UUID]:
    """Get IDs of all users blocked by or blocking the given user.

    Results are cached in Django's default cache for 5 minutes to
    avoid repeated DB queries on every feed / comment listing.
    """

    from django.core.cache import cache
    from apps.accounts.models import BlockRelationship

    cache_key = f"blocked_user_ids:{user_id}"

    result = cache.get(cache_key)

    if result is not None:
        return result

    from django.db.models import Q

    relationships = BlockRelationship.objects.filter(
        Q(blocker_id=user_id) | Q(blocked_id=user_id)
    ).values_list("blocker_id", "blocked_id")

    result: set[UUID] = set()

    for blocker_id, blocked_id in relationships:
        other_id = blocked_id if blocker_id == user_id else blocker_id
        result.add(other_id)

    from apps.common.constants import CACHE_TIMEOUT_BLOCKED_USERS

    cache.set(cache_key, result, timeout=CACHE_TIMEOUT_BLOCKED_USERS)

    return result


def invalidate_blocked_user_cache(user_id: UUID, other_user_id: UUID | None = None) -> None:
    """Invalidate the blocked-user cache for both sides of a block relationship.

    Call this from BlockRelationship signals on create/delete.
    """

    from django.core.cache import cache

    cache.delete(f"blocked_user_ids:{user_id}")

    if other_user_id is not None:
        cache.delete(f"blocked_user_ids:{other_user_id}")


def send_notification_safe(
    *,
    recipient_id: UUID,
    sender_id: UUID | None = None,
    notification_type: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> None:
    """Fire-and-forget notification dispatch.

    Swallows all exceptions so callers are never disrupted by notification
    failures. Logs warnings on failure for debugging.
    """

    import logging

    logger = logging.getLogger("apps.common.utils")

    try:
        from apps.notifications.services import NotificationService

        NotificationService().create_notification(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
        )

    except Exception:
        logger.warning(
            "Failed to send %s notification to %s",
            notification_type,
            recipient_id,
            exc_info=True,
        )
