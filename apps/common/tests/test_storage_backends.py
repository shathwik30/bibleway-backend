"""Tests for apps.common.storage_backends — S3-compatible storage."""

from __future__ import annotations

import pytest

from apps.common.storage_backends import PrivateMediaStorage, PublicMediaStorage


class TestPublicMediaStorage:
    def test_default_acl_is_public_read(self):
        s = PublicMediaStorage()
        assert s.default_acl == "public-read"

    def test_querystring_auth_disabled(self):
        s = PublicMediaStorage()
        assert s.querystring_auth is False


class TestPrivateMediaStorage:
    def test_default_acl_is_private(self):
        s = PrivateMediaStorage()
        assert s.default_acl == "private"

    def test_querystring_auth_enabled(self):
        s = PrivateMediaStorage()
        assert s.querystring_auth is True

    def test_querystring_expire_is_set(self):
        s = PrivateMediaStorage()
        assert s.querystring_expire == 3600
