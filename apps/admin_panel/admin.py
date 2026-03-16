from django.contrib import admin

from .models import AdminLog, AdminRole, BoostTier


@admin.register(AdminRole)
class AdminRoleAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__email", "user__full_name"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(AdminLog)
class AdminLogAdmin(admin.ModelAdmin):
    list_display = [
        "admin_user",
        "action",
        "target_model",
        "target_id",
        "created_at",
    ]
    list_filter = ["action", "target_model"]
    search_fields = ["admin_user__email", "detail", "target_id"]
    readonly_fields = ["id", "created_at"]


@admin.register(BoostTier)
class BoostTierAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "duration_days",
        "display_price",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active"]
    readonly_fields = ["id", "created_at", "updated_at"]
