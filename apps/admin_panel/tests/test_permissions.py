"""Tests for apps.admin_panel.permissions — RBAC admin permission classes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.contrib.auth.models import AnonymousUser

from apps.admin_panel.models import AdminRole
from apps.admin_panel.permissions import (
    IsAdminStaff,
    IsContentAdmin,
    IsModerationAdmin,
    IsSuperAdmin,
)

# Import factories from root conftest (available via pytest fixtures).
# We use the conftest factories directly for convenience.
from conftest import AdminRoleFactory, UserFactory


@pytest.fixture
def mock_view():
    """Return a minimal mock view for permission checks."""
    return MagicMock()


@pytest.fixture
def request_factory():
    """Return a callable that creates a mock request with a given user."""
    def _make(user):
        req = MagicMock()
        req.user = user
        return req
    return _make


# ════════════════════════════════════════════════════════════════
# IsAdminStaff
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIsAdminStaff:
    """Tests for IsAdminStaff permission."""

    def test_anonymous_user_denied(self, mock_view, request_factory):
        """Anonymous users are denied."""
        perm = IsAdminStaff()
        request = request_factory(AnonymousUser())
        assert perm.has_permission(request, mock_view) is False

    def test_non_staff_user_denied(self, mock_view, request_factory):
        """Authenticated non-staff user is denied."""
        user = UserFactory(is_staff=False)
        perm = IsAdminStaff()
        assert perm.has_permission(request_factory(user), mock_view) is False

    def test_staff_without_admin_role_denied(self, mock_view, request_factory):
        """Staff user without an AdminRole is denied."""
        user = UserFactory(is_staff=True)
        perm = IsAdminStaff()
        assert perm.has_permission(request_factory(user), mock_view) is False

    def test_staff_with_admin_role_allowed(self, mock_view, request_factory):
        """Staff user with an AdminRole is allowed."""
        role = AdminRoleFactory(role=AdminRole.RoleType.CONTENT_ADMIN)
        perm = IsAdminStaff()
        assert perm.has_permission(request_factory(role.user), mock_view) is True

    def test_none_user_denied(self, mock_view):
        """Request with user=None is denied."""
        perm = IsAdminStaff()
        request = MagicMock()
        request.user = None
        assert perm.has_permission(request, mock_view) is False


# ════════════════════════════════════════════════════════════════
# IsSuperAdmin
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIsSuperAdmin:
    """Tests for IsSuperAdmin permission."""

    def test_anonymous_user_denied(self, mock_view, request_factory):
        perm = IsSuperAdmin()
        assert perm.has_permission(request_factory(AnonymousUser()), mock_view) is False

    def test_non_staff_denied(self, mock_view, request_factory):
        user = UserFactory(is_staff=False)
        perm = IsSuperAdmin()
        assert perm.has_permission(request_factory(user), mock_view) is False

    def test_staff_without_role_denied(self, mock_view, request_factory):
        user = UserFactory(is_staff=True)
        perm = IsSuperAdmin()
        assert perm.has_permission(request_factory(user), mock_view) is False

    def test_super_admin_allowed(self, mock_view, request_factory):
        role = AdminRoleFactory(role=AdminRole.RoleType.SUPER_ADMIN)
        perm = IsSuperAdmin()
        assert perm.has_permission(request_factory(role.user), mock_view) is True

    def test_content_admin_denied(self, mock_view, request_factory):
        role = AdminRoleFactory(role=AdminRole.RoleType.CONTENT_ADMIN)
        perm = IsSuperAdmin()
        assert perm.has_permission(request_factory(role.user), mock_view) is False

    def test_moderation_admin_denied(self, mock_view, request_factory):
        role = AdminRoleFactory(role=AdminRole.RoleType.MODERATION_ADMIN)
        perm = IsSuperAdmin()
        assert perm.has_permission(request_factory(role.user), mock_view) is False


# ════════════════════════════════════════════════════════════════
# IsContentAdmin
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIsContentAdmin:
    """Tests for IsContentAdmin permission."""

    def test_anonymous_user_denied(self, mock_view, request_factory):
        perm = IsContentAdmin()
        assert perm.has_permission(request_factory(AnonymousUser()), mock_view) is False

    def test_non_staff_denied(self, mock_view, request_factory):
        user = UserFactory(is_staff=False)
        perm = IsContentAdmin()
        assert perm.has_permission(request_factory(user), mock_view) is False

    def test_staff_without_role_denied(self, mock_view, request_factory):
        user = UserFactory(is_staff=True)
        perm = IsContentAdmin()
        assert perm.has_permission(request_factory(user), mock_view) is False

    def test_super_admin_allowed(self, mock_view, request_factory):
        role = AdminRoleFactory(role=AdminRole.RoleType.SUPER_ADMIN)
        perm = IsContentAdmin()
        assert perm.has_permission(request_factory(role.user), mock_view) is True

    def test_content_admin_allowed(self, mock_view, request_factory):
        role = AdminRoleFactory(role=AdminRole.RoleType.CONTENT_ADMIN)
        perm = IsContentAdmin()
        assert perm.has_permission(request_factory(role.user), mock_view) is True

    def test_moderation_admin_denied(self, mock_view, request_factory):
        role = AdminRoleFactory(role=AdminRole.RoleType.MODERATION_ADMIN)
        perm = IsContentAdmin()
        assert perm.has_permission(request_factory(role.user), mock_view) is False


# ════════════════════════════════════════════════════════════════
# IsModerationAdmin
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIsModerationAdmin:
    """Tests for IsModerationAdmin permission."""

    def test_anonymous_user_denied(self, mock_view, request_factory):
        perm = IsModerationAdmin()
        assert perm.has_permission(request_factory(AnonymousUser()), mock_view) is False

    def test_non_staff_denied(self, mock_view, request_factory):
        user = UserFactory(is_staff=False)
        perm = IsModerationAdmin()
        assert perm.has_permission(request_factory(user), mock_view) is False

    def test_staff_without_role_denied(self, mock_view, request_factory):
        user = UserFactory(is_staff=True)
        perm = IsModerationAdmin()
        assert perm.has_permission(request_factory(user), mock_view) is False

    def test_super_admin_allowed(self, mock_view, request_factory):
        role = AdminRoleFactory(role=AdminRole.RoleType.SUPER_ADMIN)
        perm = IsModerationAdmin()
        assert perm.has_permission(request_factory(role.user), mock_view) is True

    def test_moderation_admin_allowed(self, mock_view, request_factory):
        role = AdminRoleFactory(role=AdminRole.RoleType.MODERATION_ADMIN)
        perm = IsModerationAdmin()
        assert perm.has_permission(request_factory(role.user), mock_view) is True

    def test_content_admin_denied(self, mock_view, request_factory):
        role = AdminRoleFactory(role=AdminRole.RoleType.CONTENT_ADMIN)
        perm = IsModerationAdmin()
        assert perm.has_permission(request_factory(role.user), mock_view) is False
