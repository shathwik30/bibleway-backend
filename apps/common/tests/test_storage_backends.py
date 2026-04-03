"""Tests for apps.common.storage_backends — S3-compatible storage."""

from __future__ import annotations

import pytest

from apps.common.storage_backends import PrivateMediaStorage, PublicMediaStorage


class TestPublicMediaStorage:
    def test_default_acl_is_none(self):
        s = PublicMediaStorage()
        assert s.default_acl is None

    def test_querystring_auth_enabled(self):
        s = PublicMediaStorage()
        assert s.querystring_auth is True

    def test_querystring_expire_7_days(self):
        s = PublicMediaStorage()
        assert s.querystring_expire == 604800


class TestPrivateMediaStorage:
    def test_default_acl_is_none(self):
        s = PrivateMediaStorage()
        assert s.default_acl is None

    def test_querystring_auth_enabled(self):
        s = PrivateMediaStorage()
        assert s.querystring_auth is True

    def test_querystring_expire_1_hour(self):
        s = PrivateMediaStorage()
        assert s.querystring_expire == 3600
