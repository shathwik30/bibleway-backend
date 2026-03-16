"""Tests for apps.common.permissions — IsOwner, IsOwnerOrReadOnly, IsAdminUser, IsNotBlocked."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest

from apps.common.permissions import IsAdminUser, IsNotBlocked, IsOwner, IsOwnerOrReadOnly


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(user_id=None, method="GET", is_staff=False):
    """Build a minimal mock DRF request."""
    request = MagicMock()
    if user_id is not None:
        request.user.id = user_id
        request.user.is_staff = is_staff
        request.user.__bool__ = lambda self: True
    else:
        request.user = None
    request.method = method
    return request


def _make_view(target_user_id=None, has_method=True):
    """Build a minimal mock view for IsNotBlocked tests."""
    view = MagicMock()
    if has_method:
        view.get_target_user_id = MagicMock(return_value=target_user_id)
    else:
        del view.get_target_user_id
    return view


def _make_obj_with_author(author_id):
    """Object with an 'author' attribute (like Post)."""
    obj = SimpleNamespace(author=True, author_id=author_id)
    return obj


def _make_obj_with_user(user_id):
    """Object with a 'user' attribute (like Bookmark, Purchase)."""
    obj = SimpleNamespace(user=True, user_id=user_id)
    return obj


# ---------------------------------------------------------------------------
# IsOwner
# ---------------------------------------------------------------------------


class TestIsOwner:
    def test_allows_owner_via_author_id(self):
        uid = uuid4()
        perm = IsOwner()
        request = _make_request(user_id=uid)
        obj = _make_obj_with_author(author_id=uid)
        assert perm.has_object_permission(request, MagicMock(), obj) is True

    def test_allows_owner_via_user_id(self):
        uid = uuid4()
        perm = IsOwner()
        request = _make_request(user_id=uid)
        obj = _make_obj_with_user(user_id=uid)
        assert perm.has_object_permission(request, MagicMock(), obj) is True

    def test_denies_non_owner_author(self):
        perm = IsOwner()
        request = _make_request(user_id=uuid4())
        obj = _make_obj_with_author(author_id=uuid4())
        assert perm.has_object_permission(request, MagicMock(), obj) is False

    def test_denies_non_owner_user(self):
        perm = IsOwner()
        request = _make_request(user_id=uuid4())
        obj = _make_obj_with_user(user_id=uuid4())
        assert perm.has_object_permission(request, MagicMock(), obj) is False

    def test_denies_when_no_author_or_user_attr(self):
        perm = IsOwner()
        request = _make_request(user_id=uuid4())
        obj = SimpleNamespace(title="no owner fields")
        assert perm.has_object_permission(request, MagicMock(), obj) is False

    def test_author_takes_precedence_over_user(self):
        """When obj has both author and user, author_id is checked."""
        uid = uuid4()
        other = uuid4()
        perm = IsOwner()
        request = _make_request(user_id=uid)
        obj = SimpleNamespace(
            author=True, author_id=uid,
            user=True, user_id=other,
        )
        assert perm.has_object_permission(request, MagicMock(), obj) is True


# ---------------------------------------------------------------------------
# IsOwnerOrReadOnly
# ---------------------------------------------------------------------------


class TestIsOwnerOrReadOnly:
    def test_get_allowed_for_anyone(self):
        perm = IsOwnerOrReadOnly()
        request = _make_request(user_id=uuid4(), method="GET")
        obj = _make_obj_with_author(author_id=uuid4())  # different user
        assert perm.has_object_permission(request, MagicMock(), obj) is True

    def test_head_allowed_for_anyone(self):
        perm = IsOwnerOrReadOnly()
        request = _make_request(user_id=uuid4(), method="HEAD")
        obj = _make_obj_with_author(author_id=uuid4())
        assert perm.has_object_permission(request, MagicMock(), obj) is True

    def test_options_allowed_for_anyone(self):
        perm = IsOwnerOrReadOnly()
        request = _make_request(user_id=uuid4(), method="OPTIONS")
        obj = _make_obj_with_author(author_id=uuid4())
        assert perm.has_object_permission(request, MagicMock(), obj) is True

    def test_write_allowed_for_owner(self):
        uid = uuid4()
        perm = IsOwnerOrReadOnly()
        request = _make_request(user_id=uid, method="PUT")
        obj = _make_obj_with_author(author_id=uid)
        assert perm.has_object_permission(request, MagicMock(), obj) is True

    def test_write_denied_for_non_owner(self):
        perm = IsOwnerOrReadOnly()
        request = _make_request(user_id=uuid4(), method="DELETE")
        obj = _make_obj_with_author(author_id=uuid4())
        assert perm.has_object_permission(request, MagicMock(), obj) is False

    def test_patch_denied_for_non_owner(self):
        perm = IsOwnerOrReadOnly()
        request = _make_request(user_id=uuid4(), method="PATCH")
        obj = _make_obj_with_user(user_id=uuid4())
        assert perm.has_object_permission(request, MagicMock(), obj) is False

    def test_post_denied_for_non_owner_via_user_field(self):
        perm = IsOwnerOrReadOnly()
        request = _make_request(user_id=uuid4(), method="POST")
        obj = _make_obj_with_user(user_id=uuid4())
        assert perm.has_object_permission(request, MagicMock(), obj) is False


# ---------------------------------------------------------------------------
# IsAdminUser
# ---------------------------------------------------------------------------


class TestIsAdminUser:
    def test_allows_staff(self):
        perm = IsAdminUser()
        request = _make_request(user_id=uuid4(), is_staff=True)
        assert perm.has_permission(request, MagicMock()) is True

    def test_denies_non_staff(self):
        perm = IsAdminUser()
        request = _make_request(user_id=uuid4(), is_staff=False)
        assert perm.has_permission(request, MagicMock()) is False

    def test_denies_none_user(self):
        perm = IsAdminUser()
        request = _make_request(user_id=None)
        assert perm.has_permission(request, MagicMock()) is False


# ---------------------------------------------------------------------------
# IsNotBlocked
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestIsNotBlocked:
    def test_denies_when_block_exists(self, user, user2):
        from conftest import BlockRelationshipFactory

        BlockRelationshipFactory(blocker=user, blocked=user2)
        perm = IsNotBlocked()
        request = _make_request(user_id=user2.id)
        view = _make_view(target_user_id=user.id)
        assert perm.has_permission(request, view) is False

    def test_allows_when_no_block(self, user, user2):
        perm = IsNotBlocked()
        request = _make_request(user_id=user2.id)
        view = _make_view(target_user_id=user.id)
        assert perm.has_permission(request, view) is True

    def test_denies_reverse_block(self, user, user2):
        """If the requesting user blocked the target, access is also denied."""
        from conftest import BlockRelationshipFactory

        BlockRelationshipFactory(blocker=user2, blocked=user)
        perm = IsNotBlocked()
        request = _make_request(user_id=user2.id)
        view = _make_view(target_user_id=user.id)
        assert perm.has_permission(request, view) is False

    def test_allows_when_target_is_none(self, user):
        """If get_target_user_id returns None, access is allowed."""
        perm = IsNotBlocked()
        request = _make_request(user_id=user.id)
        view = _make_view(target_user_id=None)
        assert perm.has_permission(request, view) is True

    def test_denies_when_view_missing_method(self, user):
        """If the view doesn't implement get_target_user_id, deny by default."""
        perm = IsNotBlocked()
        request = _make_request(user_id=user.id)
        view = _make_view(has_method=False)
        assert perm.has_permission(request, view) is False
