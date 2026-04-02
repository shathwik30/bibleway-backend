from __future__ import annotations
from typing import Any
from rest_framework import serializers


class BaseModelSerializer(serializers.ModelSerializer):
    """Base serializer with common patterns for all models.

    Makes `id` and timestamps read-only by default.
    """

    id = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class BaseTimestampedSerializer(BaseModelSerializer):
    """Base serializer for TimeStampedModel (has updated_at)."""

    updated_at = serializers.DateTimeField(read_only=True)


class GenericRelatedField(serializers.RelatedField):
    """Serializer field for GenericForeignKey that returns content type and object id."""

    def to_representation(self, value: Any) -> dict[str, str]:
        return {
            "type": value.__class__.__name__.lower(),
            "id": str(value.pk),
        }


class InlineMediaSerializer(serializers.Serializer):
    """Base serializer for inline media display."""

    id = serializers.UUIDField(read_only=True)
    file = serializers.FileField(read_only=True)
    media_type = serializers.CharField(read_only=True)
    order = serializers.IntegerField(read_only=True)
