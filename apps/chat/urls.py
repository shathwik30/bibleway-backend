from django.urls import path

from .views import (
    ChatUnreadCountView,
    ConversationListCreateView,
    MessageListCreateView,
    MessageMarkReadView,
)

app_name = "chat"

urlpatterns = [
    path(
        "conversations/",
        ConversationListCreateView.as_view(),
        name="conversation-list-create",
    ),
    path(
        "conversations/<uuid:pk>/messages/",
        MessageListCreateView.as_view(),
        name="message-list-create",
    ),
    path(
        "conversations/<uuid:pk>/messages/mark-read/",
        MessageMarkReadView.as_view(),
        name="message-mark-read",
    ),
    path(
        "unread-count/",
        ChatUnreadCountView.as_view(),
        name="chat-unread-count",
    ),
]
