"""Tests for bible models.

Covers:
- SegregatedSection, SegregatedChapter, SegregatedPage
- TranslatedPageCache
- Bookmark, Highlight, Note
- SegregatedPageComment, SegregatedPageLike
"""

from __future__ import annotations
import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from apps.bible.models import (
    Bookmark,
    Highlight,
    Note,
    SegregatedChapter,
    SegregatedPage,
    SegregatedPageComment,
    SegregatedPageLike,
    SegregatedSection,
    TranslatedPageCache,
)

from conftest import UserFactory


@pytest.fixture
def section(db):
    return SegregatedSection.objects.create(
        title="Kids Bible",
        age_min=5,
        age_max=8,
        order=0,
    )


@pytest.fixture
def chapter(section):
    return SegregatedChapter.objects.create(
        section=section,
        title="Creation",
        order=0,
    )


@pytest.fixture
def page(chapter):
    return SegregatedPage.objects.create(
        chapter=chapter,
        title="Day 1",
        content="In the beginning...",
        order=0,
    )


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.mark.django_db
class TestSegregatedSection:
    """Tests for the SegregatedSection model."""

    def test_create(self, section):
        """A section can be created with valid data."""
        assert section.pk is not None
        assert section.title == "Kids Bible"
        assert section.age_min == 5
        assert section.age_max == 8

    def test_str(self, section):
        """__str__ includes title and age range."""
        result = str(section)
        assert "Kids Bible" in result
        assert "5" in result
        assert "8" in result

    def test_ordering_by_order(self, db):
        """Sections are ordered by the `order` field."""
        s2 = SegregatedSection.objects.create(
            title="Teens",
            age_min=13,
            age_max=17,
            order=2,
        )
        s1 = SegregatedSection.objects.create(
            title="Kids",
            age_min=5,
            age_max=8,
            order=1,
        )
        sections = list(SegregatedSection.objects.all())
        assert sections[0].pk == s1.pk
        assert sections[1].pk == s2.pk

    def test_check_constraint_age_min_lte_age_max(self, db):
        """age_min must be <= age_max (CheckConstraint)."""

        with pytest.raises(IntegrityError):
            SegregatedSection.objects.create(
                title="Invalid",
                age_min=18,
                age_max=5,
                order=0,
            )

    def test_is_active_default_true(self, section):
        """is_active defaults to True."""
        assert section.is_active is True

    def test_timestamps(self, section):
        """Section has created_at and updated_at timestamps."""
        assert section.created_at is not None
        assert section.updated_at is not None


@pytest.mark.django_db
class TestSegregatedChapter:
    """Tests for the SegregatedChapter model."""

    def test_create(self, chapter):
        """A chapter can be created with valid data."""
        assert chapter.pk is not None
        assert chapter.title == "Creation"
        assert chapter.section is not None

    def test_str(self, chapter):
        """__str__ includes section title and chapter title."""
        result = str(chapter)
        assert "Kids Bible" in result
        assert "Creation" in result

    def test_cascade_delete_section(self, chapter):
        """Deleting the section cascades to its chapters."""
        section_pk = chapter.section.pk
        chapter.section.delete()
        assert not SegregatedChapter.objects.filter(section_id=section_pk).exists()

    def test_ordering_by_order(self, section):
        """Chapters are ordered by the `order` field."""
        ch2 = SegregatedChapter.objects.create(section=section, title="B", order=2)
        ch1 = SegregatedChapter.objects.create(section=section, title="A", order=1)
        chapters = list(SegregatedChapter.objects.filter(section=section))
        assert chapters[0].pk == ch1.pk
        assert chapters[1].pk == ch2.pk


