from __future__ import annotations

import logging
from uuid import UUID

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.common.constants import CACHE_TIMEOUT_TRANSLATION, CACHE_TIMEOUT_UNREAD_COUNT
from apps.common.exceptions import BadRequestError, ForbiddenError, NotFoundError
from apps.common.services import BaseService
from apps.common.utils import (
    build_notification_data,
    get_blocked_user_ids,
    send_notification_safe,
    truncate_text,
)

from .models import Conversation, Message

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 1000


class ConversationService(BaseService[Conversation]):
    """Business logic for one-to-one conversations."""

    model = Conversation

    def get_queryset(self) -> QuerySet[Conversation]:
        return (
            super()
            .get_queryset()
            .select_related("user1", "user2", "last_message_sender")
        )

    @staticmethod
    def _canonical_ids(user_a_id: UUID, user_b_id: UUID) -> tuple[UUID, UUID]:
        """Return user IDs in canonical order (smaller first)."""
        if user_a_id < user_b_id:
            return user_a_id, user_b_id
        return user_b_id, user_a_id

    @transaction.atomic
    def get_or_create_conversation(
        self, *, user_a_id: UUID, user_b_id: UUID
    ) -> tuple[Conversation, bool]:
        """Create or retrieve a conversation between two users."""
        if user_a_id == user_b_id:
            raise BadRequestError(detail="Cannot start a conversation with yourself.")

        blocked = get_blocked_user_ids(user_a_id)
        if user_b_id in blocked:
            raise ForbiddenError(detail="Cannot start a conversation with this user.")

        u1, u2 = self._canonical_ids(user_a_id, user_b_id)
        conversation, created = Conversation.objects.get_or_create(
            user1_id=u1, user2_id=u2
        )

        if created:
            logger.info("Conversation created between %s and %s", u1, u2)

        return conversation, created

    def list_user_conversations(self, *, user_id: UUID) -> QuerySet[Conversation]:
        """Return conversations for a user, annotated with unread counts."""
        blocked = get_blocked_user_ids(user_id)
        qs = self.get_queryset().filter(Q(user1_id=user_id) | Q(user2_id=user_id))
        if blocked:
            qs = qs.exclude(Q(user1_id__in=blocked) | Q(user2_id__in=blocked))

        qs = qs.annotate(
            _unread_count=Count(
                "messages",
                filter=Q(messages__is_read=False) & ~Q(messages__sender_id=user_id),
            )
        )

        return qs.filter(last_message_at__isnull=False)

    def get_conversation_for_user(
        self, *, user_id: UUID, conversation_id: UUID
    ) -> Conversation:
        """Retrieve a conversation, verifying the user is a participant."""
        conversation = self.get_by_id(conversation_id)
        if user_id not in (conversation.user1_id, conversation.user2_id):
            raise ForbiddenError(
                detail="You are not a participant of this conversation."
            )
        return conversation

    @staticmethod
    def get_other_user_id(conversation: Conversation, user_id: UUID) -> UUID:
        """Return the ID of the other participant in the conversation."""
        if conversation.user1_id == user_id:
            return conversation.user2_id
        return conversation.user1_id

    def get_total_unread_count(self, *, user_id: UUID) -> int:
        """Return total unread messages across all conversations, cached for 30s."""
        cache_key = f"chat_unread:{user_id}"
        count: int | None = cache.get(cache_key)
        if count is not None:
            return count

        count = (
            Message.objects.filter(
                Q(conversation__user1_id=user_id) | Q(conversation__user2_id=user_id),
                is_read=False,
            )
            .exclude(sender_id=user_id)
            .count()
        )
        cache.set(cache_key, count, timeout=CACHE_TIMEOUT_UNREAD_COUNT)
        return count


