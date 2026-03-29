from __future__ import annotations


from rest_framework import serializers

from apps.common.serializers import (
    BaseModelSerializer,
    BaseTimestampedSerializer,
    GenericRelatedField,
)

from .models import (
    Bookmark,
    Highlight,
    Note,
    SegregatedChapter,
    SegregatedPage,
    SegregatedSection,
    TranslatedPageCache,
)


# ---------------------------------------------------------------------------
# Segregated Bible content
# ---------------------------------------------------------------------------


class SegregatedSectionListSerializer(BaseTimestampedSerializer):
    """Compact representation for section lists."""

    chapter_count = serializers.IntegerField(read_only=True, default=0)
    is_prioritized = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = SegregatedSection
        fields = [
            "id",
            "title",
            "age_min",
            "age_max",
            "order",
            "is_active",
            "chapter_count",
            "is_prioritized",
            "created_at",
            "updated_at",
        ]


class SegregatedChapterListSerializer(BaseTimestampedSerializer):
    """Compact representation for chapter lists."""

    page_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = SegregatedChapter
        fields = [
            "id",
            "section",
            "title",
            "order",
            "is_active",
            "page_count",
            "created_at",
            "updated_at",
        ]


class SegregatedPageListSerializer(BaseTimestampedSerializer):
    """Compact page representation (no full content body)."""

    class Meta:
        model = SegregatedPage
        fields = [
            "id",
            "chapter",
            "title",
            "youtube_url",
            "order",
            "is_active",
            "created_at",
            "updated_at",
        ]


class SegregatedPageDetailSerializer(BaseTimestampedSerializer):
    """Full page detail including content and navigation context."""

    section_title = serializers.CharField(
        source="chapter.section.title", read_only=True,
    )
    chapter_title = serializers.CharField(
        source="chapter.title", read_only=True,
    )

    class Meta:
        model = SegregatedPage
        fields = [
            "id",
            "chapter",
            "title",
            "content",
            "youtube_url",
            "order",
            "is_active",
            "section_title",
            "chapter_title",
            "created_at",
            "updated_at",
        ]


class PageCommentCreateSerializer(serializers.Serializer):
    """Validates page comment input from users."""

    content = serializers.CharField(max_length=1000)


class TranslatedPageSerializer(serializers.ModelSerializer):
    """Serializer for cached translations."""

    class Meta:
        model = TranslatedPageCache
        fields = [
            "id",
            "page",
            "language_code",
            "translated_content",
            "created_at",
        ]
        read_only_fields = ["id", "translated_content", "created_at"]


# ---------------------------------------------------------------------------
# Bookmark
# ---------------------------------------------------------------------------


class BookmarkCreateSerializer(serializers.Serializer):
    """Write serializer for creating bookmarks."""

    bookmark_type = serializers.ChoiceField(choices=Bookmark.BookmarkType.choices)
    verse_reference = serializers.CharField(
        max_length=50, required=False, default="",
    )
    content_type = serializers.IntegerField(required=False, allow_null=True)
    object_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        bookmark_type = attrs.get("bookmark_type")
        if bookmark_type == Bookmark.BookmarkType.API_BIBLE:
            if not attrs.get("verse_reference"):
                raise serializers.ValidationError(
                    {"verse_reference": "Required for API Bible bookmarks."}
                )
        elif bookmark_type == Bookmark.BookmarkType.SEGREGATED:
            if not attrs.get("content_type") or not attrs.get("object_id"):
                raise serializers.ValidationError(
                    "content_type and object_id are required for segregated bookmarks."
                )
        return attrs


class BookmarkSerializer(BaseModelSerializer):
    """Read serializer for bookmarks."""

    content_object = GenericRelatedField(read_only=True)

    class Meta:
        model = Bookmark
        fields = [
            "id",
            "bookmark_type",
            "verse_reference",
            "content_type",
            "object_id",
            "content_object",
            "created_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Highlight
# ---------------------------------------------------------------------------


class HighlightCreateSerializer(serializers.Serializer):
    """Write serializer for creating highlights."""

    highlight_type = serializers.ChoiceField(choices=Highlight.HighlightType.choices)
    color = serializers.ChoiceField(
        choices=Highlight.Color.choices, default=Highlight.Color.YELLOW,
    )
    verse_reference = serializers.CharField(
        max_length=50, required=False, default="",
    )
    content_type = serializers.IntegerField(required=False, allow_null=True)
    object_id = serializers.UUIDField(required=False, allow_null=True)
    selection_start = serializers.IntegerField(
        required=False, allow_null=True, min_value=0,
    )
    selection_end = serializers.IntegerField(
        required=False, allow_null=True, min_value=0,
    )

    def validate(self, attrs: dict) -> dict:
        highlight_type = attrs.get("highlight_type")
        if highlight_type == Highlight.HighlightType.API_BIBLE:
            if not attrs.get("verse_reference"):
                raise serializers.ValidationError(
                    {"verse_reference": "Required for API Bible highlights."}
                )
        elif highlight_type == Highlight.HighlightType.SEGREGATED:
            if not attrs.get("content_type") or not attrs.get("object_id"):
                raise serializers.ValidationError(
                    "content_type and object_id are required for segregated highlights."
                )
            if attrs.get("selection_start") is None or attrs.get("selection_end") is None:
                raise serializers.ValidationError(
                    "selection_start and selection_end are required for segregated highlights."
                )
            if attrs["selection_start"] >= attrs["selection_end"]:
                raise serializers.ValidationError(
                    "selection_start must be less than selection_end."
                )
        return attrs


class HighlightSerializer(BaseModelSerializer):
    """Read serializer for highlights."""

    content_object = GenericRelatedField(read_only=True)

    class Meta:
        model = Highlight
        fields = [
            "id",
            "highlight_type",
            "color",
            "verse_reference",
            "content_type",
            "object_id",
            "content_object",
            "selection_start",
            "selection_end",
            "created_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Note
# ---------------------------------------------------------------------------


class NoteCreateSerializer(serializers.Serializer):
    """Write serializer for creating notes."""

    note_type = serializers.ChoiceField(choices=Note.NoteType.choices)
    text = serializers.CharField()
    verse_reference = serializers.CharField(
        max_length=50, required=False, default="",
    )
    content_type = serializers.IntegerField(required=False, allow_null=True)
    object_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        note_type = attrs.get("note_type")
        if note_type == Note.NoteType.API_BIBLE:
            if not attrs.get("verse_reference"):
                raise serializers.ValidationError(
                    {"verse_reference": "Required for API Bible notes."}
                )
        elif note_type == Note.NoteType.SEGREGATED:
            if not attrs.get("content_type") or not attrs.get("object_id"):
                raise serializers.ValidationError(
                    "content_type and object_id are required for segregated notes."
                )
        return attrs


class NoteUpdateSerializer(serializers.Serializer):
    """Write serializer for updating note text."""

    text = serializers.CharField()


class NoteSerializer(BaseTimestampedSerializer):
    """Read serializer for notes."""

    content_object = GenericRelatedField(read_only=True)

    class Meta:
        model = Note
        fields = [
            "id",
            "note_type",
            "text",
            "verse_reference",
            "content_type",
            "object_id",
            "content_object",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
