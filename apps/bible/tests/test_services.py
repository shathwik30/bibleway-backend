"""Tests for bible services.

Covers:
- SegregatedBibleService (sections, chapters, pages, search, page detail with translation)
- BibleTranslationService (translate_page, invalidate_cache_for_page)
- BookmarkService (create, delete, list)
- HighlightService (create, delete, list, list_for_content)
- NoteService (create, update, delete, list, get_notes_for_content)
"""

from __future__ import annotations
import uuid
from unittest.mock import MagicMock, patch
import pytest
from django.contrib.contenttypes.models import ContentType
from apps.bible.models import (
    Bookmark,
    Highlight,
    Note,
    SegregatedChapter,
    SegregatedPage,
    SegregatedSection,
    TranslatedPageCache,
)

from apps.bible.services import (
    BibleTranslationService,
    BookmarkService,
    HighlightService,
    NoteService,
    SegregatedBibleService,
)

from apps.common.exceptions import BadRequestError, NotFoundError
from conftest import UserFactory


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def section(db):
    return SegregatedSection.objects.create(
        title="Kids Bible",
        age_min=5,
        age_max=8,
        order=0,
        is_active=True,
    )


@pytest.fixture
def section_inactive(db):
    return SegregatedSection.objects.create(
        title="Inactive Section",
        age_min=0,
        age_max=4,
        order=99,
        is_active=False,
    )


@pytest.fixture
def chapter(section):
    return SegregatedChapter.objects.create(
        section=section,
        title="Creation",
        order=0,
        is_active=True,
    )


@pytest.fixture
def chapter_inactive(section):
    return SegregatedChapter.objects.create(
        section=section,
        title="Inactive Chapter",
        order=99,
        is_active=False,
    )


@pytest.fixture
def page(chapter):
    return SegregatedPage.objects.create(
        chapter=chapter,
        title="Day 1",
        content="In the beginning God created the heavens and the earth.",
        order=0,
        is_active=True,
    )


@pytest.fixture
def page_inactive(chapter):
    return SegregatedPage.objects.create(
        chapter=chapter,
        title="Inactive Page",
        content="Hidden content.",
        order=99,
        is_active=False,
    )


@pytest.fixture
def bible_service():
    return SegregatedBibleService()


@pytest.fixture
def translation_service():
    return BibleTranslationService()


@pytest.fixture
def bookmark_service():
    return BookmarkService()


@pytest.fixture
def highlight_service():
    return HighlightService()


@pytest.fixture
def note_service():
    return NoteService()