class MessageService(BaseService[Message]):
    """Business logic for chat messages."""

    model = Message

    def get_queryset(self) -> QuerySet[Message]:
        return super().get_queryset().select_related("sender")

    def _conversation_service(self) -> ConversationService:
        return ConversationService()

    @transaction.atomic
    def create_message(
        self, *, conversation_id: UUID, sender_id: UUID, text: str
    ) -> tuple[Message, UUID]:
        """Create a message and update the conversation metadata.

        Returns a tuple of (message, recipient_id) so the caller can
        dispatch notifications outside the transaction.
        """
        conv_svc = self._conversation_service()
        conversation = conv_svc.get_conversation_for_user(
            user_id=sender_id, conversation_id=conversation_id
        )

        recipient_id = conv_svc.get_other_user_id(conversation, sender_id)
        blocked = get_blocked_user_ids(sender_id)
        if recipient_id in blocked:
            raise ForbiddenError(detail="Cannot send messages to this user.")

        message = Message.objects.create(
            conversation=conversation,
            sender_id=sender_id,
            text=text,
        )

        now = timezone.now()
        Conversation.objects.filter(pk=conversation.pk).update(
            last_message_text=truncate_text(text, MAX_MESSAGE_LENGTH),
            last_message_at=now,
            last_message_sender_id=sender_id,
            updated_at=now,
        )

        cache.delete(f"chat_unread:{recipient_id}")
        cache.delete(f"chat_unread:{sender_id}")

        logger.info(
            "Message sent: conversation=%s sender=%s",
            conversation_id,
            sender_id,
        )
        return message, recipient_id

    def send_notification(
        self,
        *,
        recipient_id: UUID,
        sender_id: UUID,
        conversation_id: UUID,
        text: str,
    ) -> None:
        """Dispatch a push notification for a new message."""
        send_notification_safe(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type="new_message",
            title="New message",
            body=truncate_text(text, 100),
            data=build_notification_data(
                "new_message",
                conversation_id=str(conversation_id),
            ),
        )

    def list_messages(
        self, *, conversation_id: UUID, user_id: UUID
    ) -> QuerySet[Message]:
        """Return messages for a conversation, verifying user is a participant."""
        self._conversation_service().get_conversation_for_user(
            user_id=user_id, conversation_id=conversation_id
        )
        return self.get_queryset().filter(conversation_id=conversation_id)

    def mark_messages_as_read(self, *, conversation_id: UUID, user_id: UUID) -> int:
        """Mark all unread messages from the other user as read."""
        count = (
            Message.objects.filter(
                conversation_id=conversation_id,
                is_read=False,
            )
            .exclude(sender_id=user_id)
            .update(is_read=True)
        )

        if count > 0:
            cache.delete(f"chat_unread:{user_id}")

        return count


class TranslationService:
    """Translates chat messages via Google Cloud Translation API with caching."""

    def translate_message(
        self,
        *,
        message_id: UUID,
        target_language: str,
        user_id: UUID,
    ) -> dict[str, str]:
        """Translate a single message text into the target language.

        The result is cached for 24 hours keyed by (message_id, target_language).
        The user must be a participant of the conversation that owns the message.
        """
        cache_key = f"msg_translate:{message_id}:{target_language}"
        cached: str | None = cache.get(cache_key)
        if cached is not None:
            return {
                "translated_text": cached,
                "source_language": "",
                "target_language": target_language,
            }

        try:
            message = Message.objects.select_related("conversation").get(pk=message_id)
        except Message.DoesNotExist:
            raise NotFoundError(detail="Message not found.")

        conversation = message.conversation
        if user_id not in (conversation.user1_id, conversation.user2_id):
            raise ForbiddenError(detail="You are not a participant of this conversation.")

        translated_text, detected_source = self._call_google_translate(
            message.text, target_language=target_language
        )

        cache.set(cache_key, translated_text, timeout=CACHE_TIMEOUT_TRANSLATION)

        return {
            "translated_text": translated_text,
            "source_language": detected_source,
            "target_language": target_language,
        }

    @staticmethod
    def _call_google_translate(
        text: str, *, target_language: str
    ) -> tuple[str, str]:
        """Call Google Cloud Translation API v2. Returns (translated_text, detected_source)."""
        import requests
        from django.conf import settings

        api_key: str = getattr(settings, "GOOGLE_TRANSLATE_API_KEY", "")
        if not api_key:
            logger.error("GOOGLE_TRANSLATE_API_KEY is not configured.")
            raise BadRequestError(detail="Translation service is not configured.")

        url = "https://translation.googleapis.com/language/translate/v2"
        payload = {
            "q": text,
            "target": target_language,
            "format": "text",
            "key": api_key,
        }

        try:
            response = requests.post(url, data=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            translations = data.get("data", {}).get("translations", [])

            if not translations:
                raise BadRequestError(detail="Translation API returned no results.")

            entry = translations[0]
            return entry["translatedText"], entry.get("detectedSourceLanguage", "")

        except requests.RequestException as exc:
            logger.exception("Google Translate API call failed: %s", exc)
            raise BadRequestError(
                detail="Translation service is temporarily unavailable."
            )
