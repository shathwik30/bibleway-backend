from __future__ import annotations

from uuid import UUID

from rest_framework import serializers

from apps.common.serializers import BaseModelSerializer, BaseTimestampedSerializer

from .models import Conversation, Message


class ParticipantSerializer(serializers.Serializer):
    """Minimal user representation for chat participants."""

    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    profile_photo = serializers.ImageField(read_only=True)
    age = serializers.IntegerField(read_only=True)


class ConversationListSerializer(BaseTimestampedSerializer):
    """Read representation of a conversation for list endpoints."""

    other_user = serializers.SerializerMethodField()
    last_message_is_mine = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(source="_unread_count", read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "other_user",
            "last_message_text",
            "last_message_at",
            "last_message_is_mine",
            "unread_count",
            "created_at",
            "updated_at",
        ]

    def _get_request_user_id(self) -> UUID | None:
        user = self.context.get("user")
        return user.id if user else None

    def get_other_user(self, obj: Conversation) -> dict | None:
        """Return the other participant's profile data."""
        user_id = self._get_request_user_id()
        if user_id is None:
            return None
        other = obj.user2 if obj.user1_id == user_id else obj.user1
        return ParticipantSerializer(other).data

    def get_last_message_is_mine(self, obj: Conversation) -> bool:
        """Check whether the last message was sent by the requesting user."""
        user_id = self._get_request_user_id()
        if user_id is None:
            return False
        return obj.last_message_sender_id == user_id


class MessageSerializer(BaseModelSerializer):
    """Read representation of a single chat message."""

    sender = ParticipantSerializer(read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "text",
            "is_read",
            "created_at",
        ]
        read_only_fields = ["id", "sender", "is_read", "created_at"]


class MessageCreateSerializer(serializers.Serializer):
    """Validates input for sending a chat message."""

    text = serializers.CharField(max_length=1000)


class TranslateMessageSerializer(serializers.Serializer):
    """Validates input for translating a chat message."""

    message_id = serializers.UUIDField()
    target_language = serializers.CharField(max_length=10)


class CreateConversationSerializer(serializers.Serializer):
    """Validates input for creating or retrieving a conversation."""

    user_id = serializers.UUIDField()
