from django.contrib import admin

from .models import VerseFallbackPool, VerseOfDay


@admin.register(VerseOfDay)
class VerseOfDayAdmin(admin.ModelAdmin):
    list_display = ["display_date", "bible_reference", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["bible_reference", "verse_text"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-display_date"]


@admin.register(VerseFallbackPool)
class VerseFallbackPoolAdmin(admin.ModelAdmin):
    list_display = ["bible_reference", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["bible_reference", "verse_text"]
    readonly_fields = ["id", "created_at", "updated_at"]
