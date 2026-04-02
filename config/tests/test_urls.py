from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.django_db
class TestHealthCheck:
    def test_returns_ok_when_cache_round_trip_succeeds(self, client):
        response = client.get("/api/v1/health/")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["cache"] == "ok"

    def test_returns_degraded_when_cache_round_trip_fails(self, client):
        with patch("django.core.cache.cache.set"), patch(
            "django.core.cache.cache.get", return_value=None
        ):
            response = client.get("/api/v1/health/")

        assert response.status_code == 200
        assert response.json()["status"] == "degraded"
        assert response.json()["db"] == "ok"
        assert response.json()["cache"] == "error"