@pytest.mark.django_db
class TestSegregatedPage:
    """Tests for the SegregatedPage model."""

    def test_create(self, page):
        """A page can be created with valid data."""
        assert page.pk is not None
        assert page.title == "Day 1"
        assert page.content == "In the beginning..."

    def test_str(self, page):
        """__str__ includes chapter title and page title."""
        result = str(page)
        assert "Creation" in result
        assert "Day 1" in result

    def test_youtube_url_blank_by_default(self, page):
        """youtube_url defaults to empty string."""
        assert page.youtube_url == ""

    def test_cascade_delete_chapter(self, page):
        """Deleting the chapter cascades to its pages."""
        chapter_pk = page.chapter.pk
        page.chapter.delete()
        assert not SegregatedPage.objects.filter(chapter_id=chapter_pk).exists()

    def test_ordering_by_order(self, chapter):
        """Pages are ordered by the `order` field."""
        p2 = SegregatedPage.objects.create(
            chapter=chapter,
            title="P2",
            content="c2",
            order=2,
        )
        p1 = SegregatedPage.objects.create(
            chapter=chapter,
            title="P1",
            content="c1",
            order=1,
        )
        pages = list(SegregatedPage.objects.filter(chapter=chapter))
        assert pages[0].pk == p1.pk
        assert pages[1].pk == p2.pk


@pytest.mark.django_db
class TestTranslatedPageCache:
    """Tests for the TranslatedPageCache model."""

    def test_create(self, page):
        """A translation cache entry can be created."""
        cache = TranslatedPageCache.objects.create(
            page=page,
            language_code="es",
            translated_content="En el principio...",
        )
        assert cache.pk is not None
        assert cache.language_code == "es"

    def test_str(self, page):
        """__str__ includes page title and language code."""
        cache = TranslatedPageCache.objects.create(
            page=page,
            language_code="fr",
            translated_content="Au commencement...",
        )
        result = str(cache)
        assert page.title in result
        assert "fr" in result

    def test_unique_constraint_page_language(self, page):
        """Only one translation per page per language is allowed."""
        TranslatedPageCache.objects.create(
            page=page,
            language_code="es",
            translated_content="Texto 1",
        )

        with pytest.raises(IntegrityError):
            TranslatedPageCache.objects.create(
                page=page,
                language_code="es",
                translated_content="Texto 2",
            )

    def test_different_languages_allowed(self, page):
        """Multiple translations of the same page in different languages are allowed."""
        TranslatedPageCache.objects.create(
            page=page,
            language_code="es",
            translated_content="Espanol",
        )
        TranslatedPageCache.objects.create(
            page=page,
            language_code="fr",
            translated_content="Francais",
        )
        assert TranslatedPageCache.objects.filter(page=page).count() == 2

    def test_cascade_delete_page(self, page):
        """Deleting the page cascades to its translation cache entries."""
        TranslatedPageCache.objects.create(
            page=page,
            language_code="es",
            translated_content="text",
        )
        page.delete()
        assert TranslatedPageCache.objects.count() == 0


