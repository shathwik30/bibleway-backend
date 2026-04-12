from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.constants import MediaType
from apps.common.validators import validate_image_file, validate_video_file


class MediaValidationMixin:
    """Shared media validation for Post and Prayer create serializers.

    Validates media_keys/media_types/media_files count matching,
    video count limits, and file-type constraints.

    Subclasses must define ``content_label`` (e.g. ``"post"`` or ``"prayer"``)
    for human-readable error messages.
    """

    content_label: str = "content"

    def validate_media_fields(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate media-related fields and return attrs unchanged."""
        media_keys: list[str] = attrs.get("media_keys", [])
        media_files: list[Any] = attrs.get("media_files", [])
        media_types: list[str] = attrs.get("media_types", [])
        media_count = len(media_keys) if media_keys else len(media_files)

        if media_count > 0 and len(media_types) != media_count:
            raise serializers.ValidationError(
                "media_types must match the number of media items."
            )

        video_count = sum(1 for mt in media_types if mt == MediaType.VIDEO)
        image_count = sum(1 for mt in media_types if mt == MediaType.IMAGE)

        if video_count > 1:
            raise serializers.ValidationError(
                f"A {self.content_label} can have at most 1 video."
            )

        if video_count > 0 and image_count > 0:
            raise serializers.ValidationError(
                f"A {self.content_label} with a video cannot also have images."
            )

        if image_count > 10:
            raise serializers.ValidationError(
                f"A {self.content_label} can have at most 10 images."
            )

        if media_files and not media_keys:
            for file, media_type in zip(media_files, media_types):
                if media_type == MediaType.IMAGE:
                    validate_image_file(file)

                elif media_type == MediaType.VIDEO:
                    validate_video_file(file)

        return attrs


class UserReactionMixin:
    """Mixin that provides a ``get_user_reaction`` method for serializers.

    Relies on the module-level ``_get_user_reaction_from_annotation``
    helper already defined in the serializers module.

    Subclasses must still declare the field explicitly::

        user_reaction = serializers.SerializerMethodField()

    This is required because DRF's ``SerializerMetaclass`` only collects
    declared fields from ``Serializer`` subclasses, not plain mixins.
    """

    def get_user_reaction(self, obj: Any) -> str | None:
        from .serializers import _get_user_reaction_from_annotation

        return _get_user_reaction_from_annotation(obj, self.context)  # type: ignore[attr-defined]