@pytest.mark.django_db
class TestSegregatedBibleService:
    """Tests for SegregatedBibleService."""

    def test_get_sections_returns_active_only(
        self,
        bible_service,
        section,
        section_inactive,
    ):
        """get_sections only returns active sections."""
        qs = bible_service.get_sections()
        pks = set(qs.values_list("pk", flat=True))
        assert section.pk in pks
        assert section_inactive.pk not in pks

    def test_get_sections_annotates_chapter_count(
        self,
        bible_service,
        section,
        chapter,
    ):
        """get_sections annotates chapter_count (active chapters only)."""
        qs = bible_service.get_sections()
        result = qs.get(pk=section.pk)
        assert result.chapter_count == 1

    def test_get_sections_excludes_inactive_chapters_in_count(
        self,
        bible_service,
        section,
        chapter,
        chapter_inactive,
    ):
        """chapter_count does not include inactive chapters."""
        qs = bible_service.get_sections()
        result = qs.get(pk=section.pk)
        assert result.chapter_count == 1

    def test_get_sections_with_user_age_prioritizes(
        self,
        bible_service,
        section,
        db,
    ):
        """When user_age is provided, matching section is prioritized."""
        SegregatedSection.objects.create(
            title="Teens",
            age_min=13,
            age_max=17,
            order=1,
            is_active=True,
        )
        qs = bible_service.get_sections(user_age=7)
        result = list(qs)
        assert result[0].pk == section.pk
        assert result[0].is_prioritized is True

    def test_get_sections_without_user_age(self, bible_service, section):
        """When user_age is None, is_prioritized defaults to False."""
        qs = bible_service.get_sections(user_age=None)
        result = qs.get(pk=section.pk)
        assert result.is_prioritized is False

    def test_get_chapters_for_section(self, bible_service, section, chapter):
        """get_chapters_for_section returns active chapters for a section."""
        qs = bible_service.get_chapters_for_section(section.pk)
        assert qs.filter(pk=chapter.pk).exists()

    def test_get_chapters_excludes_inactive(
        self,
        bible_service,
        section,
        chapter,
        chapter_inactive,
    ):
        """get_chapters_for_section excludes inactive chapters."""
        qs = bible_service.get_chapters_for_section(section.pk)
        pks = set(qs.values_list("pk", flat=True))
        assert chapter_inactive.pk not in pks

    def test_get_chapters_annotates_page_count(
        self,
        bible_service,
        section,
        chapter,
        page,
    ):
        """Chapters are annotated with page_count."""
        qs = bible_service.get_chapters_for_section(section.pk)
        result = qs.get(pk=chapter.pk)
        assert result.page_count == 1

    def test_get_chapters_for_nonexistent_section(self, bible_service):
        """get_chapters_for_section raises NotFoundError for missing section."""

        with pytest.raises(NotFoundError):
            bible_service.get_chapters_for_section(uuid.uuid4())

    def test_get_pages_for_chapter(self, bible_service, chapter, page):
        """get_pages_for_chapter returns active pages."""
        qs = bible_service.get_pages_for_chapter(chapter.pk)
        assert qs.filter(pk=page.pk).exists()

    def test_get_pages_excludes_inactive(
        self,
        bible_service,
        chapter,
        page,
        page_inactive,
    ):
        """get_pages_for_chapter excludes inactive pages."""
        qs = bible_service.get_pages_for_chapter(chapter.pk)
        pks = set(qs.values_list("pk", flat=True))
        assert page_inactive.pk not in pks

    def test_get_pages_for_nonexistent_chapter(self, bible_service):
        """get_pages_for_chapter raises NotFoundError for missing chapter."""

        with pytest.raises(NotFoundError):
            bible_service.get_pages_for_chapter(uuid.uuid4())

    def test_get_page_detail(self, bible_service, page):
        """get_page_detail returns the page with select_related."""
        result = bible_service.get_page_detail(page.pk)
        assert result.pk == page.pk
        assert result.chapter is not None
        assert result.chapter.section is not None

    def test_get_page_detail_not_found(self, bible_service):
        """get_page_detail raises NotFoundError for missing page."""

        with pytest.raises(NotFoundError):
            bible_service.get_page_detail(uuid.uuid4())

    def test_get_page_detail_inactive_not_found(self, bible_service, page_inactive):
        """get_page_detail raises NotFoundError for inactive page."""

        with pytest.raises(NotFoundError):
            bible_service.get_page_detail(page_inactive.pk)

    def test_get_page_detail_with_translation(self, bible_service, page):
        """get_page_detail replaces content with translation when available."""
        TranslatedPageCache.objects.create(
            page=page,
            language_code="es",
            translated_content="En el principio...",
        )
        result = bible_service.get_page_detail(page.pk, language_code="es")
        assert result.content == "En el principio..."

    def test_get_page_detail_no_translation_keeps_original(self, bible_service, page):
        """get_page_detail keeps original content when no translation exists."""
        result = bible_service.get_page_detail(page.pk, language_code="fr")
        assert result.content == page.content

    def test_get_page_detail_english_no_replacement(self, bible_service, page):
        """get_page_detail skips translation for language_code='en'."""
        TranslatedPageCache.objects.create(
            page=page,
            language_code="en",
            translated_content="Should not be used.",
        )
        result = bible_service.get_page_detail(page.pk, language_code="en")
        assert result.content == page.content

    def test_search_content_by_title(self, bible_service, page):
        """search_content finds pages by title."""
        qs = bible_service.search_content("Day 1")
        assert qs.filter(pk=page.pk).exists()

    def test_search_content_by_content(self, bible_service, page):
        """search_content finds pages by content body."""
        qs = bible_service.search_content("heavens and the earth")
        assert qs.filter(pk=page.pk).exists()

    def test_search_content_empty_query_raises(self, bible_service):
        """search_content raises BadRequestError for empty query."""

        with pytest.raises(BadRequestError):
            bible_service.search_content("")

    def test_search_content_whitespace_only_raises(self, bible_service):
        """search_content raises BadRequestError for whitespace-only query."""

        with pytest.raises(BadRequestError):
            bible_service.search_content("   ")

    def test_search_content_scoped_to_section(self, bible_service, section, page, db):
        """search_content can be scoped to a specific section."""
        other_section = SegregatedSection.objects.create(
            title="Other",
            age_min=9,
            age_max=12,
            order=1,
            is_active=True,
        )
        other_ch = SegregatedChapter.objects.create(
            section=other_section,
            title="Other Ch",
            order=0,
            is_active=True,
        )
        other_page = SegregatedPage.objects.create(
            chapter=other_ch,
            title="Day 1 also",
            content="Also in the beginning.",
            order=0,
            is_active=True,
        )
        qs = bible_service.search_content("Day 1", section_id=section.pk)
        pks = set(qs.values_list("pk", flat=True))
        assert page.pk in pks
        assert other_page.pk not in pks

    def test_search_content_excludes_inactive(self, bible_service, page_inactive):
        """search_content excludes inactive pages."""
        qs = bible_service.search_content("Hidden")
        assert not qs.filter(pk=page_inactive.pk).exists()