@pytest.mark.django_db
class TestBookmark:
    """Tests for the Bookmark model."""

    def test_create_api_bible_bookmark(self, user):
        """An API Bible bookmark can be created."""
        bm = Bookmark.objects.create(
            user=user,
            bookmark_type=Bookmark.BookmarkType.API_BIBLE,
            verse_reference="JHN.3.16",
        )
        assert bm.pk is not None
        assert bm.bookmark_type == "api_bible"
        assert bm.verse_reference == "JHN.3.16"

    def test_create_segregated_bookmark(self, user, page):
        """A segregated bookmark can be created with a content_type and object_id."""
        ct = ContentType.objects.get_for_model(page)
        bm = Bookmark.objects.create(
            user=user,
            bookmark_type=Bookmark.BookmarkType.SEGREGATED,
            content_type=ct,
            object_id=page.pk,
        )
        assert bm.pk is not None
        assert bm.content_type == ct
        assert bm.object_id == page.pk

    def test_str_api_bible(self, user):
        """__str__ for API Bible bookmark includes verse reference."""
        bm = Bookmark.objects.create(
            user=user,
            bookmark_type="api_bible",
            verse_reference="PSA.23.1",
        )
        assert "PSA.23.1" in str(bm)

    def test_str_segregated(self, user, page):
        """__str__ for segregated bookmark includes content object."""
        ct = ContentType.objects.get_for_model(page)
        bm = Bookmark.objects.create(
            user=user,
            bookmark_type="segregated",
            content_type=ct,
            object_id=page.pk,
        )
        result = str(bm)
        assert user.full_name in result

    def test_unique_api_bible_bookmark_constraint(self, user):
        """A user cannot have duplicate API Bible bookmarks for the same verse."""
        Bookmark.objects.create(
            user=user,
            bookmark_type="api_bible",
            verse_reference="JHN.3.16",
        )

        with pytest.raises(IntegrityError):
            Bookmark.objects.create(
                user=user,
                bookmark_type="api_bible",
                verse_reference="JHN.3.16",
            )

    def test_unique_segregated_bookmark_constraint(self, user, page):
        """A user cannot have duplicate segregated bookmarks for the same object."""
        ct = ContentType.objects.get_for_model(page)
        Bookmark.objects.create(
            user=user,
            bookmark_type="segregated",
            content_type=ct,
            object_id=page.pk,
        )

        with pytest.raises(IntegrityError):
            Bookmark.objects.create(
                user=user,
                bookmark_type="segregated",
                content_type=ct,
                object_id=page.pk,
            )

    def test_different_users_same_verse(self, page):
        """Different users can bookmark the same verse."""
        u1 = UserFactory()
        u2 = UserFactory()
        Bookmark.objects.create(
            user=u1, bookmark_type="api_bible", verse_reference="JHN.3.16"
        )
        Bookmark.objects.create(
            user=u2, bookmark_type="api_bible", verse_reference="JHN.3.16"
        )
        assert Bookmark.objects.filter(verse_reference="JHN.3.16").count() == 2

    def test_ordering_newest_first(self, user):
        """Bookmarks are ordered by -created_at."""
        bm1 = Bookmark.objects.create(
            user=user, bookmark_type="api_bible", verse_reference="A"
        )
        bm2 = Bookmark.objects.create(
            user=user, bookmark_type="api_bible", verse_reference="B"
        )
        bookmarks = list(Bookmark.objects.filter(user=user))
        assert bookmarks[0].pk == bm2.pk
        assert bookmarks[1].pk == bm1.pk


@pytest.mark.django_db
class TestHighlight:
    """Tests for the Highlight model."""

    def test_create_api_bible_highlight(self, user):
        """An API Bible highlight can be created."""
        h = Highlight.objects.create(
            user=user,
            highlight_type=Highlight.HighlightType.API_BIBLE,
            verse_reference="ROM.8.28",
            color=Highlight.Color.GREEN,
        )
        assert h.pk is not None
        assert h.color == "green"

    def test_create_segregated_highlight(self, user, page):
        """A segregated highlight can be created with character offsets."""
        ct = ContentType.objects.get_for_model(page)
        h = Highlight.objects.create(
            user=user,
            highlight_type=Highlight.HighlightType.SEGREGATED,
            content_type=ct,
            object_id=page.pk,
            selection_start=0,
            selection_end=10,
            color=Highlight.Color.BLUE,
        )
        assert h.selection_start == 0
        assert h.selection_end == 10

    def test_default_color_is_yellow(self, user):
        """Default color is yellow."""
        h = Highlight.objects.create(
            user=user,
            highlight_type="api_bible",
            verse_reference="GEN.1.1",
        )
        assert h.color == Highlight.Color.YELLOW

    def test_color_choices(self):
        """All expected color choices exist."""
        choices = {c[0] for c in Highlight.Color.choices}
        assert choices == {"yellow", "green", "blue", "pink"}

    def test_str_api_bible(self, user):
        """__str__ for API Bible highlight includes verse_reference and color."""
        h = Highlight.objects.create(
            user=user,
            highlight_type="api_bible",
            verse_reference="JHN.1.1",
            color="green",
        )
        result = str(h)
        assert "JHN.1.1" in result
        assert "green" in result

    def test_str_segregated(self, user, page):
        """__str__ for segregated highlight includes object_id and color."""
        ct = ContentType.objects.get_for_model(page)
        h = Highlight.objects.create(
            user=user,
            highlight_type="segregated",
            content_type=ct,
            object_id=page.pk,
            selection_start=0,
            selection_end=5,
            color="pink",
        )
        result = str(h)
        assert "pink" in result


