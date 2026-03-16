from django.contrib import admin

from .models import (
    Bookmark,
    Highlight,
    Note,
    SegregatedChapter,
    SegregatedPage,
    SegregatedPageComment,
    SegregatedSection,
    TranslatedPageCache,
)


class SegregatedChapterInline(admin.TabularInline):
    model = SegregatedChapter
    extra = 0
    readonly_fields = ["id", "created_at"]


class SegregatedPageInline(admin.TabularInline):
    model = SegregatedPage
    extra = 0
    readonly_fields = ["id", "created_at"]
    fields = ["title", "order", "is_active", "youtube_url", "created_at"]


@admin.register(SegregatedSection)
class SegregatedSectionAdmin(admin.ModelAdmin):
    list_display = ["title", "age_min", "age_max", "order", "is_active"]
    list_filter = ["is_active"]
    list_editable = ["order", "is_active"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [SegregatedChapterInline]


@admin.register(SegregatedChapter)
class SegregatedChapterAdmin(admin.ModelAdmin):
    list_display = ["title", "section", "order", "is_active"]
    list_filter = ["section", "is_active"]
    list_editable = ["order", "is_active"]
    search_fields = ["title"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [SegregatedPageInline]


@admin.register(SegregatedPage)
class SegregatedPageAdmin(admin.ModelAdmin):
    list_display = ["title", "chapter", "order", "is_active"]
    list_filter = ["chapter__section", "is_active"]
    list_editable = ["order", "is_active"]
    search_fields = ["title"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(TranslatedPageCache)
class TranslatedPageCacheAdmin(admin.ModelAdmin):
    list_display = ["page", "language_code", "created_at"]
    list_filter = ["language_code"]
    search_fields = ["page__title"]
    readonly_fields = ["id", "created_at"]


@admin.register(SegregatedPageComment)
class SegregatedPageCommentAdmin(admin.ModelAdmin):
    list_display = ["user", "page", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__email", "page__title"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["user", "page"]


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ["user", "bookmark_type", "verse_reference", "created_at"]
    list_filter = ["bookmark_type"]
    search_fields = ["user__email", "verse_reference"]
    readonly_fields = ["id", "created_at"]


@admin.register(Highlight)
class HighlightAdmin(admin.ModelAdmin):
    list_display = ["user", "highlight_type", "color", "verse_reference", "created_at"]
    list_filter = ["highlight_type", "color"]
    search_fields = ["user__email", "verse_reference"]
    readonly_fields = ["id", "created_at"]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ["user", "note_type", "verse_reference", "created_at"]
    list_filter = ["note_type"]
    search_fields = ["user__email", "verse_reference", "text"]
    readonly_fields = ["id", "created_at", "updated_at"]
