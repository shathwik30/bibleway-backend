from __future__ import annotations

import re

from django.core.exceptions import ValidationError


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
