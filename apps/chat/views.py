from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.pagination import FeedCursorPagination
from apps.common.throttles import FeedRateThrottle, SocialCreateThrottle
from apps.common.views import BaseAPIView

from .serializers import (
    ConversationListSerializer,
    CreateConversationSerializer,
    MessageCreateSerializer,
    MessageSerializer,
)
from .services import ConversationService, MessageService


class ConversationListCreateView(BaseAPIView):
    """GET  /conversations/  — list the current user's conversations.
    POST /conversations/  — create (or retrieve) a conversation with another user.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._conv_service = ConversationService()

    def get(self, request: Request) -> Response:
        conversations = self._conv_service.list_user_conversations(
            user_id=request.user.id,
        )
        return self.paginated_response(
            conversations, ConversationListSerializer, request
        )

    def post(self, request: Request) -> Response:
        serializer = CreateConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user_id: UUID = serializer.validated_data["user_id"]

        conversation, created = self._conv_service.get_or_create_conversation(
            user_a_id=request.user.id,
            user_b_id=target_user_id,
        )

        context = self.get_serializer_context(request)
        data = ConversationListSerializer(conversation, context=context).data

        if created:
            return self.created_response(
                data=data, message="Conversation created."
            )
        return self.success_response(data=data, message="Conversation retrieved.")


class MessageListCreateView(BaseAPIView):
    """GET  /conversations/<uuid>/messages/  — paginated message history.
    POST /conversations/<uuid>/messages/  — send a new message.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = FeedCursorPagination
    throttle_classes = [SocialCreateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._msg_service = MessageService()

    def get(self, request: Request, pk: UUID) -> Response:
        messages = self._msg_service.list_messages(
            conversation_id=pk, user_id=request.user.id
        )
        return self.paginated_response(messages, MessageSerializer, request)

    def post(self, request: Request, pk: UUID) -> Response:
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message, recipient_id = self._msg_service.create_message(
            conversation_id=pk,
            sender_id=request.user.id,
            text=serializer.validated_data["text"],
        )

        self._msg_service._send_notification(
            recipient_id=recipient_id,
            sender_id=request.user.id,
            conversation_id=pk,
            text=serializer.validated_data["text"],
        )

        context = self.get_serializer_context(request)
        data = MessageSerializer(message, context=context).data
        return self.created_response(data=data, message="Message sent.")


class MessageMarkReadView(BaseAPIView):
    """POST /conversations/<uuid>/messages/mark-read/ — mark messages as read."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._msg_service = MessageService()

    def post(self, request: Request, pk: UUID) -> Response:
        count = self._msg_service.mark_messages_as_read(
            conversation_id=pk, user_id=request.user.id
        )
        return self.success_response(
            data={"marked_read": count},
            message="Messages marked as read.",
        )


class ChatUnreadCountView(BaseAPIView):
    """GET /unread-count/ — total unread messages across all conversations."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._conv_service = ConversationService()

    def get(self, request: Request) -> Response:
        count = self._conv_service.get_total_unread_count(
            user_id=request.user.id
        )
        return self.success_response(data={"unread_count": count})
