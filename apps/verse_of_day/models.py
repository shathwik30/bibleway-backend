from django.db import models
from apps.common.models import TimeStampedModel
from apps.common.storage_backends import PublicMediaStorage


def verse_background_upload_path(instance: "VerseOfDay", filename: str) -> str:
    return f"verse_of_day/{instance.display_date}/{filename}"


def fallback_background_upload_path(instance: "VerseFallbackPool", filename: str) -> str:
    return f"verse_of_day/fallback_pool/{instance.id}/{filename}"


class VerseOfDay(TimeStampedModel):
    """Scheduled Verse of the Day. Admin schedules one verse per date.

    If no verse is scheduled for a given day, the system falls back
    to the VerseFallbackPool.
    """

    bible_reference = models.CharField(
        max_length=100,
        help_text="e.g., 'John 3:16'",
    )

    verse_text = models.TextField()
    background_image = models.ImageField(
        upload_to=verse_background_upload_path,
        storage=PublicMediaStorage(),
        blank=True,
        default="",
    )

    display_date = models.DateField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "verse of the day"
        verbose_name_plural = "verses of the day"
        ordering = ["-display_date"]

    def __str__(self) -> str:
        return f"{self.display_date}: {self.bible_reference}"


class VerseFallbackPool(TimeStampedModel):
    """Pool of fallback verses used when no VerseOfDay is scheduled."""

    bible_reference = models.CharField(
        max_length=100,
        help_text="e.g., 'Psalm 23:1'",
    )

    verse_text = models.TextField()
    background_image = models.ImageField(
        upload_to=fallback_background_upload_path,
        storage=PublicMediaStorage(),
        blank=True,
        default="",
    )

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "verse fallback pool entry"
        verbose_name_plural = "verse fallback pool entries"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Fallback: {self.bible_reference}"