@pytest.mark.django_db
class TestBibleTranslationService:
    """Tests for BibleTranslationService."""

    def test_translate_page_cache_hit(self, translation_service, page):
        """translate_page returns cached translation without calling Google."""
        cache = TranslatedPageCache.objects.create(
            page=page,
            language_code="es",
            translated_content="Cached translation.",
        )
        result = translation_service.translate_page(page.pk, "es")
        assert result.pk == cache.pk
        assert result.translated_content == "Cached translation."

    @patch.object(BibleTranslationService, "_call_google_translate")
    def test_translate_page_cache_miss(self, mock_translate, translation_service, page):
        """translate_page calls Google Translate on cache miss."""
        mock_translate.return_value = "Translated text"
        result = translation_service.translate_page(page.pk, "de")
        assert result.translated_content == "Translated text"
        assert result.language_code == "de"
        mock_translate.assert_called_once_with(page.content, target_language="de")
        assert TranslatedPageCache.objects.filter(
            page=page,
            language_code="de",
        ).exists()

    def test_translate_page_not_found(self, translation_service):
        """translate_page raises NotFoundError for missing page."""

        with pytest.raises(NotFoundError):
            translation_service.translate_page(uuid.uuid4(), "es")

    def test_translate_page_inactive_not_found(
        self, translation_service, page_inactive
    ):
        """translate_page raises NotFoundError for inactive page."""

        with pytest.raises(NotFoundError):
            translation_service.translate_page(page_inactive.pk, "es")

    def test_invalidate_cache_for_page(self, translation_service, page):
        """invalidate_cache_for_page deletes all cached translations for a page."""
        TranslatedPageCache.objects.create(
            page=page,
            language_code="es",
            translated_content="ES",
        )
        TranslatedPageCache.objects.create(
            page=page,
            language_code="fr",
            translated_content="FR",
        )
        count = translation_service.invalidate_cache_for_page(page.pk)
        assert count == 2
        assert TranslatedPageCache.objects.filter(page=page).count() == 0

    def test_invalidate_cache_for_page_no_entries(self, translation_service, page):
        """invalidate_cache_for_page returns 0 when no entries exist."""
        count = translation_service.invalidate_cache_for_page(page.pk)
        assert count == 0

    @patch("requests.post")
    def test_call_google_translate_success(self, mock_post, page):
        """_call_google_translate returns translated text on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "translations": [{"translatedText": "Translated text from Google."}]
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        result = BibleTranslationService._call_google_translate(
            "Original text",
            target_language="es",
        )
        assert result == "Translated text from Google."

    @patch("requests.post")
    def test_call_google_translate_no_results(self, mock_post):
        """_call_google_translate raises BadRequestError when no results returned."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"translations": []}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with pytest.raises(BadRequestError, match="no results"):
            BibleTranslationService._call_google_translate(
                "Text",
                target_language="es",
            )

    @patch("requests.post")
    def test_call_google_translate_network_error(self, mock_post):
        """_call_google_translate raises BadRequestError on network failure."""
        import requests

        mock_post.side_effect = requests.RequestException("timeout")

        with pytest.raises(BadRequestError, match="temporarily unavailable"):
            BibleTranslationService._call_google_translate(
                "Text",
                target_language="es",
            )

    def test_call_google_translate_no_api_key(self, settings):
        """_call_google_translate raises BadRequestError when API key is missing."""
        settings.GOOGLE_TRANSLATE_API_KEY = ""

        with pytest.raises(BadRequestError, match="not configured"):
            BibleTranslationService._call_google_translate(
                "Text",
                target_language="es",
            )


