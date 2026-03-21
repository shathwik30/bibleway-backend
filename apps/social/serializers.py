from __future__ import annotations

from typing import Any
from uuid import UUID

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.common.serializers import (
    BaseModelSerializer,
    BaseTimestampedSerializer,
    InlineMediaSerializer,
)
from apps.common.validators import validate_image_file, validate_video_file

from .models import (
    Comment,
    Post,
    PostMedia,
    Prayer,
    PrayerMedia,
    Reaction,
    Reply,
    Report,
)


# ---------------------------------------------------------------------------
# Lightweight author representation (avoids circular import from accounts)
# ---------------------------------------------------------------------------


class AuthorSerializer(serializers.Serializer):
    """Minimal user representation embedded in social objects."""

    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    profile_photo = serializers.ImageField(read_only=True)
    age = serializers.IntegerField(read_only=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_user_reaction_from_annotation(obj: Any, context: dict) -> str | None:
    """Return the requesting user's emoji_type from an annotated attribute.

    Falls back to a DB query when the annotation is not present (e.g. after
    create, where the object is freshly fetched without the annotation).
    """
    # Fast path: read from Subquery annotation set by the queryset.
    annotated = getattr(obj, "user_reaction_type", _SENTINEL)
    if annotated is not _SENTINEL:
        return annotated  # str or None

    # Fallback: context-based DB lookup (single query, only for detail views
    # where the queryset annotation is absent).
    request = context.get("request")
    if request is None or not hasattr(request, "user") or request.user.is_anonymous:
        return None
    ct = ContentType.objects.get_for_model(type(obj))
    reaction = Reaction.objects.filter(
        user=request.user, content_type=ct, object_id=obj.pk
    ).values_list("emoji_type", flat=True).first()
    return reaction


# Unique sentinel so we can distinguish "annotation missing" from "annotation
# is None" (which is a valid value meaning "no reaction").
_SENTINEL = object()


# ---------------------------------------------------------------------------
# Post serializers
# ---------------------------------------------------------------------------


class PostMediaSerializer(InlineMediaSerializer):
    """Read-only inline representation of a post's media attachment."""

    class Meta:
        fields = ["id", "file", "media_type", "order"]


class PostCreateSerializer(serializers.Serializer):
    """Validates input for creating a new post.

    Accepts either ``media_keys`` (UploadThing file keys from client-side
    uploads) or ``media_files`` (legacy server-side upload). ``media_keys``
    is the preferred path.
    """

    text_content = serializers.CharField(
        max_length=2000, required=False, default="", allow_blank=True
    )
    # Client-side upload: UploadThing file keys
    media_keys = serializers.ListField(
        child=serializers.CharField(max_length=500), required=False, max_length=10
    )
    media_types = serializers.ListField(
        child=serializers.ChoiceField(choices=PostMedia.MediaType.choices),
        required=False,
        max_length=10,
    )
    # Legacy server-side upload (kept for backward compatibility)
    media_files = serializers.ListField(
        child=serializers.FileField(), required=False, max_length=10
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        text_content: str = attrs.get("text_content", "")
        media_keys: list[str] = attrs.get("media_keys", [])
        media_files: list[Any] = attrs.get("media_files", [])
        media_types: list[str] = attrs.get("media_types", [])

        has_media = bool(media_keys) or bool(media_files)

        if not text_content and not has_media:
            raise serializers.ValidationError(
                "A post must have text content or at least one media file."
            )

        # Determine which media source to validate against
        media_count = len(media_keys) if media_keys else len(media_files)

        if media_count > 0 and len(media_types) != media_count:
            raise serializers.ValidationError(
                "media_types must match the number of media items."
            )

        # Enforce media constraints: max 10 images or 1 video, not both.
        video_count = sum(1 for mt in media_types if mt == PostMedia.MediaType.VIDEO)
        image_count = sum(1 for mt in media_types if mt == PostMedia.MediaType.IMAGE)

        if video_count > 1:
            raise serializers.ValidationError("A post can have at most 1 video.")
        if video_count > 0 and image_count > 0:
            raise serializers.ValidationError(
                "A post with a video cannot also have images."
            )
        if image_count > 10:
            raise serializers.ValidationError("A post can have at most 10 images.")

        # Per-file validation only for legacy server-side uploads
        if media_files and not media_keys:
            for file, media_type in zip(media_files, media_types):
                if media_type == PostMedia.MediaType.IMAGE:
                    validate_image_file(file)
                elif media_type == PostMedia.MediaType.VIDEO:
                    validate_video_file(file)

        return attrs


class PostDetailSerializer(BaseTimestampedSerializer):
    """Full post representation including author, media, and engagement counts."""

    author = AuthorSerializer(read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)
    reaction_count = serializers.IntegerField(read_only=True, default=0)
    comment_count = serializers.IntegerField(read_only=True, default=0)
    user_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "text_content",
            "is_boosted",
            "media",
            "reaction_count",
            "comment_count",
            "user_reaction",
            "created_at",
            "updated_at",
        ]

    def get_user_reaction(self, obj: Post) -> str | None:
        """Return the requesting user's emoji_type on this post, or null."""
        return _get_user_reaction_from_annotation(obj, self.context)


class PostListSerializer(BaseTimestampedSerializer):
    """Lighter post serializer for feed listings."""

    author = AuthorSerializer(read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)
    reaction_count = serializers.IntegerField(read_only=True, default=0)
    comment_count = serializers.IntegerField(read_only=True, default=0)
    user_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "text_content",
            "is_boosted",
            "media",
            "reaction_count",
            "comment_count",
            "user_reaction",
            "created_at",
        ]

    def get_user_reaction(self, obj: Post) -> str | None:
        return _get_user_reaction_from_annotation(obj, self.context)


