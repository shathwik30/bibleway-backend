"""Tests for apps.verse_of_day.services — VerseOfDayService."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from apps.verse_of_day.models import VerseFallbackPool, VerseOfDay
from apps.verse_of_day.services import VerseOfDayService


# ---------------------------------------------------------------------------
# get_today_verse
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetTodayVerse:
    def setup_method(self):
        self.service = VerseOfDayService()

    def test_returns_scheduled_verse(self):
        from conftest import VerseOfDayFactory

        today = timezone.now().date()
        scheduled = VerseOfDayFactory(display_date=today, is_active=True)

        result = self.service.get_today_verse()
        assert isinstance(result, VerseOfDay)
        assert result.pk == scheduled.pk
        assert result.bible_reference == scheduled.bible_reference

    def test_falls_back_when_no_scheduled(self):
        from conftest import VerseFallbackPoolFactory

        # No scheduled verse for today, but fallback pool exists
        VerseFallbackPoolFactory(is_active=True)

        result = self.service.get_today_verse()
        assert isinstance(result, VerseFallbackPool)

    def test_returns_default_when_pool_empty(self):
        """When no scheduled verse and pool is empty, return built-in default."""
        result = self.service.get_today_verse()
        assert isinstance(result, VerseFallbackPool)
        assert result.bible_reference == "John 3:16"
        assert "For God so loved the world" in result.verse_text

    def test_ignores_inactive_scheduled(self):
        from conftest import VerseFallbackPoolFactory, VerseOfDayFactory

        today = timezone.now().date()
        VerseOfDayFactory(display_date=today, is_active=False)
        VerseFallbackPoolFactory(is_active=True)

        result = self.service.get_today_verse()
        # Should fall back since scheduled is inactive
        assert isinstance(result, VerseFallbackPool)

    def test_prefers_scheduled_over_fallback(self):
        from conftest import VerseFallbackPoolFactory, VerseOfDayFactory

        today = timezone.now().date()
        scheduled = VerseOfDayFactory(display_date=today, is_active=True)
        VerseFallbackPoolFactory(is_active=True)

        result = self.service.get_today_verse()
        assert isinstance(result, VerseOfDay)
        assert result.pk == scheduled.pk


# ---------------------------------------------------------------------------
# get_verse_by_date
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetVerseByDate:
    def setup_method(self):
        self.service = VerseOfDayService()

    def test_returns_scheduled_for_specific_date(self):
        from conftest import VerseOfDayFactory

        target = datetime.date(2025, 12, 25)
        v = VerseOfDayFactory(
            display_date=target,
            is_active=True,
            bible_reference="Luke 2:11",
            verse_text="For unto you is born...",
        )

        result = self.service.get_verse_by_date(target_date=target)
        assert isinstance(result, VerseOfDay)
        assert result.pk == v.pk

    def test_falls_back_when_no_scheduled(self):
        from conftest import VerseFallbackPoolFactory

        VerseFallbackPoolFactory(is_active=True)
        target = datetime.date(2025, 6, 15)

        result = self.service.get_verse_by_date(target_date=target)
        assert isinstance(result, VerseFallbackPool)

    def test_returns_default_when_no_fallback(self):
        target = datetime.date(2025, 6, 15)
        result = self.service.get_verse_by_date(target_date=target)
        assert result.bible_reference == "John 3:16"

    def test_consistent_fallback_for_same_date(self):
        """Fallback selection is date-seeded, so same date returns same verse."""
        from conftest import VerseFallbackPoolFactory

        VerseFallbackPoolFactory(
            is_active=True, bible_reference="Ps 23:1", verse_text="The Lord..."
        )
        VerseFallbackPoolFactory(
            is_active=True, bible_reference="Ps 46:1", verse_text="God is..."
        )

        target = datetime.date(2025, 3, 1)
        result1 = self.service.get_verse_by_date(target_date=target)
        result2 = self.service.get_verse_by_date(target_date=target)
        assert result1.pk == result2.pk


# ---------------------------------------------------------------------------
# list_scheduled_verses
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListScheduledVerses:
    def setup_method(self):
        self.service = VerseOfDayService()

    def test_returns_verses_in_range(self):
        from conftest import VerseOfDayFactory

        VerseOfDayFactory(display_date=datetime.date(2025, 1, 1), is_active=True)
        VerseOfDayFactory(display_date=datetime.date(2025, 1, 5), is_active=True)
        VerseOfDayFactory(display_date=datetime.date(2025, 1, 10), is_active=True)
        VerseOfDayFactory(display_date=datetime.date(2025, 2, 1), is_active=True)  # outside range

        results = self.service.list_scheduled_verses(
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 1, 10),
        )
        assert results.count() == 3

    def test_excludes_inactive(self):
        from conftest import VerseOfDayFactory

        VerseOfDayFactory(display_date=datetime.date(2025, 3, 1), is_active=True)
        VerseOfDayFactory(display_date=datetime.date(2025, 3, 2), is_active=False)

        results = self.service.list_scheduled_verses(
            start_date=datetime.date(2025, 3, 1),
            end_date=datetime.date(2025, 3, 2),
        )
        assert results.count() == 1

    def test_empty_range(self):
        results = self.service.list_scheduled_verses(
            start_date=datetime.date(2099, 1, 1),
            end_date=datetime.date(2099, 12, 31),
        )
        assert results.count() == 0