@pytest.mark.django_db
class TestBookmarkService:
    """Tests for BookmarkService."""

    def test_create_api_bible_bookmark(self, bookmark_service, user):
        """create_bookmark creates an API Bible bookmark."""
        bm = bookmark_service.create_bookmark(
            user.pk,
            bookmark_type="api_bible",
            verse_reference="JHN.3.16",
        )
        assert bm.pk is not None
        assert bm.bookmark_type == "api_bible"
        assert bm.verse_reference == "JHN.3.16"

    def test_create_api_bible_bookmark_missing_verse(self, bookmark_service, user):
        """create_bookmark raises BadRequestError when verse_reference is missing."""

        with pytest.raises(BadRequestError, match="verse_reference"):
            bookmark_service.create_bookmark(
                user.pk,
                bookmark_type="api_bible",
                verse_reference="",
            )

    def test_create_segregated_bookmark(self, bookmark_service, user, page):
        """create_bookmark creates a segregated bookmark."""
        ct = ContentType.objects.get_for_model(page)
        bm = bookmark_service.create_bookmark(
            user.pk,
            bookmark_type="segregated",
            content_type_id=ct.pk,
            object_id=page.pk,
        )
        assert bm.bookmark_type == "segregated"
        assert bm.content_type == ct
        assert bm.object_id == page.pk

    def test_create_segregated_bookmark_missing_content_type(
        self,
        bookmark_service,
        user,
    ):
        """create_bookmark raises BadRequestError when content_type is missing."""

        with pytest.raises(BadRequestError, match="content_type"):
            bookmark_service.create_bookmark(
                user.pk,
                bookmark_type="segregated",
            )

    def test_create_segregated_bookmark_invalid_content_type(
        self,
        bookmark_service,
        user,
    ):
        """create_bookmark raises BadRequestError for invalid content_type."""
        ct = ContentType.objects.get(app_label="accounts", model="user")

        with pytest.raises(BadRequestError, match="content_type must reference"):
            bookmark_service.create_bookmark(
                user.pk,
                bookmark_type="segregated",
                content_type_id=ct.pk,
                object_id=uuid.uuid4(),
            )

    def test_create_segregated_bookmark_nonexistent_object(
        self,
        bookmark_service,
        user,
        page,
    ):
        """create_bookmark raises NotFoundError for nonexistent target object."""
        ct = ContentType.objects.get_for_model(page)

        with pytest.raises(NotFoundError):
            bookmark_service.create_bookmark(
                user.pk,
                bookmark_type="segregated",
                content_type_id=ct.pk,
                object_id=uuid.uuid4(),
            )

    def test_create_bookmark_invalid_type(self, bookmark_service, user):
        """create_bookmark raises BadRequestError for invalid bookmark_type."""

        with pytest.raises(BadRequestError, match="Invalid bookmark_type"):
            bookmark_service.create_bookmark(
                user.pk,
                bookmark_type="unknown_type",
            )

    def test_delete_bookmark(self, bookmark_service, user):
        """delete_bookmark removes the bookmark."""
        bm = bookmark_service.create_bookmark(
            user.pk,
            bookmark_type="api_bible",
            verse_reference="JHN.3.16",
        )
        bookmark_service.delete_bookmark(user.pk, bm.pk)
        assert not Bookmark.objects.filter(pk=bm.pk).exists()

    def test_delete_bookmark_wrong_user(self, bookmark_service, user):
        """delete_bookmark raises NotFoundError when user does not own the bookmark."""
        bm = bookmark_service.create_bookmark(
            user.pk,
            bookmark_type="api_bible",
            verse_reference="JHN.3.16",
        )
        other = UserFactory()

        with pytest.raises(NotFoundError):
            bookmark_service.delete_bookmark(other.pk, bm.pk)

    def test_list_bookmarks(self, bookmark_service, user):
        """list_bookmarks returns all bookmarks for a user."""
        bookmark_service.create_bookmark(
            user.pk,
            bookmark_type="api_bible",
            verse_reference="A",
        )
        bookmark_service.create_bookmark(
            user.pk,
            bookmark_type="api_bible",
            verse_reference="B",
        )
        qs = bookmark_service.list_bookmarks(user.pk)
        assert qs.count() == 2

    def test_list_bookmarks_filtered_by_type(self, bookmark_service, user, page):
        """list_bookmarks can filter by bookmark_type."""
        bookmark_service.create_bookmark(
            user.pk,
            bookmark_type="api_bible",
            verse_reference="JHN.3.16",
        )
        ct = ContentType.objects.get_for_model(page)
        bookmark_service.create_bookmark(
            user.pk,
            bookmark_type="segregated",
            content_type_id=ct.pk,
            object_id=page.pk,
        )
        api_qs = bookmark_service.list_bookmarks(user.pk, bookmark_type="api_bible")
        seg_qs = bookmark_service.list_bookmarks(user.pk, bookmark_type="segregated")
        assert api_qs.count() == 1
        assert seg_qs.count() == 1

    def test_list_bookmarks_user_isolation(self, bookmark_service, user):
        """list_bookmarks only returns bookmarks for the specified user."""
        other = UserFactory()
        bookmark_service.create_bookmark(
            user.pk,
            bookmark_type="api_bible",
            verse_reference="A",
        )
        bookmark_service.create_bookmark(
            other.pk,
            bookmark_type="api_bible",
            verse_reference="B",
        )
        qs = bookmark_service.list_bookmarks(user.pk)
        assert qs.count() == 1
        assert qs.first().user_id == user.pk

    def test_create_segregated_bookmark_for_chapter(
        self, bookmark_service, user, chapter
    ):
        """create_bookmark works for SegregatedChapter content type."""
        ct = ContentType.objects.get_for_model(chapter)
        bm = bookmark_service.create_bookmark(
            user.pk,
            bookmark_type="segregated",
            content_type_id=ct.pk,
            object_id=chapter.pk,
        )
        assert bm.content_type == ct


