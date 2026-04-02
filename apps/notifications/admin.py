from django.contrib import admin
from .models import DevicePushToken, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "recipient",
        "notification_type",
        "title",
        "is_read",
        "created_at",
    ]

    list_filter = ["notification_type", "is_read"]

    search_fields = ["recipient__email", "title", "body"]

    readonly_fields = ["id", "created_at"]


@admin.register(DevicePushToken)
class DevicePushTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "platform", "is_active", "created_at"]

    list_filter = ["platform", "is_active"]

    search_fields = ["user__email"]

    readonly_fields = ["id", "created_at", "updated_at"]
