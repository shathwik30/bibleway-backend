from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .models import AdminRole


class IsAdminStaff(BasePermission):
    """Allow access only to users with is_staff=True and an AdminRole."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_staff:
            return False
        return AdminRole.objects.filter(user=request.user).exists()


class IsSuperAdmin(BasePermission):
    """Allow access only to Super Admin users."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_staff:
            return False
        try:
            return request.user.admin_role.role == AdminRole.RoleType.SUPER_ADMIN
        except AdminRole.DoesNotExist:
            return False


class IsContentAdmin(BasePermission):
    """Allow access to Content Admin or Super Admin."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_staff:
            return False
        try:
            return request.user.admin_role.role in (
                AdminRole.RoleType.SUPER_ADMIN,
                AdminRole.RoleType.CONTENT_ADMIN,
            )
        except AdminRole.DoesNotExist:
            return False


class IsModerationAdmin(BasePermission):
    """Allow access to Moderation Admin or Super Admin."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_staff:
            return False
        try:
            return request.user.admin_role.role in (
                AdminRole.RoleType.SUPER_ADMIN,
                AdminRole.RoleType.MODERATION_ADMIN,
            )
        except AdminRole.DoesNotExist:
            return False