@pytest.mark.django_db
class TestHighlightService:
    """Tests for HighlightService."""

    def test_create_api_bible_highlight(self, highlight_service, user):
        """create_highlight creates an API Bible highlight."""
        h = highlight_service.create_highlight(
            user.pk,
            highlight_type="api_bible",
            verse_reference="ROM.8.28",
            color="green",
        )
        assert h.pk is not None
        assert h.color == "green"

    def test_create_api_bible_highlight_missing_verse(self, highlight_service, user):
        """create_highlight raises BadRequestError when verse_reference is missing."""

        with pytest.raises(BadRequestError, match="verse_reference"):
            highlight_service.create_highlight(
                user.pk,
                highlight_type="api_bible",
                verse_reference="",
            )

    def test_create_segregated_highlight(self, highlight_service, user, page):
        """create_highlight creates a segregated highlight."""
        ct = ContentType.objects.get_for_model(page)
        h = highlight_service.create_highlight(
            user.pk,
            highlight_type="segregated",
            content_type_id=ct.pk,
            object_id=page.pk,
            selection_start=0,
            selection_end=10,
            color="blue",
        )
        assert h.selection_start == 0
        assert h.selection_end == 10

    def test_create_segregated_highlight_missing_offsets(
        self,
        highlight_service,
        user,
        page,
    ):
        """create_highlight raises BadRequestError when offsets are missing."""
        ct = ContentType.objects.get_for_model(page)

        with pytest.raises(BadRequestError, match="selection_start"):
            highlight_service.create_highlight(
                user.pk,
                highlight_type="segregated",
                content_type_id=ct.pk,
                object_id=page.pk,
            )

    def test_create_segregated_highlight_invalid_offsets(
        self,
        highlight_service,
        user,
        page,
    ):
        """create_highlight raises BadRequestError when start >= end."""
        ct = ContentType.objects.get_for_model(page)

        with pytest.raises(BadRequestError, match="selection_start must be less"):
            highlight_service.create_highlight(
                user.pk,
                highlight_type="segregated",
                content_type_id=ct.pk,
                object_id=page.pk,
                selection_start=10,
                selection_end=5,
            )

    def test_create_segregated_highlight_equal_offsets(
        self,
        highlight_service,
        user,
        page,
    ):
        """create_highlight raises BadRequestError when start == end."""
        ct = ContentType.objects.get_for_model(page)

        with pytest.raises(BadRequestError, match="selection_start must be less"):
            highlight_service.create_highlight(
                user.pk,
                highlight_type="segregated",
                content_type_id=ct.pk,
                object_id=page.pk,
                selection_start=5,
                selection_end=5,
            )

    def test_create_segregated_highlight_wrong_content_type(
        self,
        highlight_service,
        user,
    ):
        """create_highlight raises BadRequestError for non-SegregatedPage content_type."""
        ct = ContentType.objects.get(app_label="bible", model="segregatedchapter")

        with pytest.raises(BadRequestError, match="content_type must reference"):
            highlight_service.create_highlight(
                user.pk,
                highlight_type="segregated",
                content_type_id=ct.pk,
                object_id=uuid.uuid4(),
                selection_start=0,
                selection_end=5,
            )

    def test_create_segregated_highlight_nonexistent_page(
        self,
        highlight_service,
        user,
        page,
    ):
        """create_highlight raises NotFoundError for nonexistent page."""
        ct = ContentType.objects.get_for_model(page)

        with pytest.raises(NotFoundError):
            highlight_service.create_highlight(
                user.pk,
                highlight_type="segregated",
                content_type_id=ct.pk,
                object_id=uuid.uuid4(),
                selection_start=0,
                selection_end=5,
            )

    def test_create_highlight_invalid_type(self, highlight_service, user):
        """create_highlight raises BadRequestError for invalid highlight_type."""

        with pytest.raises(BadRequestError, match="Invalid highlight_type"):
            highlight_service.create_highlight(
                user.pk,
                highlight_type="bad_type",
            )

    def test_delete_highlight(self, highlight_service, user):
        """delete_highlight removes the highlight."""
        h = highlight_service.create_highlight(
            user.pk,
            highlight_type="api_bible",
            verse_reference="JHN.1.1",
        )
        highlight_service.delete_highlight(user.pk, h.pk)
        assert not Highlight.objects.filter(pk=h.pk).exists()

    def test_delete_highlight_wrong_user(self, highlight_service, user):
        """delete_highlight raises NotFoundError for wrong user."""
        h = highlight_service.create_highlight(
            user.pk,
            highlight_type="api_bible",
            verse_reference="JHN.1.1",
        )
        other = UserFactory()

        with pytest.raises(NotFoundError):
            highlight_service.delete_highlight(other.pk, h.pk)

    def test_list_highlights(self, highlight_service, user):
        """list_highlights returns all highlights for a user."""
        highlight_service.create_highlight(
            user.pk,
            highlight_type="api_bible",
            verse_reference="A",
        )
        highlight_service.create_highlight(
            user.pk,
            highlight_type="api_bible",
            verse_reference="B",
        )
        qs = highlight_service.list_highlights(user.pk)
        assert qs.count() == 2

    def test_list_highlights_filtered_by_type(self, highlight_service, user, page):
        """list_highlights can filter by highlight_type."""
        highlight_service.create_highlight(
            user.pk,
            highlight_type="api_bible",
            verse_reference="JHN.1.1",
        )
        ct = ContentType.objects.get_for_model(page)
        highlight_service.create_highlight(
            user.pk,
            highlight_type="segregated",
            content_type_id=ct.pk,
            object_id=page.pk,
            selection_start=0,
            selection_end=5,
        )
        api_qs = highlight_service.list_highlights(user.pk, highlight_type="api_bible")
        seg_qs = highlight_service.list_highlights(user.pk, highlight_type="segregated")
        assert api_qs.count() == 1
        assert seg_qs.count() == 1

    def test_list_highlights_for_content(self, highlight_service, user, page):
        """list_highlights_for_content returns highlights for a specific object."""
        ct = ContentType.objects.get_for_model(page)
        highlight_service.create_highlight(
            user.pk,
            highlight_type="segregated",
            content_type_id=ct.pk,
            object_id=page.pk,
            selection_start=0,
            selection_end=5,
        )
        highlight_service.create_highlight(
            user.pk,
            highlight_type="segregated",
            content_type_id=ct.pk,
            object_id=page.pk,
            selection_start=10,
            selection_end=20,
        )
        qs = highlight_service.list_highlights_for_content(
            user.pk,
            content_type_id=ct.pk,
            object_id=page.pk,
        )
        assert qs.count() == 2


