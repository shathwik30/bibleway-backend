from __future__ import annotations

import datetime
import html
import logging

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

logger: logging.Logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_otp_email_task(
    self,
    user_email: str,
    user_name: str,
    otp_code: str,
    purpose: str,
) -> None:
    """Send an OTP email via Resend. Retries up to 3 times on failure."""
    try:
        import resend
        from django.conf import settings

        resend.api_key = settings.RESEND_API_KEY

        subject_map: dict[str, str] = {
            "registration": "Your BibleWay verification code",
            "password_reset": "Your BibleWay password reset code",
        }
        subject: str = subject_map.get(purpose, "Your BibleWay code")
        safe_name: str = html.escape(user_name)

        resend.Emails.send(
            {
                "from": "BibleWay <noreply@bibleway.io>",
                "to": user_email,
                "subject": subject,
                "html": (
                    f"<p>Hi {safe_name},</p>"
                    f"<p>Your verification code is: <strong>{otp_code}</strong></p>"
                    f"<p>This code expires in 10 minutes.</p>"
                    f"<p>If you did not request this, please ignore this email.</p>"
                ),
            }
        )

        logger.info("OTP email sent to %s for %s", user_email, purpose)

    except Exception as exc:
        logger.exception("Failed to send OTP email to %s: %s", user_email, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def cleanup_expired_otps(self) -> int:
    """Delete OTP tokens that are expired and used, or expired for over 24 hours.

    Should be scheduled to run daily via Celery Beat.
    """
    try:
        from apps.accounts.models import OTPToken

        now = timezone.now()
        cutoff: datetime.datetime = timezone.now() - datetime.timedelta(hours=24)
        deleted_count: int
        deleted_count, _ = OTPToken.objects.filter(
            Q(used=True, expires_at__lt=now) | Q(expires_at__lt=cutoff),
        ).delete()
        logger.info("Cleaned up %d expired OTP tokens.", deleted_count)
        return deleted_count
    except Exception as exc:
        logger.exception("cleanup_expired_otps task failed: %s", exc)
        raise self.retry(exc=exc)
