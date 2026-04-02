"""Custom JWT authentication middleware for Django Channels WebSocket connections.

Mobile clients send JWT tokens via query string: ws://host/ws/<path>/?token=<jwt>
"""

from __future__ import annotations
import logging
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger("config.middleware")


@database_sync_to_async
def get_user_from_token(token_str: str):
    """Validate a JWT access token and return the associated user."""

    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        token = AccessToken(token_str)
        user_id = token["user_id"]

        return User.objects.get(id=user_id)

    except (InvalidToken, TokenError) as e:
        logger.warning("WebSocket JWT validation failed: %s", e)

        return AnonymousUser()

    except User.DoesNotExist:
        logger.warning("WebSocket JWT references non-existent user")

        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Authenticate WebSocket connections using JWT from query string."""

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        token_list = query_params.get("token", [])

        if token_list:
            scope["user"] = await get_user_from_token(token_list[0])

        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
