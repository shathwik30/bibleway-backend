"""Centralized constants for the Bibleway backend.

Avoids magic numbers and duplicated values across services/serializers.
"""

from django.db import models

MAX_POST_TEXT_LENGTH = 2000

MAX_COMMENT_LENGTH = 1000

MAX_REPLY_LENGTH = 1000

MAX_BIO_LENGTH = 250

MAX_IMAGES_PER_POST = 10

MAX_VIDEOS_PER_POST = 1

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024

OTP_EXPIRY_MINUTES = 10

OTP_MAX_ATTEMPTS = 5

OTP_CODE_LENGTH = 6

CACHE_TIMEOUT_PROFILE = 60

CACHE_TIMEOUT_BLOCKED_USERS = 300

CACHE_TIMEOUT_UNREAD_COUNT = 30

CACHE_TIMEOUT_VERSE_OF_DAY = 3600

CACHE_TIMEOUT_BIBLE_SECTIONS = 3600

CACHE_TIMEOUT_TRANSLATION = 86400  # 24 hours

FEED_TEXT_TRUNCATE_LENGTH = 200


class MediaType(models.TextChoices):
    """Shared media type choices for PostMedia and PrayerMedia."""

    IMAGE = "image", "Image"
    VIDEO = "video", "Video"
