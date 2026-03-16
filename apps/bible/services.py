from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, models
from django.db.models import Count, Q, QuerySet, Value

from apps.common.exceptions import BadRequestError, NotFoundError
from apps.common.services import BaseService, BaseUserScopedService

from .models import (
    Bookmark,
    Highlight,
    Note,
    SegregatedChapter,
    SegregatedPage,
    SegregatedSection,
    TranslatedPageCache,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Segregated Bible content
# ---------------------------------------------------------------------------


class SegregatedBibleService(BaseService[SegregatedSection]):
    """Read-only service for navigating the Segregated Bible hierarchy.

    Sections -> Chapters -> Pages.
    """

    model = SegregatedSection

    # -- Sections ----------------------------------------------------------

    def get_sections(
        self,
        *,
        user_age: int | None = None,
    ) -> QuerySet[SegregatedSection]:
        """Return active sections, ordered by ``order``.

        If *user_age* is provided the user's matching section is annotated with
        ``is_prioritized=True`` and placed first in the result set (by a
        secondary sort on a computed column).
        """
        qs: QuerySet[SegregatedSection] = (
            self.get_queryset().filter(is_active=True)
        )

        # Annotate chapter_count to avoid N+1 queries in the serializer.
        qs = qs.annotate(
            chapter_count=Count(
                "chapters",
                filter=Q(chapters__is_active=True),
            ),
        )

        if user_age is not None:
            qs = qs.annotate(
                is_prioritized=models.Case(
                    models.When(
                        age_min__lte=user_age,
                        age_max__gte=user_age,
                        then=models.Value(True),
                    ),
                    default=models.Value(False),
                    output_field=models.BooleanField(),
                ),
            ).order_by("-is_prioritized", "order")
        else:
            qs = qs.annotate(
                is_prioritized=Value(False, output_field=models.BooleanField()),
            )

        return qs

    # -- Chapters ----------------------------------------------------------

    def get_chapters_for_section(
        self,
        section_id: UUID,
    ) -> QuerySet[SegregatedChapter]:
        """Return active chapters for a given section, ordered by ``order``."""
        section: SegregatedSection = self.get_by_id(section_id)
        return (
            SegregatedChapter.objects.filter(
                section=section,
                is_active=True,
            )
            .annotate(
                page_count=Count(
                    "pages",
                    filter=Q(pages__is_active=True),
                ),
            )
            .order_by("order")
        )

    # -- Pages -------------------------------------------------------------

    def get_pages_for_chapter(
        self,
        chapter_id: UUID,
    ) -> QuerySet[SegregatedPage]:
        """Return active pages for a chapter, ordered by ``order``."""
        chapter: SegregatedChapter = self._get_chapter(chapter_id)
        return (
            SegregatedPage.objects.filter(
                chapter=chapter,
                is_active=True,
            )
            .order_by("order")
        )

    def get_page_detail(
        self,
        page_id: UUID,
        *,
        language_code: str | None = None,
    ) -> SegregatedPage:
        """Return a single page, optionally with translated content.

        When *language_code* is given and a cached translation exists, the
        ``content`` attribute of the returned instance is replaced in-memory
        with the translated text (the DB record is **not** mutated).
        """
        try:
            page: SegregatedPage = (
                SegregatedPage.objects.select_related("chapter", "chapter__section")
                .get(pk=page_id, is_active=True)
            )
        except SegregatedPage.DoesNotExist:
            raise NotFoundError(detail=f"Page with id '{page_id}' not found.")

        if language_code and language_code != "en":
            cached: TranslatedPageCache | None = (
                TranslatedPageCache.objects.filter(
                    page=page,
                    language_code=language_code,
                ).first()
            )
            if cached is not None:
                # Replace content in-memory only; do not save.
                page.content = cached.translated_content

        return page

    # -- Search ------------------------------------------------------------

    def search_content(
        self,
        query: str,
        *,
        section_id: UUID | None = None,
    ) -> QuerySet[SegregatedPage]:
        """Full-text search across active page titles and content.

        Optionally scoped to pages within a specific section.
        """
        if not query or not query.strip():
            raise BadRequestError(detail="Search query must not be empty.")

        qs: QuerySet[SegregatedPage] = SegregatedPage.objects.filter(
            is_active=True,
            chapter__is_active=True,
            chapter__section__is_active=True,
        ).select_related("chapter", "chapter__section")

        if section_id is not None:
            qs = qs.filter(chapter__section_id=section_id)

        qs = qs.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )

        return qs.order_by("chapter__section__order", "chapter__order", "order")

    # -- Private helpers ---------------------------------------------------

    def _get_chapter(self, chapter_id: UUID) -> SegregatedChapter:
        try:
            return SegregatedChapter.objects.get(pk=chapter_id, is_active=True)
        except SegregatedChapter.DoesNotExist:
            raise NotFoundError(
                detail=f"Chapter with id '{chapter_id}' not found."
            )


