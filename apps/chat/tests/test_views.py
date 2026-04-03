from __future__ import annotations

from unittest.mock import patch

import pytest
from rest_framework import status

from apps.chat.models import Conversation, Message
from conftest import (
    BlockRelationshipFactory,
    ConversationFactory,
    MessageFactory,
    UserFactory,
)

CONVERSATIONS_URL = "/api/v1/chat/conversations/"
UNREAD_COUNT_URL = "/api/v1/chat/unread-count/"


def messages_url(conversation_id):
    return f"/api/v1/chat/conversations/{conversation_id}/messages/"


def mark_read_url(conversation_id):
    return f"/api/v1/chat/conversations/{conversation_id}/messages/mark-read/"


@pytest.mark.django_db
class TestConversationListCreateView:
    def test_list_empty(self, auth_client):
        response = auth_client.get(CONVERSATIONS_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Success"

    def test_list_returns_conversations(self, auth_client, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        Conversation.objects.filter(pk=conv.pk).update(
            last_message_at=conv.created_at, last_message_text="hi"
        )

        response = auth_client.get(CONVERSATIONS_URL)
        assert response.status_code == status.HTTP_200_OK
        results = response.data["data"]["results"]
        assert len(results) == 1
        assert results[0]["id"] == str(conv.pk)
        assert "other_user" in results[0]
        assert "unread_count" in results[0]

    def test_list_excludes_blocked(self, auth_client, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        Conversation.objects.filter(pk=conv.pk).update(last_message_at=conv.created_at)
        BlockRelationshipFactory(blocker=user, blocked=user2)

        response = auth_client.get(CONVERSATIONS_URL)
        assert response.data["data"]["results"] == []

    def test_create_conversation(self, auth_client, user, user2):
        response = auth_client.post(
            CONVERSATIONS_URL, {"user_id": str(user2.id)}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"] == "Conversation created."
        assert Conversation.objects.count() == 1

    def test_create_returns_existing(self, auth_client, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        ConversationFactory(user1=u1, user2=u2)

        response = auth_client.post(
            CONVERSATIONS_URL, {"user_id": str(user2.id)}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Conversation retrieved."
        assert Conversation.objects.count() == 1

    def test_create_with_self_returns_400(self, auth_client, user):
        response = auth_client.post(
            CONVERSATIONS_URL, {"user_id": str(user.id)}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_blocked_user_returns_403(self, auth_client, user, user2):
        BlockRelationshipFactory(blocker=user2, blocked=user)

        response = auth_client.post(
            CONVERSATIONS_URL, {"user_id": str(user2.id)}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(CONVERSATIONS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMessageListCreateView:
    def test_list_messages(self, auth_client, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        MessageFactory(conversation=conv, sender=u1, text="hello")
        MessageFactory(conversation=conv, sender=u2, text="hey")

        response = auth_client.get(messages_url(conv.id))
        assert response.status_code == status.HTTP_200_OK
        results = response.data["data"]["results"]
        assert len(results) == 2

    @patch("apps.chat.services.send_notification_safe")
    def test_send_message(self, mock_notify, auth_client, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)

        response = auth_client.post(
            messages_url(conv.id), {"text": "Hi there!"}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["text"] == "Hi there!"
        assert response.data["data"]["sender"]["id"] == str(user.id)

    @patch("apps.chat.services.send_notification_safe")
    def test_send_sticker(self, mock_notify, auth_client, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)

        response = auth_client.post(
            messages_url(conv.id), {"text": "[sticker:7]"}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["text"] == "[sticker:7]"

    @patch("apps.chat.services.send_notification_safe")
    def test_send_empty_message_returns_400(
        self, mock_notify, auth_client, user, user2
    ):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)

        response = auth_client.post(messages_url(conv.id), {"text": ""}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_participant_returns_403(self, user, user2):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        outsider = UserFactory()
        client = APIClient()
        refresh = RefreshToken.for_user(outsider)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = client.get(messages_url(conv.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self, api_client, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)

        response = api_client.get(messages_url(conv.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMessageMarkReadView:
    def test_marks_messages_as_read(self, auth_client, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        MessageFactory(conversation=conv, sender=user2, is_read=False)
        MessageFactory(conversation=conv, sender=user2, is_read=False)

        response = auth_client.post(mark_read_url(conv.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["marked_read"] == 2
        assert (
            Message.objects.filter(
                conversation=conv, sender=user2, is_read=True
            ).count()
            == 2
        )

    def test_does_not_mark_own_messages(self, auth_client, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        MessageFactory(conversation=conv, sender=user, is_read=False)

        response = auth_client.post(mark_read_url(conv.id))
        assert response.data["data"]["marked_read"] == 0

    def test_unauthenticated_returns_401(self, api_client, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)

        response = api_client.post(mark_read_url(conv.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestChatUnreadCountView:
    def test_returns_unread_count(self, auth_client, user, user2):
        u1, u2 = sorted([user, user2], key=lambda u: u.pk)
        conv = ConversationFactory(user1=u1, user2=u2)
        MessageFactory(conversation=conv, sender=user2, is_read=False)
        MessageFactory(conversation=conv, sender=user2, is_read=False)
        MessageFactory(conversation=conv, sender=user, is_read=False)

        response = auth_client.get(UNREAD_COUNT_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["unread_count"] == 2

    def test_returns_zero_when_no_messages(self, auth_client):
        response = auth_client.get(UNREAD_COUNT_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["unread_count"] == 0

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(UNREAD_COUNT_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
