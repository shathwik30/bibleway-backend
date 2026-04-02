from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import OTPToken
from apps.accounts.tasks import cleanup_expired_otps
from conftest import OTPTokenFactory


@pytest.mark.django_db
class TestCleanupExpiredOtpsTask:
    def test_deletes_used_tokens_as_soon_as_they_expire(self):
        expired_used = OTPTokenFactory(
            used=True,
            expires_at=timezone.now() - datetime.timedelta(minutes=1),
        )
        fresh_unused = OTPTokenFactory(
            used=False,
            expires_at=timezone.now() + datetime.timedelta(minutes=5),
        )

        deleted_count = cleanup_expired_otps()

        assert deleted_count == 1
        assert not OTPToken.objects.filter(pk=expired_used.pk).exists()
        assert OTPToken.objects.filter(pk=fresh_unused.pk).exists()

    def test_deletes_stale_unused_tokens_after_grace_period(self):
        stale_unused = OTPTokenFactory(
            used=False,
            expires_at=timezone.now() - datetime.timedelta(hours=25),
        )
        recent_unused = OTPTokenFactory(
            used=False,
            expires_at=timezone.now() - datetime.timedelta(hours=2),
        )

        deleted_count = cleanup_expired_otps()

        assert deleted_count == 1
        assert not OTPToken.objects.filter(pk=stale_unused.pk).exists()
        assert OTPToken.objects.filter(pk=recent_unused.pk).exists()
