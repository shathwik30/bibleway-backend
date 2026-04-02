"""Tests for apps.notifications.services — NotificationService and DevicePushTokenService."""

from __future__ import annotations
from unittest.mock import patch
from uuid import uuid4
import pytest
from apps.common.exceptions import ForbiddenError, NotFoundError
from apps.notifications.models import DevicePushToken, Notification
from apps.notifications.services import DevicePushTokenService, NotificationService


@pytest.mark.django_db
class TestNotificationServiceCreate:
    def setup_method(self):
        self.service = NotificationService()

    @patch(
        "apps.notifications.services.NotificationService.create_notification.__module__"
    )
    def test_create_notification(self, _mock, user, user2):
        """create_notification persists a notification and dispatches a push task."""

        with patch("apps.notifications.tasks.send_push_notification.delay"):
            notification = self.service.create_notification(
                recipient_id=user.id,
                sender_id=user2.id,
                notification_type="follow",
                title="New follower",
                body=f"{user2.full_name} followed you.",
            )

        assert isinstance(notification, Notification)
        assert notification.recipient_id == user.id
        assert notification.sender_id == user2.id
        assert notification.notification_type == "follow"
        assert notification.title == "New follower"
        assert notification.is_read is False

    def test_create_notification_dispatches_push(self, user, user2):
        with patch(
            "apps.notifications.tasks.send_push_notification.delay"
        ) as mock_push:
            self.service.create_notification(
                recipient_id=user.id,
                sender_id=user2.id,
                notification_type="comment",
                title="New comment",
                body="Someone commented.",
            )
            mock_push.assert_called_once()
            call_kwargs = mock_push.call_args
            assert call_kwargs.kwargs["user_id"] == str(user.id)
            assert call_kwargs.kwargs["title"] == "New comment"

    def test_create_notification_push_failure_does_not_raise(self, user, user2):
        """If the push task dispatch fails, the notification is still created."""

        with patch(
            "apps.notifications.tasks.send_push_notification.delay",
            side_effect=Exception("Redis down"),
        ):
            notification = self.service.create_notification(
                recipient_id=user.id,
                sender_id=user2.id,
                notification_type="follow",
                title="Follower",
                body="Followed.",
            )

        assert notification.pk is not None

    def test_create_with_data_payload(self, user, user2):
        with patch("apps.notifications.tasks.send_push_notification.delay"):
            notification = self.service.create_notification(
                recipient_id=user.id,
                sender_id=user2.id,
                notification_type="comment",
                title="Comment",
                body="Body",
                data={"post_id": "abc123"},
            )

        assert notification.data == {"post_id": "abc123"}


@pytest.mark.django_db
class TestNotificationServiceList:
    def setup_method(self):
        self.service = NotificationService()

    def test_list_user_notifications(self, user, user2):
        from conftest import NotificationFactory

        NotificationFactory(recipient=user, sender=user2)
        NotificationFactory(recipient=user, sender=user2)
        NotificationFactory(recipient=user2, sender=user)
        qs = self.service.list_user_notifications(user_id=user.id)
        assert qs.count() == 2

    def test_list_empty(self, user):
        qs = self.service.list_user_notifications(user_id=user.id)
        assert qs.count() == 0


@pytest.mark.django_db
class TestNotificationServiceMarkRead:
    def setup_method(self):
        self.service = NotificationService()

    def test_mark_as_read(self, user, user2):
        from conftest import NotificationFactory

        n = NotificationFactory(recipient=user, sender=user2, is_read=False)
        result = self.service.mark_as_read(user_id=user.id, notification_id=n.id)
        assert result.is_read is True

    def test_mark_as_read_not_found(self, user):
        with pytest.raises(NotFoundError):
            self.service.mark_as_read(user_id=user.id, notification_id=uuid4())

    def test_mark_as_read_wrong_user(self, user, user2):
        from conftest import NotificationFactory

        n = NotificationFactory(recipient=user2, sender=user)

        with pytest.raises(NotFoundError):
            self.service.mark_as_read(user_id=user.id, notification_id=n.id)

    def test_mark_all_as_read(self, user, user2):
        from conftest import NotificationFactory

        NotificationFactory(recipient=user, sender=user2, is_read=False)
        NotificationFactory(recipient=user, sender=user2, is_read=False)
        NotificationFactory(recipient=user, sender=user2, is_read=True)
        count = self.service.mark_all_as_read(user_id=user.id)
        assert count == 2

    def test_mark_all_as_read_returns_zero_when_all_read(self, user, user2):
        from conftest import NotificationFactory

        NotificationFactory(recipient=user, sender=user2, is_read=True)
        count = self.service.mark_all_as_read(user_id=user.id)
        assert count == 0


