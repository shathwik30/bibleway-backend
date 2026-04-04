"""WebSocket consumer for real-time chat.

Connects on ws://<host>/ws/chat/?token=<jwt>
All actions use JSON frames: { "action": "<name>", "request_id": "...", ...data }
"""

from __future__ import annotations

import logging
from uuid import UUID

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from .services import ConversationService, MessageService

logger = logging.getLogger(__name__)

def _conv_group(cid: str) -> str:
    return f"chat.conversation.{cid}"


def _user_group(uid: str) -> str:
    return f"chat.user.{uid}"


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Handles one authenticated WebSocket connection per user."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.user_group = None
        self.joined_conversations: set[str] = set()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or isinstance(self.user, AnonymousUser):
            await self.close(code=4001)
            return

        self.user_group = _user_group(str(self.user.id))
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()

        # Broadcast presence
        await self._broadcast_presence(online=True)

    async def disconnect(self, code):
        if self.user and not isinstance(self.user, AnonymousUser):
            await self._broadcast_presence(online=False)

        # Leave all conversation groups
        for cid in list(self.joined_conversations):
            await self.channel_layer.group_discard(
                _conv_group(cid), self.channel_name
            )
        self.joined_conversations.clear()

        if self.user_group:
            await self.channel_layer.group_discard(
                self.user_group, self.channel_name
            )

    # ------------------------------------------------------------------
    # Inbound message dispatch
    # ------------------------------------------------------------------

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        request_id = content.get("request_id", "")

        handler = {
            "join_conversation": self._handle_join,
            "leave_conversation": self._handle_leave,
            "send_message": self._handle_send_message,
            "typing": self._handle_typing,
            "mark_read": self._handle_mark_read,
            "get_presence": self._handle_get_presence,
            "pong": self._handle_pong,
        }.get(action)

        if handler is None:
            await self.send_json(
                {"type": "error", "request_id": request_id, "detail": f"Unknown action: {action}"}
            )
            return

        try:
            await handler(content, request_id)
        except Exception as exc:
            logger.exception("WS action %s failed: %s", action, exc)
            await self.send_json(
                {"type": "error", "request_id": request_id, "detail": str(exc)}
            )

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    async def _handle_join(self, content, request_id):
        cid = content.get("conversation_id", "")
        # Verify user is a participant
        ok = await self._verify_participant(cid)
        if not ok:
            await self.send_json({"type": "error", "request_id": request_id, "detail": "Not a participant."})
            return
        group = _conv_group(cid)
        await self.channel_layer.group_add(group, self.channel_name)
        self.joined_conversations.add(cid)
        await self.send_json({"type": "joined", "request_id": request_id, "conversation_id": cid})

    async def _handle_leave(self, content, request_id):
        cid = content.get("conversation_id", "")
        group = _conv_group(cid)
        await self.channel_layer.group_discard(group, self.channel_name)
        self.joined_conversations.discard(cid)

    async def _handle_send_message(self, content, request_id):
        cid = content.get("conversation_id", "")
        text = (content.get("text") or content.get("content") or "").strip()
        if not text:
            await self.send_json({"type": "error", "request_id": request_id, "detail": "Empty message."})
            return

        msg_data, recipient_id = await self._create_message(cid, text)

        # Auto-join conversation group if not already
        group = _conv_group(cid)
        if cid not in self.joined_conversations:
            await self.channel_layer.group_add(group, self.channel_name)
            self.joined_conversations.add(cid)

        event = {
            "type": "chat.message",
            "data": {
                "conversation_id": cid,
                "message_id": msg_data["id"],
                "sender_id": str(self.user.id),
                "sender_name": self.user.full_name,
                "sender_photo": self._get_profile_photo_url(),
                "text": text,
                "is_read": False,
                "created_at": msg_data["created_at"],
            },
        }

        # Broadcast to conversation group
        await self.channel_layer.group_send(group, event)

        # Also send to recipient's personal group (for conversation list updates)
        await self.channel_layer.group_send(
            _user_group(str(recipient_id)),
            {
                "type": "chat.conversation_update",
                "data": {
                    "conversation_id": cid,
                    "last_message_text": text,
                    "last_message_at": msg_data["created_at"],
                    "last_message_is_mine": False,
                    "sender_name": self.user.full_name,
                },
            },
        )

        # Send push notification (fire-and-forget)
        await self._send_push(
            recipient_id=recipient_id,
            conversation_id=UUID(cid),
            text=text,
        )

    async def _handle_typing(self, content, request_id):
        cid = content.get("conversation_id", "")
        is_typing = content.get("is_typing", True)
        group = _conv_group(cid)
        await self.channel_layer.group_send(
            group,
            {
                "type": "chat.typing",
                "data": {
                    "conversation_id": cid,
                    "user_id": str(self.user.id),
                    "user_name": self.user.full_name,
                    "is_typing": is_typing,
                },
            },
        )

    async def _handle_mark_read(self, content, request_id):
        cid = content.get("conversation_id", "")
        count = await self._mark_read(cid)
        group = _conv_group(cid)
        await self.channel_layer.group_send(
            group,
            {
                "type": "chat.read_receipt",
                "data": {
                    "conversation_id": cid,
                    "user_id": str(self.user.id),
                    "count": count,
                },
            },
        )

    async def _handle_get_presence(self, content, request_id):
        cid = content.get("conversation_id", "")
        other_uid = await self._get_other_user_id(cid)
        if other_uid:
            is_online = await self._check_online(other_uid)
            await self.send_json({
                "type": "presence.status",
                "request_id": request_id,
                "data": {
                    "users": [{"user_id": str(other_uid), "is_online": is_online}],
                },
            })

    async def _handle_pong(self, content, request_id):
        pass  # heartbeat acknowledged

    # ------------------------------------------------------------------
    # Outbound event handlers (called via channel layer group_send)
    # ------------------------------------------------------------------

    async def chat_message(self, event):
        await self.send_json({"type": "message.sent", "data": event["data"]})

    async def chat_conversation_update(self, event):
        await self.send_json({"type": "conversation.updated", "data": event["data"]})

    async def chat_typing(self, event):
        # Don't echo typing back to the sender
        if event["data"].get("user_id") == str(self.user.id):
            return
        await self.send_json({"type": "typing", "data": event["data"]})

    async def chat_read_receipt(self, event):
        await self.send_json({"type": "read_receipt.updated", "data": event["data"]})

    async def chat_presence(self, event):
        await self.send_json({"type": "presence.updated", "data": event["data"]})

    # ------------------------------------------------------------------
    # Database helpers (sync → async)
    # ------------------------------------------------------------------

    @database_sync_to_async
    def _verify_participant(self, conversation_id: str) -> bool:
        try:
            ConversationService().get_conversation_for_user(
                user_id=self.user.id,
                conversation_id=UUID(conversation_id),
            )
            return True
        except Exception:
            return False

    @database_sync_to_async
    def _create_message(self, conversation_id: str, text: str) -> tuple[dict, UUID]:
        svc = MessageService()
        msg, recipient_id = svc.create_message(
            conversation_id=UUID(conversation_id),
            sender_id=self.user.id,
            text=text,
        )
        return {
            "id": str(msg.id),
            "created_at": msg.created_at.isoformat(),
        }, recipient_id

    @database_sync_to_async
    def _mark_read(self, conversation_id: str) -> int:
        return MessageService().mark_messages_as_read(
            conversation_id=UUID(conversation_id),
            user_id=self.user.id,
        )

    @database_sync_to_async
    def _get_other_user_id(self, conversation_id: str):
        try:
            svc = ConversationService()
            conv = svc.get_conversation_for_user(
                user_id=self.user.id,
                conversation_id=UUID(conversation_id),
            )
            return svc.get_other_user_id(conv, self.user.id)
        except Exception:
            return None

    @database_sync_to_async
    def _send_push(self, recipient_id: UUID, conversation_id: UUID, text: str):
        try:
            MessageService().send_notification(
                recipient_id=recipient_id,
                sender_id=self.user.id,
                conversation_id=conversation_id,
                text=text,
            )
        except Exception:
            pass

    async def _broadcast_presence(self, online: bool):
        """Notify all conversations this user is in about their presence change."""
        conv_ids = await self._get_user_conversation_ids()
        event = {
            "type": "chat.presence",
            "data": {
                "user_id": str(self.user.id),
                "is_online": online,
            },
        }
        for cid in conv_ids:
            await self.channel_layer.group_send(_conv_group(cid), event)

    @database_sync_to_async
    def _get_user_conversation_ids(self) -> list[str]:
        from django.db.models import Q
        from .models import Conversation

        return list(
            Conversation.objects.filter(
                Q(user1_id=self.user.id) | Q(user2_id=self.user.id)
            ).values_list("id", flat=True)
            .distinct()[:100]
        )

    def _get_profile_photo_url(self) -> str | None:
        try:
            if self.user.profile_photo:
                return self.user.profile_photo.url
        except Exception:
            pass
        return None

    @database_sync_to_async
    def _check_online(self, user_id: UUID) -> bool:
        # Check if user has an active channel in their group
        # With InMemoryChannelLayer this is approximate; with Redis it's more reliable
        # For now, presence is tracked via connect/disconnect broadcasts
        return False
