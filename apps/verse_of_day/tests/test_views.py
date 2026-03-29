"""Tests for apps.verse_of_day.views — API endpoints for verse of the day."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone
from rest_framework import status


# ---------------------------------------------------------------------------
# GET /api/v1/verse-of-day/today/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTodayVerseView:
    url = "/api/v1/verse-of-day/today/"

    def setup_method(self):
        from django.core.cache import cache
        cache.clear()

    def test_returns_scheduled_verse(self, auth_client):
        from conftest import VerseOfDayFactory

        today = timezone.now().date()
        VerseOfDayFactory(
            display_date=today,
            is_active=True,
            bible_reference="Psalm 119:105",
            verse_text="Your word is a lamp...",
        )

        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["bible_reference"] == "Psalm 119:105"
        assert data["source"] == "scheduled"
        assert str(data["display_date"]) == str(today)

    def test_returns_fallback_when_no_scheduled(self, auth_client):
        from conftest import VerseFallbackPoolFactory

        VerseFallbackPoolFactory(is_active=True, bible_reference="Proverbs 3:5")

        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["source"] == "fallback_pool"

    def test_returns_default_when_pool_empty(self, auth_client):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["bible_reference"] == "John 3:16"
        assert data["source"] == "fallback_pool"

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_response_has_expected_fields(self, auth_client):
        from conftest import VerseOfDayFactory

        today = timezone.now().date()
        VerseOfDayFactory(display_date=today, is_active=True)

        response = auth_client.get(self.url)
        data = response.data["data"]
        assert "id" in data
        assert "bible_reference" in data
        assert "verse_text" in data
        assert "display_date" in data
        assert "source" in data

    def test_message_present(self, auth_client):
        response = auth_client.get(self.url)
        assert "message" in response.data


# ---------------------------------------------------------------------------
# GET /api/v1/verse-of-day/<date_str>/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVerseByDateView:
    def _url(self, date_str: str) -> str:
        return f"/api/v1/verse-of-day/{date_str}/"

    def test_returns_verse_for_specific_date(self, auth_client):
        from conftest import VerseOfDayFactory

        target = datetime.date(2025, 12, 25)
        VerseOfDayFactory(
            display_date=target,
            is_active=True,
            bible_reference="Luke 2:11",
        )

        response = auth_client.get(self._url("2025-12-25"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["bible_reference"] == "Luke 2:11"
        assert response.data["data"]["source"] == "scheduled"

    def test_falls_back_when_no_scheduled(self, auth_client):
        from conftest import VerseFallbackPoolFactory

        VerseFallbackPoolFactory(is_active=True)

        response = auth_client.get(self._url("2025-06-15"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["source"] == "fallback_pool"

    def test_invalid_date_format_returns_400(self, auth_client):
        response = auth_client.get(self._url("not-a-date"))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_wrong_date_format_returns_400(self, auth_client):
        response = auth_client.get(self._url("25-12-2025"))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(self._url("2025-12-25"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_display_date_matches_requested(self, auth_client):
        from conftest import VerseFallbackPoolFactory

        VerseFallbackPoolFactory(is_active=True)

        response = auth_client.get(self._url("2025-08-20"))
        assert response.status_code == status.HTTP_200_OK
        assert str(response.data["data"]["display_date"]) == "2025-08-20"