# ---------------------------------------------------------------------------
# Translation cache
# ---------------------------------------------------------------------------


class BibleTranslationService:
    """Manages translated content caching for Segregated Bible pages.

    Uses Google Cloud Translation API on cache miss.
    """

    def translate_page(
        self,
        page_id: UUID,
        language_code: str,
    ) -> TranslatedPageCache:
        """Return a cached translation, calling Google Translate on a miss.

        Returns the ``TranslatedPageCache`` instance (created or existing).
        Uses get_or_create pattern to handle concurrent requests safely.
        """
        try:
            page: SegregatedPage = SegregatedPage.objects.get(
                pk=page_id, is_active=True,
            )
        except SegregatedPage.DoesNotExist:
            raise NotFoundError(detail=f"Page with id '{page_id}' not found.")

        # Check cache first.
        cached: TranslatedPageCache | None = TranslatedPageCache.objects.filter(
            page=page,
            language_code=language_code,
        ).first()

        if cached is not None:
            return cached

        # Cache miss -- call Google Translate.
        translated_text: str = self._call_google_translate(
            page.content,
            target_language=language_code,
        )

        # Use get_or_create with IntegrityError fallback for race conditions.
        try:
            cache_entry, _created = TranslatedPageCache.objects.get_or_create(
                page=page,
                language_code=language_code,
                defaults={"translated_content": translated_text},
            )
        except IntegrityError:
            # Another request created this translation concurrently.
            cache_entry = TranslatedPageCache.objects.get(
                page=page,
                language_code=language_code,
            )
        return cache_entry

    def invalidate_cache_for_page(self, page_id: UUID) -> int:
        """Delete all cached translations for a page.

        Returns the number of deleted rows.
        """
        count, _ = TranslatedPageCache.objects.filter(page_id=page_id).delete()
        return count

    # -- Private -----------------------------------------------------------

    @staticmethod
    def _call_google_translate(text: str, *, target_language: str) -> str:
        """Call the Google Cloud Translation API v2.

        Requires ``GOOGLE_TRANSLATE_API_KEY`` in Django settings.
        """
        import requests
        from django.conf import settings

        api_key: str = getattr(settings, "GOOGLE_TRANSLATE_API_KEY", "")
        if not api_key:
            logger.error("GOOGLE_TRANSLATE_API_KEY is not configured.")
            raise BadRequestError(
                detail="Translation service is not configured."
            )

        url: str = "https://translation.googleapis.com/language/translate/v2"
        payload: dict[str, str] = {
            "q": text,
            "target": target_language,
            "format": "text",
            "key": api_key,
        }

        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            translations: list[dict[str, str]] = (
                data.get("data", {}).get("translations", [])
            )
            if not translations:
                raise BadRequestError(
                    detail="Translation API returned no results."
                )
            return translations[0]["translatedText"]
        except requests.RequestException as exc:
            logger.exception("Google Translate API call failed: %s", exc)
            raise BadRequestError(
                detail="Translation service is temporarily unavailable."
            )


# ---------------------------------------------------------------------------
# Bookmark
# ---------------------------------------------------------------------------


