"""Bible-specific validators."""

import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def validate_verse_reference(value: str) -> None:
    """Validate an API Bible verse reference format (e.g. 'GEN.1.1', 'JHN.3.16').

    Expected pattern: 3-letter book code, dot, chapter number, dot, verse number.
    Also supports ranges like 'GEN.1.1-GEN.1.5'.
    """
    pattern = r"^[A-Z1-9]{2,5}\.\d{1,3}\.\d{1,3}(-[A-Z1-9]{2,5}\.\d{1,3}\.\d{1,3})?$"
    if not re.match(pattern, value):
        raise ValidationError(
            "Invalid verse reference format. Expected format: 'GEN.1.1' or 'GEN.1.1-GEN.1.5'."
        )


def validate_youtube_url(value: str) -> None:
    """Validate that a URL is a valid YouTube URL."""
    if not value:
        return

    # First validate it's a proper URL.
    url_validator = URLValidator()
    url_validator(value)

    youtube_patterns = (
        r"^https?://(www\.)?youtube\.com/watch\?",
        r"^https?://(www\.)?youtube\.com/embed/",
        r"^https?://(www\.)?youtube\.com/shorts/",
        r"^https?://youtu\.be/",
    )
    if not any(re.match(pattern, value) for pattern in youtube_patterns):
        raise ValidationError(
            "URL must be a valid YouTube URL (youtube.com or youtu.be)."
        )


def validate_language_code(value: str) -> None:
    """Validate an ISO 639-1 language code (2-letter, lowercase)."""
    pattern = r"^[a-z]{2}(-[A-Z]{2})?$"
    if not re.match(pattern, value):
        raise ValidationError(
            "Invalid language code. Expected ISO 639-1 format (e.g. 'en', 'es', 'fr-FR')."
        )
