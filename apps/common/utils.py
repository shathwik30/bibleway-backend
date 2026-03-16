from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from typing import Any

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
    # Remove all chars except word chars, hyphens, and a single dot for extension.
    name = re.sub(r"[^\w\-.]", "", name)
    # Collapse consecutive dots to prevent ".." traversal.
    name = re.sub(r"\.{2,}", ".", name)
    # Strip leading dots to prevent hidden files.
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


def get_blocked_user_ids(user_id) -> set:
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

    blocked_by_me = set(
        BlockRelationship.objects.filter(blocker_id=user_id).values_list(
            "blocked_id", flat=True
        )
    )
    blocked_me = set(
        BlockRelationship.objects.filter(blocked_id=user_id).values_list(
            "blocker_id", flat=True
        )
    )
    result = blocked_by_me | blocked_me
    cache.set(cache_key, result, timeout=300)  # 5 minutes
    return result


def invalidate_blocked_user_cache(user_id) -> None:
    """Invalidate the blocked-user cache for a given user.

    Call this from BlockRelationship signals on create/delete.
    """
    from django.core.cache import cache

    cache.delete(f"blocked_user_ids:{user_id}")