class BookmarkService(BaseUserScopedService[Bookmark]):
    """Manages user bookmarks for both API Bible verses and Segregated content."""

    model = Bookmark

    def create_bookmark(
        self,
        user_id: UUID,
        *,
        bookmark_type: str,
        verse_reference: str = "",
        content_type_id: int | None = None,
        object_id: UUID | None = None,
    ) -> Bookmark:
        """Create a bookmark.

        For ``api_bible`` type: *verse_reference* is required.
        For ``segregated`` type: *content_type_id* and *object_id* are required.
        """
        if bookmark_type == Bookmark.BookmarkType.API_BIBLE:
            if not verse_reference:
                raise BadRequestError(
                    detail="verse_reference is required for API Bible bookmarks."
                )
            return self.model.objects.create(
                user_id=user_id,
                bookmark_type=bookmark_type,
                verse_reference=verse_reference,
            )

        if bookmark_type == Bookmark.BookmarkType.SEGREGATED:
            if not content_type_id or not object_id:
                raise BadRequestError(
                    detail="content_type and object_id are required for "
                    "segregated bookmarks.",
                )
            # Validate that the content type is allowed.
            try:
                ct: ContentType = ContentType.objects.get(pk=content_type_id)
            except ContentType.DoesNotExist:
                raise BadRequestError(detail="Invalid content_type.")

            if ct.app_label != "bible" or ct.model not in (
                "segregatedchapter",
                "segregatedpage",
            ):
                raise BadRequestError(
                    detail="content_type must reference a SegregatedChapter "
                    "or SegregatedPage.",
                )

            # Verify the target object exists.
            target_model = ct.model_class()
            if not target_model.objects.filter(pk=object_id).exists():
                raise NotFoundError(
                    detail=f"{ct.model} with id '{object_id}' not found."
                )

            return self.model.objects.create(
                user_id=user_id,
                bookmark_type=bookmark_type,
                content_type=ct,
                object_id=object_id,
            )

        raise BadRequestError(detail=f"Invalid bookmark_type '{bookmark_type}'.")

    def delete_bookmark(self, user_id: UUID, bookmark_id: UUID) -> None:
        """Delete a bookmark owned by *user_id*."""
        bookmark: Bookmark = self.get_for_user(user_id, bookmark_id)
        self.delete(bookmark)

    def list_bookmarks(
        self,
        user_id: UUID,
        *,
        bookmark_type: str | None = None,
    ) -> QuerySet[Bookmark]:
        """Return bookmarks for a user, optionally filtered by type."""
        qs: QuerySet[Bookmark] = self.list_for_user(user_id)
        if bookmark_type:
            qs = qs.filter(bookmark_type=bookmark_type)
        return qs


# ---------------------------------------------------------------------------
# Highlight
# ---------------------------------------------------------------------------


class HighlightService(BaseUserScopedService[Highlight]):
    """Manages user highlights for API Bible verses and Segregated pages."""

    model = Highlight

    def create_highlight(
        self,
        user_id: UUID,
        *,
        highlight_type: str,
        color: str = Highlight.Color.YELLOW,
        verse_reference: str = "",
        content_type_id: int | None = None,
        object_id: UUID | None = None,
        selection_start: int | None = None,
        selection_end: int | None = None,
    ) -> Highlight:
        """Create a highlight.

        For ``api_bible``: *verse_reference* is required.
        For ``segregated``: *content_type_id*, *object_id*, *selection_start*
        and *selection_end* are required.
        """
        if highlight_type == Highlight.HighlightType.API_BIBLE:
            if not verse_reference:
                raise BadRequestError(
                    detail="verse_reference is required for API Bible highlights."
                )
            return self.model.objects.create(
                user_id=user_id,
                highlight_type=highlight_type,
                verse_reference=verse_reference,
                color=color,
            )

        if highlight_type == Highlight.HighlightType.SEGREGATED:
            if not content_type_id or not object_id:
                raise BadRequestError(
                    detail="content_type and object_id are required for "
                    "segregated highlights.",
                )
            if selection_start is None or selection_end is None:
                raise BadRequestError(
                    detail="selection_start and selection_end are required "
                    "for segregated highlights.",
                )
            if selection_start >= selection_end:
                raise BadRequestError(
                    detail="selection_start must be less than selection_end."
                )

            try:
                ct: ContentType = ContentType.objects.get(pk=content_type_id)
            except ContentType.DoesNotExist:
                raise BadRequestError(detail="Invalid content_type.")

            if ct.app_label != "bible" or ct.model != "segregatedpage":
                raise BadRequestError(
                    detail="content_type must reference a SegregatedPage.",
                )

            # Verify the target object exists.
            if not SegregatedPage.objects.filter(pk=object_id).exists():
                raise NotFoundError(
                    detail=f"SegregatedPage with id '{object_id}' not found."
                )

            return self.model.objects.create(
                user_id=user_id,
                highlight_type=highlight_type,
                content_type=ct,
                object_id=object_id,
                selection_start=selection_start,
                selection_end=selection_end,
                color=color,
            )

        raise BadRequestError(
            detail=f"Invalid highlight_type '{highlight_type}'."
        )

    def delete_highlight(self, user_id: UUID, highlight_id: UUID) -> None:
        """Delete a highlight owned by *user_id*."""
        highlight: Highlight = self.get_for_user(user_id, highlight_id)
        self.delete(highlight)

    def list_highlights(
        self,
        user_id: UUID,
        *,
        highlight_type: str | None = None,
    ) -> QuerySet[Highlight]:
        """Return highlights for a user, optionally filtered by type."""
        qs: QuerySet[Highlight] = self.list_for_user(user_id)
        if highlight_type:
            qs = qs.filter(highlight_type=highlight_type)
        return qs

    def list_highlights_for_content(
        self,
        user_id: UUID,
        *,
        content_type_id: int,
        object_id: UUID,
    ) -> QuerySet[Highlight]:
        """Return all highlights for a specific content object."""
        return self.list_for_user(user_id).filter(
            content_type_id=content_type_id,
            object_id=object_id,
        )


