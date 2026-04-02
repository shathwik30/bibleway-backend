from __future__ import annotations
from rest_framework import serializers
from apps.common.serializers import BaseTimestampedSerializer
from .models import VerseFallbackPool, VerseOfDay


class VerseOfDaySerializer(BaseTimestampedSerializer):
    """Full read representation of a Verse of the Day."""

    class Meta:
        model = VerseOfDay
        fields = [
            "id",
            "bible_reference",
            "verse_text",
            "background_image",
            "display_date",
            "is_active",
            "created_at",
            "updated_at",
        ]


class VerseFallbackPoolSerializer(BaseTimestampedSerializer):
    """Full read representation of a fallback pool verse."""

    class Meta:
        model = VerseFallbackPool
        fields = [
            "id",
            "bible_reference",
            "verse_text",
            "background_image",
            "is_active",
            "created_at",
            "updated_at",
        ]


class UnifiedVerseResponseSerializer(serializers.Serializer):
    """Unified response shape for both scheduled and fallback verses.

    Always includes ``display_date``, ``source``, and the verse fields
    so that clients receive a consistent payload regardless of the
    underlying model.
    """

    id = serializers.UUIDField(read_only=True)
    bible_reference = serializers.CharField(read_only=True)
    verse_text = serializers.CharField(read_only=True)
    background_image = serializers.ImageField(read_only=True, allow_null=True)
    display_date = serializers.DateField(read_only=True)
    source = serializers.CharField(read_only=True)
