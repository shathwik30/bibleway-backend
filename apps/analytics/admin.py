from django.contrib import admin
from .models import BoostAnalyticSnapshot, PostBoost, PostView


@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = ["viewer", "content_type", "created_at"]

    list_filter = ["content_type"]

    readonly_fields = ["id", "created_at"]


@admin.register(PostBoost)
class PostBoostAdmin(admin.ModelAdmin):
    list_display = [
        "post",
        "user",
        "tier",
        "platform",
        "is_active",
        "activated_at",
        "expires_at",
    ]

    list_filter = ["is_active", "platform"]

    search_fields = ["user__email", "transaction_id"]

    readonly_fields = ["id", "created_at"]


@admin.register(BoostAnalyticSnapshot)
class BoostAnalyticSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "boost",
        "snapshot_date",
        "impressions",
        "reach",
        "engagement_rate",
    ]

    list_filter = ["snapshot_date"]

    readonly_fields = ["id", "created_at"]