# ---------------------------------------------------------------------------
# Note
# ---------------------------------------------------------------------------


class NoteService(BaseUserScopedService[Note]):
    """Manages user notes for API Bible verses and Segregated pages."""

    model = Note

    def create_note(
        self,
        user_id: UUID,
        *,
        note_type: str,
        text: str,
        verse_reference: str = "",
        content_type_id: int | None = None,
        object_id: UUID | None = None,
    ) -> Note:
        """Create a note.

        For ``api_bible``: *verse_reference* is required.
        For ``segregated``: *content_type_id* and *object_id* are required.
        """
        if not text or not text.strip():
            raise BadRequestError(detail="Note text must not be empty.")

        if note_type == Note.NoteType.API_BIBLE:
            if not verse_reference:
                raise BadRequestError(
                    detail="verse_reference is required for API Bible notes."
                )
            return self.model.objects.create(
                user_id=user_id,
                note_type=note_type,
                verse_reference=verse_reference,
                text=text,
            )

        if note_type == Note.NoteType.SEGREGATED:
            if not content_type_id or not object_id:
                raise BadRequestError(
                    detail="content_type and object_id are required for "
                    "segregated notes.",
                )

            try:
                ct: ContentType = ContentType.objects.get(pk=content_type_id)
            except ContentType.DoesNotExist:
                raise BadRequestError(detail="Invalid content_type.")

            if ct.app_label != "bible" or ct.model != "segregatedpage":
                raise BadRequestError(
                    detail="content_type must reference a SegregatedPage.",
                )

            # Verify the target object exists.
            if not SegregatedPage.objects.filter(pk=object_id).exists():
                raise NotFoundError(
                    detail=f"SegregatedPage with id '{object_id}' not found."
                )

            return self.model.objects.create(
                user_id=user_id,
                note_type=note_type,
                content_type=ct,
                object_id=object_id,
                text=text,
            )

        raise BadRequestError(detail=f"Invalid note_type '{note_type}'.")

    def update_note(
        self,
        user_id: UUID,
        note_id: UUID,
        *,
        text: str,
    ) -> Note:
        """Update the text of a note owned by *user_id*."""
        if not text or not text.strip():
            raise BadRequestError(detail="Note text must not be empty.")

        note: Note = self.get_for_user(user_id, note_id)
        return self.update(note, text=text)

    def delete_note(self, user_id: UUID, note_id: UUID) -> None:
        """Delete a note owned by *user_id*."""
        note: Note = self.get_for_user(user_id, note_id)
        self.delete(note)

    def list_notes(
        self,
        user_id: UUID,
        *,
        note_type: str | None = None,
    ) -> QuerySet[Note]:
        """Return notes for a user, optionally filtered by type."""
        qs: QuerySet[Note] = self.list_for_user(user_id)
        if note_type:
            qs = qs.filter(note_type=note_type)
        return qs

    def get_notes_for_content(
        self,
        user_id: UUID,
        *,
        content_type_id: int,
        object_id: UUID,
    ) -> QuerySet[Note]:
        """Return all notes for a specific content object."""
        return self.list_for_user(user_id).filter(
            content_type_id=content_type_id,
            object_id=object_id,
        )
