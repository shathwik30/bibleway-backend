from __future__ import annotations

from django.urls import path

from .views import (
    DeviceTokenDeregisterView,
    DeviceTokenRegisterView,
    NotificationDeleteView,
    NotificationListView,
    NotificationMarkReadView,
    NotificationUnreadCountView,
)

app_name = "notifications"

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("read/", NotificationMarkReadView.as_view(), name="notification-mark-read"),
    path(
        "unread-count/",
        NotificationUnreadCountView.as_view(),
        name="notification-unread-count",
    ),
    path(
        "<uuid:pk>/",
        NotificationDeleteView.as_view(),
        name="notification-delete",
    ),
    path(
        "device-tokens/",
        DeviceTokenRegisterView.as_view(),
        name="device-token-register",
    ),
    path(
        "device-tokens/deregister/",
        DeviceTokenDeregisterView.as_view(),
        name="device-token-deregister",
    ),
]
