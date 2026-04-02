import uuid
from django.db import models


class UUIDModel(models.Model):
    """Abstract base that replaces auto-increment PK with UUID."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    """Abstract base with UUID pk + created_at/updated_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class CreatedAtModel(UUIDModel):
    """Abstract base with UUID pk + created_at only (no updated_at).

    For immutable records like follows, blocks, reactions, views.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