@pytest.mark.django_db
class TestNoteService:
    """Tests for NoteService."""

    def test_create_api_bible_note(self, note_service, user):
        """create_note creates an API Bible note."""
        note = note_service.create_note(
            user.pk,
            note_type="api_bible",
            text="My thoughts on this verse.",
            verse_reference="JHN.3.16",
        )
        assert note.pk is not None
        assert note.text == "My thoughts on this verse."

    def test_create_api_bible_note_missing_verse(self, note_service, user):
        """create_note raises BadRequestError when verse_reference is missing."""

        with pytest.raises(BadRequestError, match="verse_reference"):
            note_service.create_note(
                user.pk,
                note_type="api_bible",
                text="Some note.",
                verse_reference="",
            )

    def test_create_note_empty_text_raises(self, note_service, user):
        """create_note raises BadRequestError when text is empty."""

        with pytest.raises(BadRequestError, match="Note text must not be empty"):
            note_service.create_note(
                user.pk,
                note_type="api_bible",
                text="",
                verse_reference="JHN.3.16",
            )

    def test_create_note_whitespace_only_text_raises(self, note_service, user):
        """create_note raises BadRequestError when text is whitespace only."""

        with pytest.raises(BadRequestError, match="Note text must not be empty"):
            note_service.create_note(
                user.pk,
                note_type="api_bible",
                text="   ",
                verse_reference="JHN.3.16",
            )

    def test_create_segregated_note(self, note_service, user, page):
        """create_note creates a segregated note."""
        ct = ContentType.objects.get_for_model(page)
        note = note_service.create_note(
            user.pk,
            note_type="segregated",
            text="Page notes.",
            content_type_id=ct.pk,
            object_id=page.pk,
        )
        assert note.note_type == "segregated"
        assert note.object_id == page.pk

    def test_create_segregated_note_missing_content_type(self, note_service, user):
        """create_note raises BadRequestError when content_type is missing."""

        with pytest.raises(BadRequestError, match="content_type"):
            note_service.create_note(
                user.pk,
                note_type="segregated",
                text="A note.",
            )

    def test_create_segregated_note_wrong_content_type(self, note_service, user):
        """create_note raises BadRequestError for non-SegregatedPage content_type."""
        ct = ContentType.objects.get(app_label="bible", model="segregatedchapter")

        with pytest.raises(BadRequestError, match="content_type must reference"):
            note_service.create_note(
                user.pk,
                note_type="segregated",
                text="A note.",
                content_type_id=ct.pk,
                object_id=uuid.uuid4(),
            )

    def test_create_segregated_note_nonexistent_page(self, note_service, user, page):
        """create_note raises NotFoundError for nonexistent target page."""
        ct = ContentType.objects.get_for_model(page)

        with pytest.raises(NotFoundError):
            note_service.create_note(
                user.pk,
                note_type="segregated",
                text="A note.",
                content_type_id=ct.pk,
                object_id=uuid.uuid4(),
            )

    def test_create_note_invalid_type(self, note_service, user):
        """create_note raises BadRequestError for invalid note_type."""

        with pytest.raises(BadRequestError, match="Invalid note_type"):
            note_service.create_note(
                user.pk,
                note_type="bad_type",
                text="A note.",
            )

    def test_update_note(self, note_service, user):
        """update_note changes the text."""
        note = note_service.create_note(
            user.pk,
            note_type="api_bible",
            text="Original text.",
            verse_reference="JHN.3.16",
        )
        updated = note_service.update_note(user.pk, note.pk, text="Updated text.")
        assert updated.text == "Updated text."

    def test_update_note_empty_text_raises(self, note_service, user):
        """update_note raises BadRequestError when text is empty."""
        note = note_service.create_note(
            user.pk,
            note_type="api_bible",
            text="Original.",
            verse_reference="JHN.3.16",
        )

        with pytest.raises(BadRequestError, match="Note text must not be empty"):
            note_service.update_note(user.pk, note.pk, text="")

    def test_update_note_wrong_user(self, note_service, user):
        """update_note raises NotFoundError for wrong user."""
        note = note_service.create_note(
            user.pk,
            note_type="api_bible",
            text="My note.",
            verse_reference="A",
        )
        other = UserFactory()

        with pytest.raises(NotFoundError):
            note_service.update_note(other.pk, note.pk, text="Hack!")

    def test_delete_note(self, note_service, user):
        """delete_note removes the note."""
        note = note_service.create_note(
            user.pk,
            note_type="api_bible",
            text="Delete me.",
            verse_reference="A",
        )
        note_service.delete_note(user.pk, note.pk)
        assert not Note.objects.filter(pk=note.pk).exists()

    def test_delete_note_wrong_user(self, note_service, user):
        """delete_note raises NotFoundError for wrong user."""
        note = note_service.create_note(
            user.pk,
            note_type="api_bible",
            text="My note.",
            verse_reference="A",
        )
        other = UserFactory()

        with pytest.raises(NotFoundError):
            note_service.delete_note(other.pk, note.pk)

    def test_list_notes(self, note_service, user):
        """list_notes returns all notes for a user."""
        note_service.create_note(
            user.pk,
            note_type="api_bible",
            text="N1",
            verse_reference="A",
        )
        note_service.create_note(
            user.pk,
            note_type="api_bible",
            text="N2",
            verse_reference="B",
        )
        qs = note_service.list_notes(user.pk)
        assert qs.count() == 2

    def test_list_notes_filtered_by_type(self, note_service, user, page):
        """list_notes can filter by note_type."""
        note_service.create_note(
            user.pk,
            note_type="api_bible",
            text="N1",
            verse_reference="A",
        )
        ct = ContentType.objects.get_for_model(page)
        note_service.create_note(
            user.pk,
            note_type="segregated",
            text="N2",
            content_type_id=ct.pk,
            object_id=page.pk,
        )
        api_qs = note_service.list_notes(user.pk, note_type="api_bible")
        seg_qs = note_service.list_notes(user.pk, note_type="segregated")
        assert api_qs.count() == 1
        assert seg_qs.count() == 1

    def test_get_notes_for_content(self, note_service, user, page):
        """get_notes_for_content returns notes for a specific content object."""
        ct = ContentType.objects.get_for_model(page)
        note_service.create_note(
            user.pk,
            note_type="segregated",
            text="Note 1",
            content_type_id=ct.pk,
            object_id=page.pk,
        )
        note_service.create_note(
            user.pk,
            note_type="segregated",
            text="Note 2",
            content_type_id=ct.pk,
            object_id=page.pk,
        )
        qs = note_service.get_notes_for_content(
            user.pk,
            content_type_id=ct.pk,
            object_id=page.pk,
        )
        assert qs.count() == 2

    def test_list_notes_user_isolation(self, note_service, user):
        """list_notes only returns notes for the specified user."""
        other = UserFactory()
        note_service.create_note(
            user.pk,
            note_type="api_bible",
            text="Mine",
            verse_reference="A",
        )
        note_service.create_note(
            other.pk,
            note_type="api_bible",
            text="Theirs",
            verse_reference="B",
        )
        qs = note_service.list_notes(user.pk)
        assert qs.count() == 1
        assert qs.first().user_id == user.pk


