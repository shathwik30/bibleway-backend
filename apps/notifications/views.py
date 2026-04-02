from __future__ import annotations
from typing import Any
from uuid import UUID
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from apps.common.throttles import DeviceTokenRateThrottle
from apps.common.views import BaseAPIView
from .serializers import (
    DeviceTokenDeregisterSerializer,
    DeviceTokenRegisterSerializer,
    MarkReadSerializer,
    NotificationListSerializer,
    NotificationSerializer,
)

from .services import DevicePushTokenService, NotificationService


class NotificationListView(BaseAPIView):
    """GET /notifications/ -- paginated list of notifications for the current user."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._notification_service = NotificationService()

    def get(self, request: Request) -> Response:
        notifications = self._notification_service.list_user_notifications(
            user_id=request.user.id,
        )

        return self.paginated_response(
            notifications, NotificationListSerializer, request
        )


class NotificationMarkReadView(BaseAPIView):
    """POST /notifications/read/ -- mark one or all notifications as read."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._notification_service = NotificationService()

    def post(self, request: Request) -> Response:
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notification_id: UUID | None = serializer.validated_data.get("notification_id")

        if notification_id is not None:
            notification = self._notification_service.mark_as_read(
                user_id=request.user.id,
                notification_id=notification_id,
            )
            out = NotificationSerializer(notification)

            return self.success_response(
                data=out.data,
                message="Notification marked as read.",
            )

        count = self._notification_service.mark_all_as_read(
            user_id=request.user.id,
        )

        return self.success_response(
            data={"updated_count": count},
            message="All notifications marked as read.",
        )


class NotificationUnreadCountView(BaseAPIView):
    """GET /notifications/unread-count/ -- return unread notification count."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._notification_service = NotificationService()

    def get(self, request: Request) -> Response:
        count = self._notification_service.get_unread_count(
            user_id=request.user.id,
        )

        return self.success_response(data={"unread_count": count})


class NotificationDeleteView(BaseAPIView):
    """DELETE /notifications/<uuid:pk>/ -- delete a single notification."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._notification_service = NotificationService()

    def delete(self, request: Request, pk: UUID) -> Response:
        self._notification_service.delete_notification(
            user_id=request.user.id,
            notification_id=pk,
        )

        return self.no_content_response()


class DeviceTokenRegisterView(BaseAPIView):
    """POST /notifications/device-tokens/ -- register or update a push token."""

    permission_classes = [IsAuthenticated]

    throttle_classes = [DeviceTokenRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._token_service = DevicePushTokenService()

    def post(self, request: Request) -> Response:
        serializer = DeviceTokenRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        device_token = self._token_service.register_token(
            user_id=request.user.id,
            token=data["token"],
            platform=data["platform"],
        )

        return self.created_response(
            data={
                "id": str(device_token.pk),
                "token": device_token.token,
                "platform": device_token.platform,
                "is_active": device_token.is_active,
            },
            message="Device token registered successfully.",
        )


class DeviceTokenDeregisterView(BaseAPIView):
    """POST /notifications/device-tokens/deregister/ -- deactivate a push token.

    Used during logout to stop push notifications to a specific device.
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._token_service = DevicePushTokenService()

    def post(self, request: Request) -> Response:
        serializer = DeviceTokenDeregisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._token_service.deactivate_token(
            user_id=request.user.id,
            token=serializer.validated_data["token"],
        )

        return self.success_response(
            data={},
            message="Device token deactivated successfully.",
        )
