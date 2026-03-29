from __future__ import annotations

from rest_framework import serializers

from apps.common.serializers import BaseModelSerializer

from .models import DevicePushToken, Notification


# ---------------------------------------------------------------------------
# Lightweight sender representation
# ---------------------------------------------------------------------------


class SenderSerializer(serializers.Serializer):
    """Minimal user representation for the notification sender.

    Matches the AuthorSerializer shape used in social serializers so the
    frontend can use the same ``Author`` type for both.
    """

    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    profile_photo = serializers.ImageField(read_only=True)
    age = serializers.IntegerField(read_only=True)


# ---------------------------------------------------------------------------
# Notification serializers
# ---------------------------------------------------------------------------


class NotificationSerializer(BaseModelSerializer):
    """Full read representation of a notification."""

    sender = SenderSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "sender",
            "notification_type",
            "title",
            "body",
            "data",
            "is_read",
            "created_at",
        ]


class NotificationListSerializer(BaseModelSerializer):
    """Notification representation for list endpoints."""

    sender = SenderSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "sender",
            "notification_type",
            "title",
            "body",
            "data",
            "is_read",
            "created_at",
        ]


# ---------------------------------------------------------------------------
# Device token serializers
# ---------------------------------------------------------------------------


class DeviceTokenRegisterSerializer(serializers.Serializer):
    """Validates input for registering / updating a device push token."""

    token = serializers.CharField()
    platform = serializers.ChoiceField(choices=DevicePushToken.Platform.choices)


class DeviceTokenDeregisterSerializer(serializers.Serializer):
    """Validates input for deactivating a device push token (e.g., on logout)."""

    token = serializers.CharField()


# ---------------------------------------------------------------------------
# Mark-read serializers
# ---------------------------------------------------------------------------


class MarkReadSerializer(serializers.Serializer):
    """Validates input for marking notifications as read.

    If ``notification_id`` is omitted (or null), all notifications are
    marked as read for the requesting user.
    """

    notification_id = serializers.UUIDField(required=False, allow_null=True)
