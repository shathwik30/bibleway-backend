from django.urls import re_path

from apps.chat.consumers import ChatConsumer

UUID_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

websocket_urlpatterns = [
    re_path(r"ws/chat/$", ChatConsumer.as_asgi()),
    # Legacy path used by existing mobile/web clients
    re_path(r"ws/user/$", ChatConsumer.as_asgi()),
]
