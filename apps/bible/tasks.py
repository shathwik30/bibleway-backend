"""Celery tasks for the bible app."""

import logging
from uuid import UUID
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    soft_time_limit=120,
    time_limit=180,
)
def translate_page_async(self, page_id: str, language_code: str) -> str | None:
    """Asynchronously translate a segregated bible page.

    Args:
        page_id: UUID string of the SegregatedPage.
        language_code: Target language code (e.g. 'es', 'fr').

    Returns:
        The UUID string of the TranslatedPageCache entry, or None on failure.
    """

    from .services import BibleTranslationService

    service = BibleTranslationService()

    try:
        cache_entry = service.translate_page(
            page_id=UUID(page_id),
            language_code=language_code,
        )
        logger.info(
            "Successfully translated page %s to %s",
            page_id,
            language_code,
        )

        return str(cache_entry.pk)

    except Exception as exc:
        logger.exception(
            "Failed to translate page %s to %s: %s",
            page_id,
            language_code,
            exc,
        )
        raise
