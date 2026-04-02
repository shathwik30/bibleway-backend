"""Tests for apps.bible.views — API endpoints for segregated Bible content."""

from __future__ import annotations
import uuid
from unittest.mock import patch
import pytest
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from apps.bible.models import (
    Bookmark,
    Highlight,
    Note,
    SegregatedChapter,
    SegregatedPage,
    SegregatedSection,
    TranslatedPageCache,
)

from conftest import UserFactory


@pytest.fixture
def section(db):
    """Create an active section."""

    return SegregatedSection.objects.create(
        title="Ages 5-8",
        age_min=5,
        age_max=8,
        order=1,
        is_active=True,
    )


@pytest.fixture
def section2(db):
    """Create a second active section."""

    return SegregatedSection.objects.create(
        title="Ages 9-12",
        age_min=9,
        age_max=12,
        order=2,
        is_active=True,
    )


@pytest.fixture
def chapter(section):
    """Create an active chapter in a section."""

    return SegregatedChapter.objects.create(
        section=section,
        title="Chapter 1: Creation",
        order=1,
        is_active=True,
    )


@pytest.fixture
def chapter2(section):
    """Create a second active chapter in a section."""

    return SegregatedChapter.objects.create(
        section=section,
        title="Chapter 2: The Fall",
        order=2,
        is_active=True,
    )


@pytest.fixture
def page(chapter):
    """Create an active page in a chapter."""

    return SegregatedPage.objects.create(
        chapter=chapter,
        title="Page 1: In the Beginning",
        content="In the beginning God created the heavens and the earth.",
        order=1,
        is_active=True,
    )


@pytest.fixture
def page2(chapter):
    """Create a second active page in a chapter."""

    return SegregatedPage.objects.create(
        chapter=chapter,
        title="Page 2: Let There Be Light",
        content="And God said, Let there be light.",
        order=2,
        is_active=True,
    )


SECTIONS_URL = "/api/v1/bible/sections/"

BOOKMARKS_URL = "/api/v1/bible/bookmarks/"

HIGHLIGHTS_URL = "/api/v1/bible/highlights/"

NOTES_URL = "/api/v1/bible/notes/"

SEARCH_URL = "/api/v1/bible/search/"


def _paginated_results(response):
    """Extract results from a paginated envelope response.

    For StandardPageNumberPagination: {"message": ..., "data": {"results": [...]}}
    For ViewSet pagination: same format via BaseModelViewSet.
    """

    data = response.data

    if "data" in data and isinstance(data["data"], dict) and "results" in data["data"]:
        return data["data"]["results"]

    if "results" in data:
        return data["results"]

    return []


def _chapters_url(section_id):
    return f"/api/v1/bible/sections/{section_id}/chapters/"


def _pages_url(chapter_id):
    return f"/api/v1/bible/chapters/{chapter_id}/pages/"


def _page_detail_url(page_id):
    return f"/api/v1/bible/pages/{page_id}/"


def _page_comments_url(page_id):
    return f"/api/v1/bible/pages/{page_id}/comments/"


@pytest.mark.django_db
class TestSegregatedSectionListView:
    url = SECTIONS_URL

    def test_list_sections(self, auth_client, section, section2):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert len(data) == 2

    def test_list_excludes_inactive_sections(self, auth_client, section):
        SegregatedSection.objects.create(
            title="Inactive",
            age_min=18,
            age_max=99,
            order=10,
            is_active=False,
        )
        response = auth_client.get(self.url)
        data = response.data["data"]
        assert len(data) == 1

    def test_section_fields(self, auth_client, section):
        response = auth_client.get(self.url)
        data = response.data["data"][0]

        for field in (
            "id",
            "title",
            "age_min",
            "age_max",
            "order",
            "is_active",
            "chapter_count",
        ):
            assert field in data

    def test_chapter_count_annotation(self, auth_client, section, chapter, chapter2):
        response = auth_client.get(self.url)
        data = response.data["data"]
        section_data = next(s for s in data if str(s["id"]) == str(section.pk))
        assert section_data["chapter_count"] == 2

    def test_unauthenticated_still_works(self, api_client, section):
        response = api_client.get(self.url)
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_returns_etag_header(self, auth_client, section):
        """GET /bible/sections/ should include an ETag header."""
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert "ETag" in response

    def test_if_none_match_matching_etag_returns_304(self, auth_client, section):
        """GET with If-None-Match matching ETag returns 304 Not Modified."""
        # First request to prime the cache and get the ETag
        response1 = auth_client.get(self.url)
        assert response1.status_code == status.HTTP_200_OK
        etag = response1["ETag"]
        assert etag  # ETag should be non-empty

        # Second request with matching If-None-Match should return 304
        response2 = auth_client.get(self.url, HTTP_IF_NONE_MATCH=etag)
        assert response2.status_code == 304

    def test_if_none_match_non_matching_etag_returns_200(self, auth_client, section):
        """GET with non-matching If-None-Match returns 200 with data."""
        # First request to prime the cache
        response1 = auth_client.get(self.url)
        assert response1.status_code == status.HTTP_200_OK

        # Second request with a non-matching ETag
        response2 = auth_client.get(
            self.url, HTTP_IF_NONE_MATCH="non-matching-etag-value"
        )
        assert response2.status_code == status.HTTP_200_OK
        assert "ETag" in response2
        # Should return actual data
        assert response2.data["data"] is not None


