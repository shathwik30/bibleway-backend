from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.request import Request
from rest_framework.views import APIView


class IsOwner(BasePermission):
    """Allows access only to the owner of the object."""

    def has_object_permission(
        self, request: Request, view: APIView, obj: Any
    ) -> bool:
        if hasattr(obj, "author"):
            return obj.author_id == request.user.id
        if hasattr(obj, "user"):
            return obj.user_id == request.user.id
        return False


class IsOwnerOrReadOnly(BasePermission):
    """Allow read access to anyone, write access only to the owner."""

    def has_object_permission(
        self, request: Request, view: APIView, obj: Any
    ) -> bool:
        if request.method in SAFE_METHODS:
            return True
        if hasattr(obj, "author"):
            return obj.author_id == request.user.id
        if hasattr(obj, "user"):
            return obj.user_id == request.user.id
        return False


class IsAdminUser(BasePermission):
    """Allows access only to admin/staff users."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_staff)


class IsNotBlocked(BasePermission):
    """Denies access if either user has blocked the other.

    Checks both directions: requesting user blocked by target,
    and requesting user has blocked target.
    Expects the view to have a `get_target_user_id()` method.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        from django.db.models import Q

        from apps.accounts.models import BlockRelationship

        if not hasattr(view, "get_target_user_id"):
            import logging

            logging.getLogger(__name__).warning(
                "IsNotBlocked used on %s but get_target_user_id() is not "
                "implemented. Denying access by default.",
                view.__class__.__name__,
            )
            return False

        target_user_id = view.get_target_user_id()
        if target_user_id is None:
            return True
        return not BlockRelationship.objects.filter(
            Q(blocker_id=target_user_id, blocked_id=request.user.id)
            | Q(blocker_id=request.user.id, blocked_id=target_user_id)
        ).exists()