# ---------------------------------------------------------------------------
# Prayer serializers
# ---------------------------------------------------------------------------


class PrayerMediaSerializer(InlineMediaSerializer):
    """Read-only inline representation of a prayer's media attachment."""

    class Meta:
        fields = ["id", "file", "media_type", "order"]


class PrayerCreateSerializer(serializers.Serializer):
    """Validates input for creating a new prayer request."""

    title = serializers.CharField(max_length=255)
    description = serializers.CharField(
        max_length=2000, required=False, default="", allow_blank=True
    )
    media_keys = serializers.ListField(
        child=serializers.CharField(max_length=500), required=False, max_length=10
    )
    media_types = serializers.ListField(
        child=serializers.ChoiceField(choices=PrayerMedia.MediaType.choices),
        required=False,
        max_length=10,
    )
    media_files = serializers.ListField(
        child=serializers.FileField(), required=False, max_length=10
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        media_keys: list[str] = attrs.get("media_keys", [])
        media_files: list[Any] = attrs.get("media_files", [])
        media_types: list[str] = attrs.get("media_types", [])

        media_count = len(media_keys) if media_keys else len(media_files)

        if media_count > 0 and len(media_types) != media_count:
            raise serializers.ValidationError(
                "media_types must match the number of media items."
            )

        video_count = sum(1 for mt in media_types if mt == PrayerMedia.MediaType.VIDEO)
        image_count = sum(1 for mt in media_types if mt == PrayerMedia.MediaType.IMAGE)

        if video_count > 1:
            raise serializers.ValidationError("A prayer can have at most 1 video.")
        if video_count > 0 and image_count > 0:
            raise serializers.ValidationError(
                "A prayer with a video cannot also have images."
            )
        if image_count > 10:
            raise serializers.ValidationError("A prayer can have at most 10 images.")

        if media_files and not media_keys:
            for file, media_type in zip(media_files, media_types):
                if media_type == PrayerMedia.MediaType.IMAGE:
                    validate_image_file(file)
                elif media_type == PrayerMedia.MediaType.VIDEO:
                    validate_video_file(file)

        return attrs


class PrayerDetailSerializer(BaseTimestampedSerializer):
    """Full prayer representation with author, media, and engagement counts."""

    author = AuthorSerializer(read_only=True)
    media = PrayerMediaSerializer(many=True, read_only=True)
    reaction_count = serializers.IntegerField(read_only=True, default=0)
    comment_count = serializers.IntegerField(read_only=True, default=0)
    user_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Prayer
        fields = [
            "id",
            "author",
            "title",
            "description",
            "media",
            "reaction_count",
            "comment_count",
            "user_reaction",
            "created_at",
            "updated_at",
        ]

    def get_user_reaction(self, obj: Prayer) -> str | None:
        return _get_user_reaction_from_annotation(obj, self.context)


class PrayerListSerializer(BaseTimestampedSerializer):
    """Lighter prayer serializer for feed listings."""

    author = AuthorSerializer(read_only=True)
    media = PrayerMediaSerializer(many=True, read_only=True)
    reaction_count = serializers.IntegerField(read_only=True, default=0)
    comment_count = serializers.IntegerField(read_only=True, default=0)
    user_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Prayer
        fields = [
            "id",
            "author",
            "title",
            "description",
            "media",
            "reaction_count",
            "comment_count",
            "user_reaction",
            "created_at",
        ]

    def get_user_reaction(self, obj: Prayer) -> str | None:
        return _get_user_reaction_from_annotation(obj, self.context)


# ---------------------------------------------------------------------------
# Reaction serializers
# ---------------------------------------------------------------------------


class ReactionSerializer(BaseModelSerializer):
    """Read representation of a reaction."""

    user = AuthorSerializer(read_only=True)

    class Meta:
        model = Reaction
        fields = ["id", "user", "emoji_type", "created_at"]


class ReactionCreateSerializer(serializers.Serializer):
    """Validates input for toggling a reaction."""

    emoji_type = serializers.ChoiceField(choices=Reaction.EmojiType.choices)
    content_type_model = serializers.ChoiceField(
        choices=[("post", "Post"), ("prayer", "Prayer")]
    )
    object_id = serializers.UUIDField()


# ---------------------------------------------------------------------------
# Comment serializers
# ---------------------------------------------------------------------------


class CommentSerializer(BaseTimestampedSerializer):
    """Read representation of a comment with user info and reply count."""

    user = AuthorSerializer(read_only=True)
    reply_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Comment
        fields = [
            "id",
            "user",
            "text",
            "reply_count",
            "created_at",
            "updated_at",
        ]


class CommentCreateSerializer(serializers.Serializer):
    """Validates input for creating a comment on a post or prayer."""

    text = serializers.CharField(max_length=1000)
    content_type_model = serializers.ChoiceField(
        choices=[("post", "Post"), ("prayer", "Prayer")]
    )
    object_id = serializers.UUIDField()


# ---------------------------------------------------------------------------
# Reply serializers
# ---------------------------------------------------------------------------


class ReplySerializer(BaseTimestampedSerializer):
    """Read representation of a reply."""

    user = AuthorSerializer(read_only=True)

    class Meta:
        model = Reply
        fields = ["id", "user", "text", "created_at", "updated_at"]


class ReplyCreateSerializer(serializers.Serializer):
    """Validates input for creating a reply to a comment."""

    text = serializers.CharField(max_length=1000)


# ---------------------------------------------------------------------------
# Report serializers
# ---------------------------------------------------------------------------


class ReportCreateSerializer(serializers.Serializer):
    """Validates input for filing a content report."""

    reason = serializers.ChoiceField(choices=Report.Reason.choices)
    description = serializers.CharField(
        max_length=2000, required=False, default="", allow_blank=True
    )
    content_type_model = serializers.ChoiceField(
        choices=[
            ("post", "Post"),
            ("prayer", "Prayer"),
            ("comment", "Comment"),
            ("user", "User"),
        ]
    )
    object_id = serializers.UUIDField()