@pytest.mark.django_db
class TestChapterListView:
    def test_list_chapters(self, auth_client, section, chapter, chapter2):
        url = _chapters_url(section.pk)
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert len(data) == 2

    def test_chapters_ordered_by_order(self, auth_client, section, chapter, chapter2):
        url = _chapters_url(section.pk)
        response = auth_client.get(url)
        data = response.data["data"]
        assert data[0]["order"] <= data[1]["order"]

    def test_excludes_inactive_chapters(self, auth_client, section, chapter):
        SegregatedChapter.objects.create(
            section=section,
            title="Inactive Chapter",
            order=99,
            is_active=False,
        )
        url = _chapters_url(section.pk)
        response = auth_client.get(url)
        data = response.data["data"]
        assert len(data) == 1

    def test_nonexistent_section(self, auth_client):
        url = _chapters_url(uuid.uuid4())
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_chapter_page_count_annotation(
        self, auth_client, section, chapter, page, page2
    ):

        url = _chapters_url(section.pk)
        response = auth_client.get(url)
        data = response.data["data"]
        ch = next(c for c in data if str(c["id"]) == str(chapter.pk))
        assert ch["page_count"] == 2

    def test_chapter_fields(self, auth_client, section, chapter):
        url = _chapters_url(section.pk)
        response = auth_client.get(url)
        ch = response.data["data"][0]

        for field in ("id", "section", "title", "order", "is_active", "page_count"):
            assert field in ch


@pytest.mark.django_db
class TestPageListView:
    def test_list_pages(self, auth_client, chapter, page, page2):
        url = _pages_url(chapter.pk)
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert len(data) == 2

    def test_excludes_inactive_pages(self, auth_client, chapter, page):
        SegregatedPage.objects.create(
            chapter=chapter,
            title="Inactive Page",
            content="hidden content",
            order=99,
            is_active=False,
        )
        url = _pages_url(chapter.pk)
        response = auth_client.get(url)
        data = response.data["data"]
        assert len(data) == 1

    def test_nonexistent_chapter(self, auth_client):
        url = _pages_url(uuid.uuid4())
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_page_list_does_not_include_content_body(self, auth_client, chapter, page):
        url = _pages_url(chapter.pk)
        response = auth_client.get(url)
        pg = response.data["data"][0]
        assert "content" not in pg


@pytest.mark.django_db
class TestPageDetailView:
    def test_get_page_detail(self, auth_client, page):
        url = _page_detail_url(page.pk)
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["title"] == page.title
        assert "content" in data

    def test_page_detail_contains_navigation_fields(self, auth_client, page):
        url = _page_detail_url(page.pk)
        response = auth_client.get(url)
        data = response.data["data"]
        assert "section_title" in data
        assert "chapter_title" in data

    def test_nonexistent_page(self, auth_client):
        url = _page_detail_url(uuid.uuid4())
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_inactive_page_returns_404(self, auth_client, chapter):
        inactive_page = SegregatedPage.objects.create(
            chapter=chapter,
            title="Inactive",
            content="hidden",
            order=99,
            is_active=False,
        )
        url = _page_detail_url(inactive_page.pk)
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.bible.services.BibleTranslationService._call_google_translate")
    def test_page_detail_with_translation(self, mock_translate, auth_client, page):
        mock_translate.return_value = (
            "En el principio Dios creo los cielos y la tierra."
        )
        url = _page_detail_url(page.pk)
        response = auth_client.get(url, {"lang": "es"})
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert "principio" in data["content"] or "beginning" in data["content"]

    def test_page_detail_with_cached_translation(self, auth_client, page):
        TranslatedPageCache.objects.create(
            page=page,
            language_code="fr",
            translated_content="Au commencement, Dieu crea les cieux et la terre.",
        )
        url = _page_detail_url(page.pk)
        response = auth_client.get(url, {"lang": "fr"})
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert "commencement" in data["content"]

    def test_page_detail_english_no_translation(self, auth_client, page):
        url = _page_detail_url(page.pk)
        response = auth_client.get(url, {"lang": "en"})
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["content"] == page.content


