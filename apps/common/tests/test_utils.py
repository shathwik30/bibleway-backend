"""Tests for apps.common.utils — OTP helpers, filename utils, notification data, and block cache."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.common.utils import (
    build_notification_data,
    generate_otp,
    get_blocked_user_ids,
    get_file_extension,
    get_otp_expiry,
    hash_otp,
    invalidate_blocked_user_cache,
    sanitize_filename,
    truncate_text,
    verify_otp,
)


# ---------------------------------------------------------------------------
# generate_otp
# ---------------------------------------------------------------------------


class TestGenerateOtp:
    def test_default_length_is_six(self):
        otp = generate_otp()
        assert len(otp) == 6

    def test_custom_length(self):
        otp = generate_otp(length=8)
        assert len(otp) == 8

    def test_only_numeric_chars(self):
        for _ in range(50):
            otp = generate_otp()
            assert otp.isdigit()

    def test_different_otps_generated(self):
        """OTPs are random; generating many should produce at least some variety."""
        otps = {generate_otp() for _ in range(100)}
        # With 6-digit codes, 100 draws should almost certainly produce > 1 unique
        assert len(otps) > 1


# ---------------------------------------------------------------------------
# hash_otp
# ---------------------------------------------------------------------------


class TestHashOtp:
    def test_returns_hex_string(self):
        h = hash_otp("123456")
        assert isinstance(h, str)
        # SHA-256 hex digest is 64 chars
        assert len(h) == 64

    def test_is_hmac_sha256(self):
        otp = "654321"
        expected = hmac.new(
            key=settings.SECRET_KEY.encode("utf-8"),
            msg=otp.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        assert hash_otp(otp) == expected

    def test_different_inputs_produce_different_hashes(self):
        assert hash_otp("111111") != hash_otp("222222")

    def test_same_input_produces_same_hash(self):
        assert hash_otp("123456") == hash_otp("123456")


# ---------------------------------------------------------------------------
# verify_otp
# ---------------------------------------------------------------------------


class TestVerifyOtp:
    def test_correct_otp_returns_true(self):
        otp = "123456"
        hashed = hash_otp(otp)
        assert verify_otp(otp, hashed) is True

    def test_incorrect_otp_returns_false(self):
        hashed = hash_otp("123456")
        assert verify_otp("654321", hashed) is False

    def test_empty_string_does_not_match_real_hash(self):
        hashed = hash_otp("123456")
        assert verify_otp("", hashed) is False


# ---------------------------------------------------------------------------
# get_otp_expiry
# ---------------------------------------------------------------------------


class TestGetOtpExpiry:
    def test_returns_future_datetime(self):
        expiry = get_otp_expiry()
        assert expiry > timezone.now()

    def test_default_10_minutes(self):
        before = timezone.now()
        expiry = get_otp_expiry()
        after = timezone.now()
        # Should be roughly 10 minutes from now
        assert before + timedelta(minutes=10) <= expiry <= after + timedelta(minutes=10)

    def test_custom_minutes(self):
        before = timezone.now()
        expiry = get_otp_expiry(minutes=30)
        after = timezone.now()
        assert before + timedelta(minutes=30) <= expiry <= after + timedelta(minutes=30)

    def test_returns_timezone_aware(self):
        expiry = get_otp_expiry()
        assert expiry.tzinfo is not None


# ---------------------------------------------------------------------------
# get_file_extension
# ---------------------------------------------------------------------------


class TestGetFileExtension:
    def test_extracts_jpg(self):
        f = SimpleUploadedFile("photo.jpg", b"data")
        assert get_file_extension(f) == "jpg"

    def test_extracts_png_case_insensitive(self):
        f = SimpleUploadedFile("image.PNG", b"data")
        assert get_file_extension(f) == "png"

    def test_no_extension_returns_empty(self):
        f = SimpleUploadedFile("README", b"data")
        assert get_file_extension(f) == ""

    def test_multiple_dots(self):
        f = SimpleUploadedFile("archive.tar.gz", b"data")
        assert get_file_extension(f) == "gz"

    def test_empty_name(self):
        """File with None name (can happen with programmatic files)."""
        from unittest.mock import MagicMock

        f = MagicMock()
        f.name = None
        assert get_file_extension(f) == ""


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------


class TestSanitizeFilename:
    def test_normal_filename_unchanged(self):
        assert sanitize_filename("photo.jpg") == "photo.jpg"

    def test_strips_path_traversal_forward_slash(self):
        result = sanitize_filename("../../etc/passwd")
        assert "/" not in result
        assert "\\" not in result
        assert ".." not in result

    def test_strips_path_traversal_backslash(self):
        result = sanitize_filename("..\\..\\etc\\passwd")
        assert "\\" not in result

    def test_strips_unsafe_chars(self):
        result = sanitize_filename("file <name>.jpg")
        # Angle brackets are removed
        assert "<" not in result
        assert ">" not in result

    def test_strips_leading_dots(self):
        result = sanitize_filename(".htaccess")
        assert not result.startswith(".")

    def test_collapses_consecutive_dots(self):
        result = sanitize_filename("file...name.jpg")
        assert "..." not in result

    def test_empty_filename_returns_uuid_hex(self):
        result = sanitize_filename("")
        # uuid4().hex is 32 chars
        assert len(result) == 32

    def test_all_unsafe_chars_returns_uuid(self):
        result = sanitize_filename("!@#$%^&*()")
        assert len(result) == 32

    def test_preserves_hyphens_and_underscores(self):
        assert sanitize_filename("my-file_name.txt") == "my-file_name.txt"


# ---------------------------------------------------------------------------
# truncate_text
# ---------------------------------------------------------------------------


class TestTruncateText:
    def test_short_text_unchanged(self):
        text = "Hello"
        assert truncate_text(text, max_length=50) == "Hello"

    def test_exact_length_unchanged(self):
        text = "a" * 50
        assert truncate_text(text, max_length=50) == text

    def test_over_limit_gets_ellipsis(self):
        text = "a" * 60
        result = truncate_text(text, max_length=50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_default_max_length_50(self):
        text = "a" * 100
        result = truncate_text(text)
        assert len(result) == 50
        assert result.endswith("...")

    def test_empty_string(self):
        assert truncate_text("") == ""


# ---------------------------------------------------------------------------
# build_notification_data
# ---------------------------------------------------------------------------


class TestBuildNotificationData:
    def test_basic_data(self):
        data = build_notification_data("follow", user_id="abc")
        assert data == {"type": "follow", "user_id": "abc"}

    def test_skips_none_values(self):
        data = build_notification_data("comment", post_id="123", reply_id=None)
        assert "reply_id" not in data
        assert data["post_id"] == "123"

    def test_type_always_present(self):
        data = build_notification_data("reaction")
        assert data == {"type": "reaction"}

    def test_values_converted_to_string(self):
        import uuid

        uid = uuid.uuid4()
        data = build_notification_data("share", post_id=uid)
        assert data["post_id"] == str(uid)

    def test_multiple_kwargs(self):
        data = build_notification_data(
            "comment", post_id="p1", comment_id="c1", user_id="u1"
        )
        assert data == {
            "type": "comment",
            "post_id": "p1",
            "comment_id": "c1",
            "user_id": "u1",
        }


# ---------------------------------------------------------------------------
# get_blocked_user_ids / invalidate_blocked_user_cache
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetBlockedUserIds:
    def test_returns_set_of_ids(self, user, user2):
        from conftest import BlockRelationshipFactory

        BlockRelationshipFactory(blocker=user, blocked=user2)
        result = get_blocked_user_ids(user.id)
        assert isinstance(result, set)
        assert user2.id in result

    def test_bidirectional(self, user, user2):
        from conftest import BlockRelationshipFactory, UserFactory

        user3 = UserFactory()
        BlockRelationshipFactory(blocker=user, blocked=user2)
        BlockRelationshipFactory(blocker=user3, blocked=user)
        result = get_blocked_user_ids(user.id)
        assert user2.id in result
        assert user3.id in result

    def test_empty_when_no_blocks(self, user):
        result = get_blocked_user_ids(user.id)
        assert result == set()

    def test_uses_cache(self, user, user2):
        from conftest import BlockRelationshipFactory

        BlockRelationshipFactory(blocker=user, blocked=user2)
        # First call populates cache
        result1 = get_blocked_user_ids(user.id)
        # Second call should come from cache
        with patch(
            "apps.accounts.models.BlockRelationship.objects"
        ) as mock_manager:
            result2 = get_blocked_user_ids(user.id)
        # Results should be the same
        assert result1 == result2

    def test_invalidate_cache(self, user, user2):
        from conftest import BlockRelationshipFactory

        BlockRelationshipFactory(blocker=user, blocked=user2)
        get_blocked_user_ids(user.id)
        # Cache should have an entry
        cache_key = f"blocked_user_ids:{user.id}"
        assert cache.get(cache_key) is not None

        invalidate_blocked_user_cache(user.id)
        assert cache.get(cache_key) is None

    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()
