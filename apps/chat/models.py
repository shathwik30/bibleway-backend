from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, F, Q, UniqueConstraint
from apps.common.models import CreatedAtModel, TimeStampedModel


class Conversation(TimeStampedModel):
    """One-to-one conversation between two users.

    User1 always has the smaller UUID to enforce a canonical pair and
    prevent duplicate conversations.
    """

    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations_as_user1",
        db_index=True,
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations_as_user2",
        db_index=True,
    )
    last_message_text = models.CharField(max_length=1000, blank=True, default="")
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_message_sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        ordering = ["-last_message_at"]
        constraints = [
            UniqueConstraint(
                fields=["user1", "user2"],
                name="unique_conversation_pair",
            ),
            CheckConstraint(
                condition=Q(user1_id__lt=F("user2_id")),
                name="user1_lt_user2",
            ),
            CheckConstraint(
                condition=~Q(user1=F("user2")),
                name="prevent_self_conversation",
            ),
        ]
        indexes = [
            models.Index(fields=["user1", "-last_message_at"]),
            models.Index(fields=["user2", "-last_message_at"]),
        ]

    def __str__(self) -> str:
        return f"Conversation({self.user1_id}, {self.user2_id})"


class Message(CreatedAtModel):
    """A single text message or sticker in a conversation.

    Stickers are stored as ``[sticker:ID]`` text which the frontend
    parses and renders as GIF images.
    """

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True,
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        db_index=True,
    )
    text = models.TextField(max_length=1000)
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["conversation", "-created_at"]),
            models.Index(fields=["conversation", "is_read", "sender"]),
        ]

    def __str__(self) -> str:
        return f"Message({self.sender_id} -> {self.conversation_id})"
