from __future__ import annotations
import datetime
import re
from django.core.exceptions import ValidationError
from django.utils import timezone

MIN_AGE: int = 13

MAX_AGE: int = 120

SUPPORTED_LANGUAGES: frozenset[str] = frozenset(
    {
        "en",
        "es",
        "fr",
        "pt",
        "hi",
        "ar",
        "sw",
        "ko",
        "zh",
        "ja",
        "de",
        "it",
        "ru",
    }
)


def calculate_age(born: datetime.date) -> int:
    """Calculate age from a date of birth."""

    today: datetime.date = timezone.now().date()

    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def validate_password_strength(password: str) -> None:
    """Ensure password has min 8 chars, uppercase, lowercase, number, and special char."""

    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")

    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least one uppercase letter.")

    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain at least one lowercase letter.")

    if not re.search(r"[0-9]", password):
        raise ValidationError("Password must contain at least one number.")

    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\",./<>?\\|`~]", password):
        raise ValidationError("Password must contain at least one special character.")


def validate_date_of_birth(value: datetime.date) -> datetime.date:
    """Validate date of birth is not in the future and within a reasonable age range."""

    today: datetime.date = timezone.now().date()

    if value >= today:
        raise ValidationError("Date of birth cannot be in the future.")

    age: int = calculate_age(value)

    if age < MIN_AGE:
        raise ValidationError(f"You must be at least {MIN_AGE} years old.")

    if age > MAX_AGE:
        raise ValidationError("Please enter a valid date of birth.")

    return value


def validate_preferred_language(value: str) -> str:
    """Validate language is in the supported set."""

    if value not in SUPPORTED_LANGUAGES:
        raise ValidationError(
            f"Unsupported language. Choose from: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
        )

    return value
