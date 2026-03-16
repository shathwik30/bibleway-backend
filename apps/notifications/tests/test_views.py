"""Tests for apps.notifications.views — API endpoints for notifications and device tokens."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework import status


# ---------------------------------------------------------------------------
# Notification list
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationListView:
    url = "/api/v1/notifications/"

    def test_list_returns_200(self, auth_client, user, user2):
        from conftest import NotificationFactory

        NotificationFactory(recipient=user, sender=user2)
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Success"
        assert "data" in response.data

    def test_list_only_own_notifications(self, auth_client, user, user2):
        from conftest import NotificationFactory

        NotificationFactory(recipient=user, sender=user2)
        NotificationFactory(recipient=user2, sender=user)  # other user

        response = auth_client.get(self.url)
        results = response.data["data"]["results"]
        assert len(results) == 1

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Notification mark read
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationMarkReadView:
    url = "/api/v1/notifications/read/"

    def test_mark_single_as_read(self, auth_client, user, user2):
        from conftest import NotificationFactory

        n = NotificationFactory(recipient=user, sender=user2, is_read=False)
        response = auth_client.post(self.url, {"notification_id": str(n.id)})
        assert response.status_code == status.HTTP_200_OK
        assert "marked as read" in response.data["message"].lower()

    def test_mark_all_as_read(self, auth_client, user, user2):
        from conftest import NotificationFactory

        NotificationFactory(recipient=user, sender=user2, is_read=False)
        NotificationFactory(recipient=user, sender=user2, is_read=False)

        response = auth_client.post(self.url, {})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["updated_count"] == 2

    def test_mark_nonexistent_returns_404(self, auth_client, user):
        response = auth_client.post(self.url, {"notification_id": str(uuid4())})
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Notification unread count
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationUnreadCountView:
    url = "/api/v1/notifications/unread-count/"

    def test_returns_count(self, auth_client, user, user2):
        from conftest import NotificationFactory

        NotificationFactory(recipient=user, sender=user2, is_read=False)
        NotificationFactory(recipient=user, sender=user2, is_read=False)
        NotificationFactory(recipient=user, sender=user2, is_read=True)

        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["unread_count"] == 2

    def test_returns_zero(self, auth_client, user):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["unread_count"] == 0


# ---------------------------------------------------------------------------
# Notification delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationDeleteView:
    def _url(self, pk):
        return f"/api/v1/notifications/{pk}/"

    def test_delete_own_notification(self, auth_client, user, user2):
        from conftest import NotificationFactory

        n = NotificationFactory(recipient=user, sender=user2)
        response = auth_client.delete(self._url(n.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_nonexistent_returns_404(self, auth_client, user):
        response = auth_client.delete(self._url(uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_other_users_notification_returns_403(
        self, auth_client, user, user2
    ):
        from conftest import NotificationFactory

        n = NotificationFactory(recipient=user2, sender=user)
        response = auth_client.delete(self._url(n.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Device token register
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeviceTokenRegisterView:
    url = "/api/v1/notifications/device-tokens/"

    def test_register_new_token(self, auth_client, user):
        response = auth_client.post(
            self.url,
            {"token": "fcm-token-view-test", "platform": "ios"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["token"] == "fcm-token-view-test"
        assert response.data["data"]["platform"] == "ios"
        assert response.data["data"]["is_active"] is True

    def test_register_missing_fields(self, auth_client, user):
        response = auth_client.post(self.url, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_invalid_platform(self, auth_client, user):
        response = auth_client.post(
            self.url,
            {"token": "some-token", "platform": "windows"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.post(
            self.url,
            {"token": "some-token", "platform": "ios"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Device token deregister
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeviceTokenDeregisterView:
    url = "/api/v1/notifications/device-tokens/deregister/"

    def test_deregister_token(self, auth_client, user):
        from conftest import DevicePushTokenFactory

        DevicePushTokenFactory(user=user, token="deregister-me", is_active=True)
        response = auth_client.post(self.url, {"token": "deregister-me"})
        assert response.status_code == status.HTTP_200_OK
        assert "deactivated" in response.data["message"].lower()

    def test_deregister_nonexistent_returns_404(self, auth_client, user):
        response = auth_client.post(self.url, {"token": "no-such-token"})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_deregister_missing_token_returns_400(self, auth_client, user):
        response = auth_client.post(self.url, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