@pytest.mark.django_db
class TestSearchContentFallback:
    """Tests search_content with SQLite fallback (icontains).

    On PostgreSQL, SearchVector/SearchRank is used. On SQLite (test DB),
    the service falls back to icontains filtering.
    """

    def test_search_by_title_returns_matching_pages(self, section, chapter):
        """Pages matching query in title are returned."""
        service = SegregatedBibleService()
        SegregatedPage.objects.create(
            chapter=chapter, title="Creation Story", content="text", order=1
        )
        SegregatedPage.objects.create(
            chapter=chapter, title="Exodus", content="other", order=2
        )
        results = list(service.search_content("Creation"))
        assert len(results) == 1
        assert results[0].title == "Creation Story"

    def test_search_by_content_returns_matching_pages(self, section, chapter):
        """Pages matching query in content are returned."""
        service = SegregatedBibleService()
        SegregatedPage.objects.create(
            chapter=chapter, title="Page A", content="The flood narrative", order=1
        )
        SegregatedPage.objects.create(
            chapter=chapter, title="Page B", content="Other text", order=2
        )
        results = list(service.search_content("flood"))
        assert len(results) == 1
        assert results[0].title == "Page A"

    def test_search_no_results(self, section, chapter):
        """Search with no matches returns empty queryset."""
        service = SegregatedBibleService()
        SegregatedPage.objects.create(
            chapter=chapter, title="Page", content="text", order=1
        )
        results = list(service.search_content("nonexistent"))
        assert len(results) == 0

    def test_search_excludes_inactive(self, section, chapter):
        """Inactive pages are excluded from search results."""
        service = SegregatedBibleService()
        SegregatedPage.objects.create(
            chapter=chapter,
            title="Active flood",
            content="text",
            order=1,
            is_active=True,
        )
        SegregatedPage.objects.create(
            chapter=chapter,
            title="Inactive flood",
            content="text",
            order=2,
            is_active=False,
        )
        results = list(service.search_content("flood"))
        assert len(results) == 1
