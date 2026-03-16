from __future__ import annotations

from datetime import datetime
from typing import Any

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from django.utils import timezone

from apps.common.exceptions import BadRequestError
from apps.common.views import BaseAPIView

from .models import VerseFallbackPool, VerseOfDay
from .serializers import UnifiedVerseResponseSerializer
from .services import VerseOfDayService


def _build_unified_data(verse: VerseOfDay | VerseFallbackPool, display_date=None) -> dict:
    """Build a unified response dict from either a VerseOfDay or VerseFallbackPool."""
    if isinstance(verse, VerseOfDay):
        return {
            "id": verse.pk,
            "bible_reference": verse.bible_reference,
            "verse_text": verse.verse_text,
            "background_image": verse.background_image,
            "display_date": verse.display_date,
            "source": "scheduled",
        }
    else:
        return {
            "id": verse.pk,
            "bible_reference": verse.bible_reference,
            "verse_text": verse.verse_text,
            "background_image": verse.background_image,
            "display_date": display_date or timezone.now().date(),
            "source": "fallback_pool",
        }


# ---------------------------------------------------------------------------
# Verse of the Day views
# ---------------------------------------------------------------------------


class TodayVerseView(BaseAPIView):
    """GET /verse-of-day/today/ -- return today's verse.

    Returns the scheduled VerseOfDay for today, or a random fallback
    from the pool if none is scheduled. Always returns a consistent
    response shape with ``display_date`` and ``source`` fields.
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._verse_service = VerseOfDayService()

    def get(self, request: Request) -> Response:
        verse = self._verse_service.get_today_verse()
        data = _build_unified_data(verse, display_date=timezone.now().date())
        serializer = UnifiedVerseResponseSerializer(data)
        return self.success_response(
            data=serializer.data,
            message="Verse of the day retrieved.",
        )


class VerseByDateView(BaseAPIView):
    """GET /verse-of-day/<str:date_str>/ -- return the verse for a specific date.

    The date must be provided in ISO format (YYYY-MM-DD).
    Falls back to a pool verse if no scheduled verse exists for that date.
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._verse_service = VerseOfDayService()

    def get(self, request: Request, date_str: str) -> Response:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise BadRequestError(
                detail="Invalid date format. Use YYYY-MM-DD."
            )

        verse = self._verse_service.get_verse_by_date(target_date=target_date)
        data = _build_unified_data(verse, display_date=target_date)
        serializer = UnifiedVerseResponseSerializer(data)
        return self.success_response(
            data=serializer.data,
            message="Verse retrieved.",
        )
