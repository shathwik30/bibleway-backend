from __future__ import annotations

import logging
import random
from datetime import date

from django.core.cache import cache
from django.db.models import QuerySet
from django.utils import timezone

from apps.common.services import BaseService

from .models import VerseFallbackPool, VerseOfDay

logger = logging.getLogger(__name__)


class VerseOfDayService(BaseService[VerseOfDay]):
    """Business logic for the Verse of the Day feature."""

    model = VerseOfDay

    def get_queryset(self) -> QuerySet[VerseOfDay]:
        return super().get_queryset().filter(is_active=True)

    # Used when no scheduled verse and the fallback pool is empty.
    _DEFAULT_VERSE = {
        "bible_reference": "John 3:16",
        "verse_text": (
            "For God so loved the world that he gave his one and only Son, "
            "that whoever believes in him shall not perish but have eternal life."
        ),
    }

    def _get_fallback_verse(self, target_date: date) -> VerseFallbackPool:
        """Pick a random fallback verse from the active pool.

        Uses a date-seeded RNG for consistency within the same day.
        If the pool is empty, returns a built-in default verse to
        guarantee clients always receive content.
        """
        # Use a single query: pick a deterministic offset into the table.
        pool_count = VerseFallbackPool.objects.filter(is_active=True).count()
        if pool_count == 0:
            logger.warning(
                "Fallback verse pool is empty for %s; returning built-in default.",
                target_date,
            )
            return VerseFallbackPool(
                bible_reference=self._DEFAULT_VERSE["bible_reference"],
                verse_text=self._DEFAULT_VERSE["verse_text"],
                is_active=True,
            )

        rng = random.Random(target_date.isoformat())
        offset = rng.randint(0, pool_count - 1)
        fallback = VerseFallbackPool.objects.filter(is_active=True).order_by("pk")[offset]

        logger.info(
            "No scheduled verse for %s; using fallback '%s'.",
            target_date,
            fallback.bible_reference,
        )
        return fallback

    def get_today_verse(self) -> VerseOfDay | VerseFallbackPool:
        """Return the scheduled verse for today, or a random fallback.

        Cached for 1 hour — the verse doesn't change within a day.
        """
        cache_key = "verse_of_day:today"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        today = timezone.now().date()

        scheduled = (
            VerseOfDay.objects.filter(display_date=today, is_active=True).first()
        )
        if scheduled is not None:
            cache.set(cache_key, scheduled, timeout=3600)
            return scheduled

        result = self._get_fallback_verse(today)
        cache.set(cache_key, result, timeout=3600)
        return result

    def get_verse_by_date(self, *, target_date: date) -> VerseOfDay | VerseFallbackPool:
        """Return the verse scheduled for a specific date.

        Falls back to a random pool verse if no scheduled verse exists.
        Cached for 1 hour per date.
        """
        cache_key = f"verse_of_day:{target_date.isoformat()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        scheduled = VerseOfDay.objects.filter(
            display_date=target_date, is_active=True
        ).first()
        if scheduled is not None:
            cache.set(cache_key, scheduled, timeout=3600)
            return scheduled

        result = self._get_fallback_verse(target_date)
        cache.set(cache_key, result, timeout=3600)
        return result

    def list_scheduled_verses(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> QuerySet[VerseOfDay]:
        """Return scheduled verses within a date range (inclusive)."""
        return self.get_queryset().filter(
            display_date__gte=start_date,
            display_date__lte=end_date,
        )
