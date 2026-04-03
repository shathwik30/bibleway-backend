from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.chat.models import Conversation, Message
from conftest import ConversationFactory, MessageFactory


@pytest.mark.django_db
class TestConversationModel:
    def test_create_conversation(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = Conversation.objects.create(user1=u1, user2=u2)

        assert conv.pk is not None
        assert conv.user1_id == u1.pk
        assert conv.user2_id == u2.pk
        assert conv.last_message_text == ""
        assert conv.last_message_at is None

    def test_unique_conversation_pair(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        Conversation.objects.create(user1=u1, user2=u2)

        with pytest.raises(IntegrityError):
            Conversation.objects.create(user1=u1, user2=u2)

    def test_user1_must_be_less_than_user2(self, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)

        with pytest.raises(IntegrityError):
            Conversation.objects.create(user1=u2, user2=u1)

    def test_self_conversation_prevented(self, user):
        with pytest.raises(IntegrityError):
            Conversation.objects.create(user1=user, user2=user)

    def test_str_representation(self):
        conv = ConversationFactory()
        assert str(conv.user1_id) in str(conv)
        assert str(conv.user2_id) in str(conv)

    def test_ordering_by_last_message_at(self):
        from django.utils import timezone

        conv1 = ConversationFactory(last_message_at=timezone.now())
        conv2 = ConversationFactory(
            last_message_at=timezone.now() + timezone.timedelta(hours=1)
        )

        convs = list(Conversation.objects.all())
        assert convs[0].pk == conv2.pk
        assert convs[1].pk == conv1.pk


@pytest.mark.django_db
class TestMessageModel:
    def test_create_message(self):
        conv = ConversationFactory()
        msg = Message.objects.create(
            conversation=conv, sender=conv.user1, text="Hello"
        )

        assert msg.pk is not None
        assert msg.text == "Hello"
        assert msg.is_read is False
        assert msg.sender_id == conv.user1_id

    def test_sticker_message(self):
        conv = ConversationFactory()
        msg = Message.objects.create(
            conversation=conv, sender=conv.user1, text="[sticker:5]"
        )

        assert msg.text == "[sticker:5]"

    def test_ordering_by_created_at_desc(self):
        conv = ConversationFactory()
        msg1 = MessageFactory(conversation=conv, sender=conv.user1, text="first")
        msg2 = MessageFactory(conversation=conv, sender=conv.user1, text="second")

        msgs = list(Message.objects.filter(conversation=conv))
        assert msgs[0].pk == msg2.pk
        assert msgs[1].pk == msg1.pk

    def test_cascade_delete_on_conversation(self):
        conv = ConversationFactory()
        conv_id = conv.pk
        MessageFactory(conversation=conv, sender=conv.user1)
        MessageFactory(conversation=conv, sender=conv.user2)

        assert Message.objects.filter(conversation_id=conv_id).count() == 2
        conv.delete()
        assert Message.objects.filter(conversation_id=conv_id).count() == 0

    def test_str_representation(self):
        msg = MessageFactory()
        assert str(msg.sender_id) in str(msg)
