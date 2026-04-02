from django.contrib import admin
from .models import (
    Comment,
    Post,
    PostMedia,
    Prayer,
    PrayerMedia,
    Reaction,
    Reply,
    Report,
)


class PostMediaInline(admin.TabularInline):
    model = PostMedia

    extra = 0

    readonly_fields = ["id", "created_at"]


class PrayerMediaInline(admin.TabularInline):
    model = PrayerMedia

    extra = 0

    readonly_fields = ["id", "created_at"]


class ReplyInline(admin.TabularInline):
    model = Reply

    extra = 0

    readonly_fields = ["id", "created_at"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["author", "text_content_preview", "is_boosted", "created_at"]

    list_filter = ["is_boosted", "created_at"]

    search_fields = ["author__email", "author__full_name", "text_content"]

    readonly_fields = ["id", "created_at", "updated_at"]

    inlines = [PostMediaInline]

    @admin.display(description="Content")
    def text_content_preview(self, obj):
        return obj.text_content[:80] if obj.text_content else "(media only)"


@admin.register(Prayer)
class PrayerAdmin(admin.ModelAdmin):
    list_display = ["author", "title", "created_at"]

    list_filter = ["created_at"]

    search_fields = ["author__email", "author__full_name", "title"]

    readonly_fields = ["id", "created_at", "updated_at"]

    inlines = [PrayerMediaInline]


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ["user", "emoji_type", "content_type", "created_at"]

    list_filter = ["emoji_type", "content_type"]

    search_fields = ["user__email"]

    readonly_fields = ["id", "created_at"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["user", "text_preview", "content_type", "created_at"]

    list_filter = ["content_type", "created_at"]

    search_fields = ["user__email", "text"]

    readonly_fields = ["id", "created_at", "updated_at"]

    inlines = [ReplyInline]

    @admin.display(description="Text")
    def text_preview(self, obj):
        return obj.text[:80]


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ["user", "comment", "created_at"]

    search_fields = ["user__email", "text"]

    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["reporter", "reason", "status", "content_type", "created_at"]

    list_filter = ["reason", "status", "content_type"]

    search_fields = ["reporter__email", "description"]

    readonly_fields = ["id", "created_at", "updated_at"]