@pytest.mark.django_db
class TestNotificationServiceUnreadCount:
    def setup_method(self):
        self.service = NotificationService()

    def test_get_unread_count(self, user, user2):
        from conftest import NotificationFactory

        NotificationFactory(recipient=user, sender=user2, is_read=False)
        NotificationFactory(recipient=user, sender=user2, is_read=False)
        NotificationFactory(recipient=user, sender=user2, is_read=True)
        assert self.service.get_unread_count(user_id=user.id) == 2

    def test_zero_unread(self, user):
        assert self.service.get_unread_count(user_id=user.id) == 0


@pytest.mark.django_db
class TestNotificationServiceDelete:
    def setup_method(self):
        self.service = NotificationService()

    def test_delete_notification(self, user, user2):
        from conftest import NotificationFactory

        n = NotificationFactory(recipient=user, sender=user2)
        self.service.delete_notification(user_id=user.id, notification_id=n.id)
        assert not Notification.objects.filter(pk=n.id).exists()

    def test_delete_not_found(self, user):
        with pytest.raises(NotFoundError):
            self.service.delete_notification(user_id=user.id, notification_id=uuid4())

    def test_delete_forbidden_other_user(self, user, user2):
        from conftest import NotificationFactory

        n = NotificationFactory(recipient=user2, sender=user)

        with pytest.raises(ForbiddenError, match="only delete your own"):
            self.service.delete_notification(user_id=user.id, notification_id=n.id)


@pytest.mark.django_db
class TestDevicePushTokenServiceRegister:
    def setup_method(self):
        self.service = DevicePushTokenService()

    def test_register_new_token(self, user):
        token = self.service.register_token(
            user_id=user.id,
            token="fcm-token-abc123",
            platform="ios",
        )
        assert isinstance(token, DevicePushToken)
        assert token.token == "fcm-token-abc123"
        assert token.platform == "ios"
        assert token.is_active is True
        assert token.user_id == user.id

    def test_update_existing_token(self, user):
        """Registering the same token twice updates instead of creating a duplicate."""
        self.service.register_token(
            user_id=user.id, token="fcm-token-xyz", platform="ios"
        )
        token = self.service.register_token(
            user_id=user.id, token="fcm-token-xyz", platform="android"
        )
        assert token.platform == "android"
        assert DevicePushToken.objects.filter(token="fcm-token-xyz").count() == 1

    def test_token_reassignment(self, user, user2):
        """Token registered by user1 can be reassigned to user2 (device changed hands)."""
        self.service.register_token(
            user_id=user.id, token="shared-token", platform="ios"
        )
        token = self.service.register_token(
            user_id=user2.id, token="shared-token", platform="ios"
        )
        assert token.user_id == user2.id
        assert DevicePushToken.objects.filter(token="shared-token").count() == 1


@pytest.mark.django_db
class TestDevicePushTokenServiceDeactivate:
    def setup_method(self):
        self.service = DevicePushTokenService()

    def test_deactivate_token(self, user):
        self.service.register_token(
            user_id=user.id, token="deactivate-me", platform="ios"
        )
        self.service.deactivate_token(user_id=user.id, token="deactivate-me")
        token = DevicePushToken.objects.get(token="deactivate-me")
        assert token.is_active is False

    def test_deactivate_other_users_token_raises(self, user, user2):
        self.service.register_token(
            user_id=user2.id, token="belongs-to-user2", platform="ios"
        )

        with pytest.raises(NotFoundError, match="not found"):
            self.service.deactivate_token(
                user_id=user.id,
                token="belongs-to-user2",
            )

        token = DevicePushToken.objects.get(token="belongs-to-user2")
        assert token.is_active is True

    def test_deactivate_nonexistent_raises(self, user):
        with pytest.raises(NotFoundError, match="not found"):
            self.service.deactivate_token(
                user_id=user.id,
                token="nonexistent-token",
            )


@pytest.mark.django_db
class TestDevicePushTokenServiceGetActive:
    def setup_method(self):
        self.service = DevicePushTokenService()

    def test_get_active_tokens(self, user):
        from conftest import DevicePushTokenFactory

        DevicePushTokenFactory(user=user, is_active=True, token="active1")
        DevicePushTokenFactory(user=user, is_active=True, token="active2")
        DevicePushTokenFactory(user=user, is_active=False, token="inactive1")
        tokens = self.service.get_active_tokens(user_id=user.id)
        assert tokens.count() == 2

    def test_get_active_tokens_empty(self, user):
        tokens = self.service.get_active_tokens(user_id=user.id)
        assert tokens.count() == 0

    def test_does_not_return_other_users_tokens(self, user, user2):
        from conftest import DevicePushTokenFactory

        DevicePushTokenFactory(user=user2, is_active=True, token="other-user-token")
        tokens = self.service.get_active_tokens(user_id=user.id)
        assert tokens.count() == 0