@pytest.mark.django_db
class TestNote:
    """Tests for the Note model."""

    def test_create_api_bible_note(self, user):
        """An API Bible note can be created."""
        note = Note.objects.create(
            user=user,
            note_type=Note.NoteType.API_BIBLE,
            verse_reference="JHN.3.16",
            text="For God so loved the world...",
        )
        assert note.pk is not None
        assert note.text == "For God so loved the world..."

    def test_create_segregated_note(self, user, page):
        """A segregated note can be created."""
        ct = ContentType.objects.get_for_model(page)
        note = Note.objects.create(
            user=user,
            note_type=Note.NoteType.SEGREGATED,
            content_type=ct,
            object_id=page.pk,
            text="My thoughts on this page.",
        )
        assert note.pk is not None
        assert note.content_type == ct

    def test_str_api_bible(self, user):
        """__str__ for API Bible note includes verse reference."""
        note = Note.objects.create(
            user=user,
            note_type="api_bible",
            verse_reference="PSA.23.1",
            text="The Lord is my shepherd.",
        )
        assert "PSA.23.1" in str(note)
        assert user.full_name in str(note)

    def test_str_segregated(self, user, page):
        """__str__ for segregated note includes page object_id."""
        ct = ContentType.objects.get_for_model(page)
        note = Note.objects.create(
            user=user,
            note_type="segregated",
            content_type=ct,
            object_id=page.pk,
            text="A note.",
        )
        result = str(note)
        assert user.full_name in result

    def test_timestamps(self, user):
        """Note has created_at and updated_at (TimeStampedModel)."""
        note = Note.objects.create(
            user=user,
            note_type="api_bible",
            verse_reference="GEN.1.1",
            text="In the beginning.",
        )
        assert note.created_at is not None
        assert note.updated_at is not None

    def test_ordering_newest_first(self, user):
        """Notes are ordered by -created_at."""
        Note.objects.create(
            user=user,
            note_type="api_bible",
            verse_reference="A",
            text="1",
        )
        n2 = Note.objects.create(
            user=user,
            note_type="api_bible",
            verse_reference="B",
            text="2",
        )
        notes = list(Note.objects.filter(user=user))
        assert notes[0].pk == n2.pk


@pytest.mark.django_db
class TestSegregatedPageComment:
    """Tests for the SegregatedPageComment model."""

    def test_create(self, user, page):
        """A page comment can be created."""
        comment = SegregatedPageComment.objects.create(
            user=user,
            page=page,
            content="Great page!",
        )
        assert comment.pk is not None
        assert comment.content == "Great page!"

    def test_cascade_delete_page(self, user, page):
        """Deleting the page cascades to its comments."""
        SegregatedPageComment.objects.create(user=user, page=page, content="Nice!")
        page.delete()
        assert SegregatedPageComment.objects.count() == 0


@pytest.mark.django_db
class TestSegregatedPageLike:
    """Tests for the SegregatedPageLike model."""

    def test_create(self, user, page):
        """A page like can be created."""
        like = SegregatedPageLike.objects.create(user=user, page=page)
        assert like.pk is not None

    def test_unique_constraint_user_page(self, user, page):
        """A user can like a page only once."""
        SegregatedPageLike.objects.create(user=user, page=page)

        with pytest.raises(IntegrityError):
            SegregatedPageLike.objects.create(user=user, page=page)

    def test_different_users_can_like_same_page(self, page):
        """Different users can like the same page."""
        u1 = UserFactory()
        u2 = UserFactory()
        SegregatedPageLike.objects.create(user=u1, page=page)
        SegregatedPageLike.objects.create(user=u2, page=page)
        assert SegregatedPageLike.objects.filter(page=page).count() == 2
