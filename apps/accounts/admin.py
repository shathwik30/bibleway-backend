from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import BlockRelationship, FollowRelationship, OTPToken, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "email",
        "full_name",
        "country",
        "preferred_language",
        "is_active",
        "is_staff",
        "date_joined",
    ]

    list_filter = ["is_active", "is_staff", "gender", "country", "preferred_language"]

    search_fields = ["email", "full_name"]

    readonly_fields = ["id", "email", "date_joined"]

    ordering = ["-date_joined"]

    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        (
            "Personal Info",
            {
                "fields": (
                    "full_name",
                    "date_of_birth",
                    "gender",
                    "phone_number",
                    "country",
                    "preferred_language",
                )
            },
        ),
        (
            "Profile",
            {"fields": ("profile_photo", "bio")},
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_email_verified",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Dates", {"fields": ("date_joined", "last_login")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "date_of_birth",
                    "gender",
                    "country",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(FollowRelationship)
class FollowRelationshipAdmin(admin.ModelAdmin):
    list_display = ["follower", "following", "created_at"]

    search_fields = ["follower__email", "following__email"]

    readonly_fields = ["id", "created_at"]


@admin.register(BlockRelationship)
class BlockRelationshipAdmin(admin.ModelAdmin):
    list_display = ["blocker", "blocked", "created_at"]

    search_fields = ["blocker__email", "blocked__email"]

    readonly_fields = ["id", "created_at"]


@admin.register(OTPToken)
class OTPTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "purpose", "used", "attempts", "expires_at", "created_at"]

    list_filter = ["purpose", "used"]

    search_fields = ["user__email"]

    readonly_fields = ["id", "hashed_code", "created_at"]
