import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, UniqueConstraint

from apps.common.models import CreatedAtModel, TimeStampedModel


class SegregatedSection(TimeStampedModel):
    """Age-wise section of the Segregated Bible.

    e.g., Ages 5-8, Ages 9-12, Ages 13-17, Ages 18+
    """

    title = models.CharField(max_length=255)
    age_min = models.PositiveSmallIntegerField()
    age_max = models.PositiveSmallIntegerField()
    order = models.PositiveSmallIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "segregated section"
        verbose_name_plural = "segregated sections"
        ordering = ["order"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(age_min__lte=models.F("age_max")),
                name="age_min_lte_age_max",
            ),
        ]

    def __str__(self):
        return f"{self.title} (Ages {self.age_min}-{self.age_max})"


class SegregatedChapter(TimeStampedModel):
    """Chapter within a section. Admin-ordered via drag-and-drop."""

    section = models.ForeignKey(
        SegregatedSection,
        on_delete=models.CASCADE,
        related_name="chapters",
    )
    title = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "segregated chapter"
        verbose_name_plural = "segregated chapters"
        ordering = ["order"]
        indexes = [
            models.Index(fields=["section", "order"]),
        ]

    def __str__(self):
        return f"{self.section.title} > {self.title}"


class SegregatedPage(TimeStampedModel):
    """Page within a chapter. Contains Markdown text with base64 images
    and optional YouTube video embeds.
    """

    chapter = models.ForeignKey(
        SegregatedChapter,
        on_delete=models.CASCADE,
        related_name="pages",
    )
    title = models.CharField(max_length=255)
    content = models.TextField(
        help_text="Markdown text with base64 embedded images.",
    )
    youtube_url = models.URLField(blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "segregated page"
        verbose_name_plural = "segregated pages"
        ordering = ["order"]
        indexes = [
            models.Index(fields=["chapter", "order"]),
        ]

    def __str__(self):
        return f"{self.chapter.title} > {self.title}"


class TranslatedPageCache(models.Model):
    """Cached translation of a SegregatedPage in a specific language.

    Invalidated when the source page content changes.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    page = models.ForeignKey(
        SegregatedPage,
        on_delete=models.CASCADE,
        related_name="translations",
    )
    language_code = models.CharField(max_length=10)
    translated_content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "translated page cache"
        verbose_name_plural = "translated page caches"
        constraints = [
            models.UniqueConstraint(
                fields=["page", "language_code"],
                name="unique_translation_per_page_per_language",
            ),
        ]

    def __str__(self):
        return f"Translation of '{self.page.title}' to {self.language_code}"


class Bookmark(CreatedAtModel):
    """Bookmark for a verse (API Bible) or a SegregatedChapter/SegregatedPage."""

    class BookmarkType(models.TextChoices):
        API_BIBLE = "api_bible", "API Bible"
        SEGREGATED = "segregated", "Segregated"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    # GenericFK for segregated content (chapter or page)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        limit_choices_to=models.Q(
            app_label="bible", model__in=["segregatedchapter", "segregatedpage"]
        ),
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    bookmark_type = models.CharField(max_length=20, choices=BookmarkType.choices)
    verse_reference = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="API Bible verse reference, e.g. 'JHN.3.16'.",
    )

    class Meta:
        verbose_name = "bookmark"
        verbose_name_plural = "bookmarks"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "bookmark_type"]),
            models.Index(fields=["user", "content_type", "object_id"]),
        ]
        constraints = [
            UniqueConstraint(
                fields=["user", "bookmark_type", "verse_reference"],
                condition=Q(bookmark_type="api_bible"),
                name="unique_api_bible_bookmark",
            ),
            UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                condition=Q(bookmark_type="segregated"),
                name="unique_segregated_bookmark",
            ),
        ]

    def __str__(self):
        if self.bookmark_type == self.BookmarkType.API_BIBLE:
            return f"Bookmark by {self.user.full_name}: {self.verse_reference}"
        return f"Bookmark by {self.user.full_name}: {self.content_object}"


class Highlight(CreatedAtModel):
    """Highlight on a verse (API Bible) or text selection within a SegregatedPage."""

    class HighlightType(models.TextChoices):
        API_BIBLE = "api_bible", "API Bible"
        SEGREGATED = "segregated", "Segregated"

    class Color(models.TextChoices):
        YELLOW = "yellow", "Yellow"
        GREEN = "green", "Green"
        BLUE = "blue", "Blue"
        PINK = "pink", "Pink"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="highlights",
    )
    # GenericFK for segregated content
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        limit_choices_to=models.Q(app_label="bible", model="segregatedpage"),
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    highlight_type = models.CharField(max_length=20, choices=HighlightType.choices)
    verse_reference = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="API Bible verse reference for API Bible highlights.",
    )
    # For segregated pages: character offsets within the content text
    selection_start = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Start character offset for text selection (segregated only).",
    )
    selection_end = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="End character offset for text selection (segregated only).",
    )
    color = models.CharField(
        max_length=10, choices=Color.choices, default=Color.YELLOW
    )

    class Meta:
        verbose_name = "highlight"
        verbose_name_plural = "highlights"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "highlight_type"]),
            models.Index(fields=["user", "content_type", "object_id"]),
        ]

    def __str__(self):
        if self.highlight_type == self.HighlightType.API_BIBLE:
            return f"Highlight: {self.verse_reference} ({self.color})"
        return f"Highlight: page {self.object_id} ({self.color})"


class Note(TimeStampedModel):
    """Private note attached to a verse (API Bible) or a SegregatedPage."""

    class NoteType(models.TextChoices):
        API_BIBLE = "api_bible", "API Bible"
        SEGREGATED = "segregated", "Segregated"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    # GenericFK for segregated content
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        limit_choices_to=models.Q(app_label="bible", model="segregatedpage"),
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    note_type = models.CharField(max_length=20, choices=NoteType.choices)
    verse_reference = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="API Bible verse reference for API Bible notes.",
    )
    text = models.TextField()

    class Meta:
        verbose_name = "note"
        verbose_name_plural = "notes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "note_type"]),
            models.Index(fields=["user", "content_type", "object_id"]),
        ]

    def __str__(self):
        if self.note_type == self.NoteType.API_BIBLE:
            return f"Note by {self.user.full_name}: {self.verse_reference}"
        return f"Note by {self.user.full_name}: page {self.object_id}"


class SegregatedPageComment(TimeStampedModel):
    """Comment on segregated bible page. Admin-visibility only."""

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="page_comments",
    )
    page = models.ForeignKey(
        SegregatedPage,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    content = models.TextField(max_length=1000)

    class Meta:
        ordering = ["-created_at"]


class SegregatedPageLike(CreatedAtModel):
    """Like on segregated bible page."""

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="page_likes",
    )
    page = models.ForeignKey(
        SegregatedPage,
        on_delete=models.CASCADE,
        related_name="likes",
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["user", "page"],
                name="unique_page_like",
            ),
        ]
