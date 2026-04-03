from django.contrib import admin

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "user1", "user2", "last_message_at", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user1__full_name", "user2__full_name"]
    raw_id_fields = ["user1", "user2", "last_message_sender"]
    list_select_related = ["user1", "user2", "last_message_sender"]
    list_per_page = 50


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "conversation",
        "sender",
        "short_text",
        "is_read",
        "created_at",
    ]
    list_filter = ["is_read", "created_at"]
    search_fields = ["sender__full_name", "text"]
    raw_id_fields = ["conversation", "sender"]
    list_select_related = ["conversation", "sender"]
    list_per_page = 50

    @admin.display(description="Text")
    def short_text(self, obj: Message) -> str:
        return obj.text[:80] if obj.text else ""
