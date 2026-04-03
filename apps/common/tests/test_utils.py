"""Tests for apps.common.utils — OTP helpers, filename utils, notification data, and block cache."""

from __future__ import annotations
import hashlib
import hmac
from datetime import timedelta
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
        assert len(otps) > 1


class TestHashOtp:
    def test_returns_hex_string(self):
        h = hash_otp("123456")
        assert isinstance(h, str)
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


class TestGetOtpExpiry:
    def test_returns_future_datetime(self):
        expiry = get_otp_expiry()
        assert expiry > timezone.now()

    def test_default_10_minutes(self):
        before = timezone.now()
        expiry = get_otp_expiry()
        after = timezone.now()
        assert before + timedelta(minutes=10) <= expiry <= after + timedelta(minutes=10)

    def test_custom_minutes(self):
        before = timezone.now()
        expiry = get_otp_expiry(minutes=30)
        after = timezone.now()
        assert before + timedelta(minutes=30) <= expiry <= after + timedelta(minutes=30)

    def test_returns_timezone_aware(self):
        expiry = get_otp_expiry()
        assert expiry.tzinfo is not None


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
        assert len(result) == 32

    def test_all_unsafe_chars_returns_uuid(self):
        result = sanitize_filename("!@#$%^&*()")
        assert len(result) == 32

    def test_preserves_hyphens_and_underscores(self):
        assert sanitize_filename("my-file_name.txt") == "my-file_name.txt"


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
        result1 = get_blocked_user_ids(user.id)

        with patch("apps.accounts.models.BlockRelationship.objects"):
            result2 = get_blocked_user_ids(user.id)

        assert result1 == result2

    def test_invalidate_cache(self, user, user2):
        from conftest import BlockRelationshipFactory

        BlockRelationshipFactory(blocker=user, blocked=user2)
        get_blocked_user_ids(user.id)
        cache_key = f"blocked_user_ids:{user.id}"
        assert cache.get(cache_key) is not None
        invalidate_blocked_user_cache(user.id)
        assert cache.get(cache_key) is None

    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()

    def test_uses_cache_timeout_blocked_users_constant(self, user, user2):
        """get_blocked_user_ids should use CACHE_TIMEOUT_BLOCKED_USERS (300s)."""
        from conftest import BlockRelationshipFactory
        from apps.common.constants import CACHE_TIMEOUT_BLOCKED_USERS

        BlockRelationshipFactory(blocker=user, blocked=user2)
        with patch.object(cache, "set", wraps=cache.set) as mock_set:
            get_blocked_user_ids(user.id)
            mock_set.assert_called_once()
            call_kwargs = mock_set.call_args

            timeout_used = call_kwargs[1].get(
                "timeout", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None
            )
            assert timeout_used == CACHE_TIMEOUT_BLOCKED_USERS
            assert timeout_used == 300


@pytest.mark.django_db
class TestSendNotificationSafe:
    """Tests for the send_notification_safe fire-and-forget helper."""

    def test_does_not_raise_on_failure(self, user):
        """send_notification_safe should swallow all exceptions."""
        from apps.common.utils import send_notification_safe

        with patch(
            "apps.notifications.services.NotificationService.create_notification",
            side_effect=Exception("Firebase is down"),
        ):

            send_notification_safe(
                recipient_id=user.id,
                sender_id=None,
                notification_type="follow",
                title="Test",
                body="Test body",
            )

    def test_calls_notification_service_create(self, user, user2):
        """send_notification_safe should call NotificationService.create_notification."""
        from apps.common.utils import send_notification_safe

        with patch(
            "apps.notifications.services.NotificationService.create_notification"
        ) as mock_create:
            send_notification_safe(
                recipient_id=user.id,
                sender_id=user2.id,
                notification_type="comment",
                title="New comment",
                body="Someone commented on your post.",
                data={"post_id": "abc"},
            )
            mock_create.assert_called_once_with(
                recipient_id=user.id,
                sender_id=user2.id,
                notification_type="comment",
                title="New comment",
                body="Someone commented on your post.",
                data={"post_id": "abc"},
            )

    def test_passes_empty_dict_when_data_is_none(self, user):
        """When data=None, send_notification_safe should pass data={}."""
        from apps.common.utils import send_notification_safe

        with patch(
            "apps.notifications.services.NotificationService.create_notification"
        ) as mock_create:
            send_notification_safe(
                recipient_id=user.id,
                notification_type="follow",
                title="Followed",
                body="You have a new follower.",
                data=None,
            )
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["data"] == {}

    def test_logs_warning_on_failure(self, user):
        """send_notification_safe should log a warning when it catches an exception."""
        import logging
        from apps.common.utils import send_notification_safe

        with (
            patch(
                "apps.notifications.services.NotificationService.create_notification",
                side_effect=RuntimeError("boom"),
            ),
            patch.object(
                logging.getLogger("apps.common.utils"), "warning"
            ) as mock_warn,
        ):
            send_notification_safe(
                recipient_id=user.id,
                notification_type="follow",
                title="Test",
                body="Body",
            )
            mock_warn.assert_called_once()
