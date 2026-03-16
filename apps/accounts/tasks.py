from __future__ import annotations

import html
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


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
                "from": "BibleWay <noreply@bibleway.app>",
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