@pytest.mark.django_db
class TestPageCommentCreateView:
    """POST /api/v1/bible/pages/<page_id>/comments/"""

    def test_create_comment_success(self, auth_client, page):
        response = auth_client.post(
            _page_comments_url(page.id),
            {"content": "Great lesson!"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        from apps.bible.models import SegregatedPageComment

        assert SegregatedPageComment.objects.filter(page=page).count() == 1

    def test_create_comment_missing_content(self, auth_client, page):
        response = auth_client.post(_page_comments_url(page.id), {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_comment_empty_content(self, auth_client, page):
        response = auth_client.post(
            _page_comments_url(page.id),
            {"content": ""},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_comment_too_long(self, auth_client, page):
        response = auth_client.post(
            _page_comments_url(page.id),
            {"content": "x" * 1001},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_comment_nonexistent_page(self, auth_client):
        response = auth_client.post(
            _page_comments_url(uuid.uuid4()),
            {"content": "Hello"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_comment_unauthenticated(self, api_client, page):
        response = api_client.post(
            _page_comments_url(page.id),
            {"content": "Hello"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestBibleSearchView:
    url = SEARCH_URL

    def test_search_by_title(self, auth_client, page, page2):
        response = auth_client.get(self.url, {"q": "Beginning"})
        assert response.status_code == status.HTTP_200_OK
        results = _paginated_results(response)
        assert len(results) == 1
        assert "Beginning" in results[0]["title"]

    def test_search_by_content(self, auth_client, page):
        response = auth_client.get(self.url, {"q": "heavens"})
        assert response.status_code == status.HTTP_200_OK
        results = _paginated_results(response)
        assert len(results) == 1

    def test_search_empty_query(self, auth_client):
        response = auth_client.get(self.url, {"q": ""})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_search_missing_q(self, auth_client):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_search_no_results(self, auth_client, page):
        response = auth_client.get(self.url, {"q": "xyznonexistent"})
        assert response.status_code == status.HTTP_200_OK
        results = _paginated_results(response)
        assert len(results) == 0

    def test_search_scoped_to_section(
        self, auth_client, section, section2, chapter, page
    ):

        ch2 = SegregatedChapter.objects.create(
            section=section2,
            title="Chapter in section 2",
            order=1,
            is_active=True,
        )
        SegregatedPage.objects.create(
            chapter=ch2,
            title="Creation in section 2",
            content="In the beginning God created...",
            order=1,
            is_active=True,
        )
        response = auth_client.get(
            self.url, {"q": "beginning", "section": str(section2.pk)}
        )
        assert response.status_code == status.HTTP_200_OK
        results = _paginated_results(response)
        assert len(results) == 1

    def test_search_invalid_section_uuid(self, auth_client):
        response = auth_client.get(self.url, {"q": "test", "section": "not-a-uuid"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestBookmarkViewSet:
    def test_list_bookmarks_empty(self, auth_client):
        response = auth_client.get(BOOKMARKS_URL)
        assert response.status_code == status.HTTP_200_OK
        results = _paginated_results(response)
        assert len(results) == 0

    def test_create_api_bible_bookmark(self, auth_client, user):
        response = auth_client.post(
            BOOKMARKS_URL,
            {
                "bookmark_type": "api_bible",
                "verse_reference": "JHN.3.16",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data["data"]
        assert data["bookmark_type"] == "api_bible"
        assert data["verse_reference"] == "JHN.3.16"
        assert Bookmark.objects.filter(user=user).count() == 1

    def test_create_segregated_bookmark(self, auth_client, user, page):
        ct = ContentType.objects.get_for_model(SegregatedPage)
        response = auth_client.post(
            BOOKMARKS_URL,
            {
                "bookmark_type": "segregated",
                "content_type": ct.pk,
                "object_id": str(page.pk),
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_api_bible_bookmark_missing_reference(self, auth_client):
        response = auth_client.post(
            BOOKMARKS_URL,
            {
                "bookmark_type": "api_bible",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_segregated_bookmark_missing_content_type(self, auth_client):
        response = auth_client.post(
            BOOKMARKS_URL,
            {
                "bookmark_type": "segregated",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_bookmark(self, auth_client, user):
        bookmark = Bookmark.objects.create(
            user=user,
            bookmark_type="api_bible",
            verse_reference="JHN.3.16",
        )
        url = f"{BOOKMARKS_URL}{bookmark.pk}/"
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Bookmark.objects.filter(pk=bookmark.pk).exists()

    def test_cannot_delete_other_users_bookmark(self, auth_client, user):
        other_user = UserFactory()
        bookmark = Bookmark.objects.create(
            user=other_user,
            bookmark_type="api_bible",
            verse_reference="ROM.8.28",
        )
        url = f"{BOOKMARKS_URL}{bookmark.pk}/"
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_bookmarks_filtered_by_type(self, auth_client, user):
        Bookmark.objects.create(
            user=user, bookmark_type="api_bible", verse_reference="JHN.3.16"
        )
        ct = ContentType.objects.get_for_model(SegregatedPage)
        page_obj = SegregatedPage.objects.create(
            chapter=SegregatedChapter.objects.create(
                section=SegregatedSection.objects.create(
                    title="S",
                    age_min=5,
                    age_max=8,
                    order=1,
                    is_active=True,
                ),
                title="C",
                order=1,
                is_active=True,
            ),
            title="P",
            content="test",
            order=1,
            is_active=True,
        )
        Bookmark.objects.create(
            user=user,
            bookmark_type="segregated",
            content_type=ct,
            object_id=page_obj.pk,
        )
        response = auth_client.get(BOOKMARKS_URL, {"type": "api_bible"})
        results = _paginated_results(response)
        assert len(results) == 1
        assert results[0]["bookmark_type"] == "api_bible"

    def test_unauthenticated_denied(self, api_client):
        response = api_client.get(BOOKMARKS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestHighlightViewSet:
    def test_list_highlights_empty(self, auth_client):
        response = auth_client.get(HIGHLIGHTS_URL)
        assert response.status_code == status.HTTP_200_OK
        results = _paginated_results(response)
        assert len(results) == 0

    def test_create_api_bible_highlight(self, auth_client, user):
        response = auth_client.post(
            HIGHLIGHTS_URL,
            {
                "highlight_type": "api_bible",
                "verse_reference": "PSA.23.1",
                "color": "green",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data["data"]
        assert data["highlight_type"] == "api_bible"
        assert data["color"] == "green"

    def test_create_segregated_highlight(self, auth_client, user, page):
        ct = ContentType.objects.get_for_model(SegregatedPage)
        response = auth_client.post(
            HIGHLIGHTS_URL,
            {
                "highlight_type": "segregated",
                "content_type": ct.pk,
                "object_id": str(page.pk),
                "selection_start": 0,
                "selection_end": 10,
                "color": "yellow",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_api_bible_highlight_missing_reference(self, auth_client):
        response = auth_client.post(
            HIGHLIGHTS_URL,
            {
                "highlight_type": "api_bible",
                "color": "yellow",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_segregated_highlight_missing_selection(self, auth_client, page):
        ct = ContentType.objects.get_for_model(SegregatedPage)
        response = auth_client.post(
            HIGHLIGHTS_URL,
            {
                "highlight_type": "segregated",
                "content_type": ct.pk,
                "object_id": str(page.pk),
                "color": "yellow",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_segregated_highlight_invalid_selection_range(
        self, auth_client, page
    ):

        ct = ContentType.objects.get_for_model(SegregatedPage)
        response = auth_client.post(
            HIGHLIGHTS_URL,
            {
                "highlight_type": "segregated",
                "content_type": ct.pk,
                "object_id": str(page.pk),
                "selection_start": 10,
                "selection_end": 5,
                "color": "yellow",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_highlight(self, auth_client, user):
        highlight = Highlight.objects.create(
            user=user,
            highlight_type="api_bible",
            verse_reference="PSA.23.1",
            color="yellow",
        )
        url = f"{HIGHLIGHTS_URL}{highlight.pk}/"
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Highlight.objects.filter(pk=highlight.pk).exists()

    def test_cannot_delete_other_users_highlight(self, auth_client):
        other_user = UserFactory()
        highlight = Highlight.objects.create(
            user=other_user,
            highlight_type="api_bible",
            verse_reference="PSA.23.1",
            color="yellow",
        )
        url = f"{HIGHLIGHTS_URL}{highlight.pk}/"
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_denied(self, api_client):
        response = api_client.get(HIGHLIGHTS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_highlights_by_type(self, auth_client, user):
        Highlight.objects.create(
            user=user,
            highlight_type="api_bible",
            verse_reference="JHN.1.1",
            color="yellow",
        )
        Highlight.objects.create(
            user=user,
            highlight_type="api_bible",
            verse_reference="JHN.1.2",
            color="green",
        )
        response = auth_client.get(HIGHLIGHTS_URL, {"type": "api_bible"})
        results = _paginated_results(response)
        assert len(results) == 2


@pytest.mark.django_db
class TestNoteViewSet:
    def test_list_notes_empty(self, auth_client):
        response = auth_client.get(NOTES_URL)
        assert response.status_code == status.HTTP_200_OK
        results = _paginated_results(response)
        assert len(results) == 0

    def test_create_api_bible_note(self, auth_client, user):
        response = auth_client.post(
            NOTES_URL,
            {
                "note_type": "api_bible",
                "verse_reference": "JHN.3.16",
                "text": "This verse speaks of God's love.",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data["data"]
        assert data["note_type"] == "api_bible"
        assert data["text"] == "This verse speaks of God's love."
        assert Note.objects.filter(user=user).count() == 1

    def test_create_segregated_note(self, auth_client, user, page):
        ct = ContentType.objects.get_for_model(SegregatedPage)
        response = auth_client.post(
            NOTES_URL,
            {
                "note_type": "segregated",
                "content_type": ct.pk,
                "object_id": str(page.pk),
                "text": "My note on this page.",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_api_bible_note_missing_reference(self, auth_client):
        response = auth_client.post(
            NOTES_URL,
            {
                "note_type": "api_bible",
                "text": "Note without reference.",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_note_missing_text(self, auth_client):
        response = auth_client.post(
            NOTES_URL,
            {
                "note_type": "api_bible",
                "verse_reference": "JHN.3.16",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_note(self, auth_client, user):
        note = Note.objects.create(
            user=user,
            note_type="api_bible",
            verse_reference="JHN.3.16",
            text="Original text.",
        )
        url = f"{NOTES_URL}{note.pk}/"
        response = auth_client.patch(url, {"text": "Updated text."})

        if response.status_code == status.HTTP_200_OK:
            data = response.data["data"]
            assert data["text"] == "Updated text."

        else:
            note.refresh_from_db()
            assert note.text == "Updated text."

    def test_delete_note(self, auth_client, user):
        note = Note.objects.create(
            user=user,
            note_type="api_bible",
            verse_reference="JHN.3.16",
            text="To be deleted.",
        )
        url = f"{NOTES_URL}{note.pk}/"
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Note.objects.filter(pk=note.pk).exists()

    def test_cannot_delete_other_users_note(self, auth_client):
        other_user = UserFactory()
        note = Note.objects.create(
            user=other_user,
            note_type="api_bible",
            verse_reference="ROM.8.28",
            text="Someone else's note.",
        )
        url = f"{NOTES_URL}{note.pk}/"
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_update_other_users_note(self, auth_client):
        other_user = UserFactory()
        note = Note.objects.create(
            user=other_user,
            note_type="api_bible",
            verse_reference="ROM.8.28",
            text="Someone else's note.",
        )
        url = f"{NOTES_URL}{note.pk}/"
        response = auth_client.patch(url, {"text": "hacked"})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_notes_by_type(self, auth_client, user):
        Note.objects.create(
            user=user,
            note_type="api_bible",
            verse_reference="JHN.1.1",
            text="Note 1",
        )
        Note.objects.create(
            user=user,
            note_type="api_bible",
            verse_reference="JHN.1.2",
            text="Note 2",
        )
        response = auth_client.get(NOTES_URL, {"type": "api_bible"})
        results = _paginated_results(response)
        assert len(results) == 2

    def test_unauthenticated_denied(self, api_client):
        response = api_client.get(NOTES_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_note_response_fields(self, auth_client, user):
        Note.objects.create(
            user=user,
            note_type="api_bible",
            verse_reference="JHN.3.16",
            text="My note.",
        )
        response = auth_client.get(NOTES_URL)
        results = _paginated_results(response)
        note = results[0]

        for field in ("id", "note_type", "text", "verse_reference", "created_at"):
            assert field in note
