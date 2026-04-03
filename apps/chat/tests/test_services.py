from __future__ import annotations

from uuid import uuid4

import pytest

from apps.chat.models import Conversation, Message
from apps.chat.services import ConversationService, MessageService
from apps.common.exceptions import BadRequestError, ForbiddenError, NotFoundError
from conftest import (
    BlockRelationshipFactory,
    ConversationFactory,
    MessageFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestConversationServiceGetOrCreate:
    def setup_method(self):
        self.service = ConversationService()

    def test_creates_new_conversation(self, user, user2):
        conv, created = self.service.get_or_create_conversation(
            user_a_id=user.id, user_b_id=user2.id
        )

        assert created is True
        assert isinstance(conv, Conversation)
        assert {conv.user1_id, conv.user2_id} == {user.id, user2.id}

    def test_returns_existing_conversation(self, user, user2):
        conv1, _ = self.service.get_or_create_conversation(
            user_a_id=user.id, user_b_id=user2.id
        )
        conv2, created = self.service.get_or_create_conversation(
            user_a_id=user2.id, user_b_id=user.id
        )

        assert created is False
        assert conv1.pk == conv2.pk

    def test_canonical_ordering(self, user, user2):
        conv, _ = self.service.get_or_create_conversation(
            user_a_id=user.id, user_b_id=user2.id
        )

        assert conv.user1_id < conv.user2_id

    def test_self_conversation_raises(self, user):
        with pytest.raises(BadRequestError, match="yourself"):
            self.service.get_or_create_conversation(
                user_a_id=user.id, user_b_id=user.id
            )

    def test_blocked_user_raises(self, user, user2):
        BlockRelationshipFactory(blocker=user, blocked=user2)

        with pytest.raises(ForbiddenError, match="Cannot start"):
            self.service.get_or_create_conversation(
                user_a_id=user.id, user_b_id=user2.id
            )


@pytest.mark.django_db
class TestConversationServiceList:
    def setup_method(self):
        self.service = ConversationService()

    def test_lists_user_conversations(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        MessageFactory(conversation=conv, sender=u1)
        Conversation.objects.filter(pk=conv.pk).update(last_message_at=conv.created_at)

        result = list(self.service.list_user_conversations(user_id=user.id))
        assert len(result) == 1
        assert result[0].pk == conv.pk

    def test_excludes_conversations_without_messages(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        ConversationFactory(user1=u1, user2=u2)

        result = list(self.service.list_user_conversations(user_id=user.id))
        assert len(result) == 0

    def test_excludes_blocked_users(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        Conversation.objects.filter(pk=conv.pk).update(last_message_at=conv.created_at)
        BlockRelationshipFactory(blocker=user, blocked=user2)

        result = list(self.service.list_user_conversations(user_id=user.id))
        assert len(result) == 0

    def test_annotates_unread_count(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        MessageFactory(conversation=conv, sender=user2, is_read=False)
        MessageFactory(conversation=conv, sender=user2, is_read=False)
        MessageFactory(conversation=conv, sender=user, is_read=False)
        Conversation.objects.filter(pk=conv.pk).update(last_message_at=conv.created_at)

        result = list(self.service.list_user_conversations(user_id=user.id))
        assert len(result) == 1
        assert result[0]._unread_count == 2


@pytest.mark.django_db
class TestConversationServiceGetForUser:
    def setup_method(self):
        self.service = ConversationService()

    def test_returns_conversation_for_participant(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)

        result = self.service.get_conversation_for_user(
            user_id=user.id, conversation_id=conv.id
        )
        assert result.pk == conv.pk

    def test_raises_for_non_participant(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        outsider = UserFactory()

        with pytest.raises(ForbiddenError, match="not a participant"):
            self.service.get_conversation_for_user(
                user_id=outsider.id, conversation_id=conv.id
            )

    def test_raises_for_nonexistent_conversation(self, user):
        with pytest.raises(NotFoundError):
            self.service.get_conversation_for_user(
                user_id=user.id, conversation_id=uuid4()
            )


@pytest.mark.django_db
class TestConversationServiceUnreadCount:
    def setup_method(self):
        self.service = ConversationService()

    def test_returns_unread_count(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        MessageFactory(conversation=conv, sender=user2, is_read=False)
        MessageFactory(conversation=conv, sender=user2, is_read=False)
        MessageFactory(conversation=conv, sender=user, is_read=False)

        count = self.service.get_total_unread_count(user_id=user.id)
        assert count == 2

    def test_returns_zero_when_all_read(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        MessageFactory(conversation=conv, sender=user2, is_read=True)

        count = self.service.get_total_unread_count(user_id=user.id)
        assert count == 0


@pytest.mark.django_db
class TestMessageServiceCreate:
    def setup_method(self):
        self.service = MessageService()

    def test_creates_message(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)

        msg, recipient_id = self.service.create_message(
            conversation_id=conv.id, sender_id=user.id, text="Hello!"
        )

        assert isinstance(msg, Message)
        assert msg.text == "Hello!"
        assert msg.sender_id == user.id
        assert msg.conversation_id == conv.id
        assert msg.is_read is False

    def test_returns_recipient_id(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)

        _, recipient_id = self.service.create_message(
            conversation_id=conv.id, sender_id=user.id, text="Hey"
        )

        assert recipient_id == user2.id

    def test_updates_conversation_last_message(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)

        self.service.create_message(
            conversation_id=conv.id, sender_id=user.id, text="Hey there"
        )

        conv.refresh_from_db()
        assert conv.last_message_text == "Hey there"
        assert conv.last_message_at is not None
        assert conv.last_message_sender_id == user.id

    def test_blocked_user_cannot_send(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        BlockRelationshipFactory(blocker=user2, blocked=user)

        with pytest.raises(ForbiddenError, match="Cannot send"):
            self.service.create_message(
                conversation_id=conv.id, sender_id=user.id, text="Hey"
            )

    def test_non_participant_cannot_send(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        outsider = UserFactory()

        with pytest.raises(ForbiddenError, match="not a participant"):
            self.service.create_message(
                conversation_id=conv.id, sender_id=outsider.id, text="Hey"
            )

    def test_sticker_message(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)

        msg, _ = self.service.create_message(
            conversation_id=conv.id,
            sender_id=user.id,
            text="[sticker:42]",
        )
        assert msg.text == "[sticker:42]"


@pytest.mark.django_db
class TestMessageServiceList:
    def setup_method(self):
        self.service = MessageService()

    def test_lists_messages_for_conversation(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        MessageFactory(conversation=conv, sender=u1, text="msg1")
        MessageFactory(conversation=conv, sender=u2, text="msg2")

        msgs = list(
            self.service.list_messages(conversation_id=conv.id, user_id=user.id)
        )
        assert len(msgs) == 2

    def test_non_participant_cannot_list(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        outsider = UserFactory()

        with pytest.raises(ForbiddenError):
            self.service.list_messages(conversation_id=conv.id, user_id=outsider.id)


@pytest.mark.django_db
class TestMessageServiceMarkRead:
    def setup_method(self):
        self.service = MessageService()

    def test_marks_other_user_messages_as_read(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        MessageFactory(conversation=conv, sender=user2, is_read=False)
        MessageFactory(conversation=conv, sender=user2, is_read=False)
        MessageFactory(conversation=conv, sender=user, is_read=False)

        count = self.service.mark_messages_as_read(
            conversation_id=conv.id, user_id=user.id
        )

        assert count == 2
        assert (
            Message.objects.filter(
                conversation=conv, sender=user2, is_read=True
            ).count()
            == 2
        )
        assert (
            Message.objects.filter(
                conversation=conv, sender=user, is_read=False
            ).count()
            == 1
        )
