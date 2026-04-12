"""Tests for apps.social.serializers — Post, Prayer, Reaction, Comment, Report."""

from __future__ import annotations
import uuid
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.social.models import Reaction, Report
from apps.social.serializers import (
    CommentCreateSerializer,
    PostCreateSerializer,
    PrayerCreateSerializer,
    ReactionCreateSerializer,
    ReportCreateSerializer,
    ReplyCreateSerializer,
)

_JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 12

_MP4_HEADER = b"\x00\x00\x00\x1c" + b"ftyp" + b"\x00" * 8


def _make_image(name: str = "photo.jpg", size: int = 1024) -> SimpleUploadedFile:
    """Create a minimal fake JPEG UploadedFile with valid magic bytes."""

    content = _JPEG_HEADER + b"\x00" * max(0, size - len(_JPEG_HEADER))

    return SimpleUploadedFile(name, content, content_type="image/jpeg")


def _make_video(name: str = "clip.mp4", size: int = 2048) -> SimpleUploadedFile:
    """Create a minimal fake MP4 UploadedFile with valid magic bytes."""

    content = _MP4_HEADER + b"\x00" * max(0, size - len(_MP4_HEADER))

    return SimpleUploadedFile(name, content, content_type="video/mp4")


class TestPostCreateSerializer:
    """Tests for PostCreateSerializer.validate()."""

    def test_text_only_post_valid(self):
        """A post with only text content is valid."""
        data = {"text_content": "Hello world"}
        serializer = PostCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_empty_post_rejected(self):
        """A post with no text and no media is rejected."""
        data = {"text_content": "", "media_files": [], "media_types": []}
        serializer = PostCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_mismatched_media_files_and_types(self):
        """Different lengths for media_files and media_types fails."""
        data = {
            "text_content": "Hello",
            "media_files": [_make_image()],
            "media_types": [],
        }
        serializer = PostCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_more_than_one_video_rejected(self):
        """More than 1 video in a post is rejected."""
        data = {
            "text_content": "",
            "media_files": [_make_video("v1.mp4"), _make_video("v2.mp4")],
            "media_types": ["video", "video"],
        }
        serializer = PostCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_video_with_images_rejected(self):
        """A video mixed with images in a post is rejected."""
        data = {
            "text_content": "",
            "media_files": [_make_video(), _make_image()],
            "media_types": ["video", "image"],
        }
        serializer = PostCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_more_than_10_images_rejected(self):
        """More than 10 images in a post is rejected."""
        data = {
            "text_content": "",
            "media_files": [_make_image(f"img{i}.jpg") for i in range(11)],
            "media_types": ["image"] * 11,
        }
        serializer = PostCreateSerializer(data=data)
        assert not serializer.is_valid()
        errors = serializer.errors
        assert "non_field_errors" in errors or "media_files" in errors

    @patch("apps.social.mixins.validate_image_file")
    def test_single_image_valid(self, mock_validate):
        """A single image post passes validation."""
        data = {
            "text_content": "",
            "media_files": [_make_image()],
            "media_types": ["image"],
        }
        serializer = PostCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        mock_validate.assert_called_once()

    @patch("apps.social.mixins.validate_video_file")
    def test_single_video_valid(self, mock_validate):
        """A single video post passes validation."""
        data = {
            "text_content": "",
            "media_files": [_make_video()],
            "media_types": ["video"],
        }
        serializer = PostCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        mock_validate.assert_called_once()

    def test_invalid_media_type_choice(self):
        """An invalid media type choice is rejected by ChoiceField."""
        data = {
            "text_content": "Hello",
            "media_files": [_make_image()],
            "media_types": ["audio"],
        }
        serializer = PostCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "media_types" in serializer.errors

    @patch("apps.social.mixins.validate_image_file")
    def test_text_with_images_valid(self, mock_validate):
        """A post with both text and images is valid."""
        data = {
            "text_content": "Check out these photos!",
            "media_files": [_make_image("a.jpg"), _make_image("b.jpg")],
            "media_types": ["image", "image"],
        }
        serializer = PostCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert mock_validate.call_count == 2


class TestPrayerCreateSerializer:
    """Tests for PrayerCreateSerializer.validate()."""

    def test_title_only_valid(self):
        """A prayer with only a title is valid."""
        data = {"title": "Please pray for me"}
        serializer = PrayerCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_missing_title_rejected(self):
        """A prayer without a title is rejected."""
        data = {"description": "Need prayer"}
        serializer = PrayerCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "title" in serializer.errors

    def test_mismatched_media_rejected(self):
        """Mismatched media_files and media_types rejected."""
        data = {
            "title": "Prayer",
            "media_files": [_make_image()],
            "media_types": [],
        }
        serializer = PrayerCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_more_than_one_video_rejected(self):
        """More than 1 video in a prayer is rejected."""
        data = {
            "title": "Prayer",
            "media_files": [_make_video("v1.mp4"), _make_video("v2.mp4")],
            "media_types": ["video", "video"],
        }
        serializer = PrayerCreateSerializer(data=data)
        assert not serializer.is_valid()

    def test_video_and_images_rejected(self):
        """Mixing video and images in a prayer is rejected."""
        data = {
            "title": "Prayer",
            "media_files": [_make_video(), _make_image()],
            "media_types": ["video", "image"],
        }
        serializer = PrayerCreateSerializer(data=data)
        assert not serializer.is_valid()

    def test_more_than_10_images_rejected(self):
        """More than 10 images in a prayer is rejected."""
        data = {
            "title": "Prayer",
            "media_files": [_make_image(f"img{i}.jpg") for i in range(11)],
            "media_types": ["image"] * 11,
        }
        serializer = PrayerCreateSerializer(data=data)
        assert not serializer.is_valid()

    @patch("apps.social.mixins.validate_image_file")
    def test_prayer_with_images_valid(self, mock_validate):
        """A prayer with images passes validation."""
        data = {
            "title": "Pray for this",
            "media_files": [_make_image()],
            "media_types": ["image"],
        }
        serializer = PrayerCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_title_with_description_valid(self):
        """A prayer with title and description is valid."""
        data = {
            "title": "Healing prayer",
            "description": "Please pray for my grandmother's recovery.",
        }
        serializer = PrayerCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors


class TestReactionCreateSerializer:
    """Tests for ReactionCreateSerializer."""

    def test_valid_reaction(self):
        """Valid reaction data passes."""
        data = {
            "emoji_type": "heart",
            "content_type_model": "post",
            "object_id": str(uuid.uuid4()),
        }
        serializer = ReactionCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_all_emoji_types_accepted(self):
        """All EmojiType choices are accepted."""

        for choice_value, _ in Reaction.EmojiType.choices:
            data = {
                "emoji_type": choice_value,
                "content_type_model": "prayer",
                "object_id": str(uuid.uuid4()),
            }
            serializer = ReactionCreateSerializer(data=data)
            assert (
                serializer.is_valid()
            ), f"Failed for emoji_type={choice_value}: {serializer.errors}"

    def test_invalid_emoji_type_rejected(self):
        """An unknown emoji type is rejected."""
        data = {
            "emoji_type": "thumbsup",
            "content_type_model": "post",
            "object_id": str(uuid.uuid4()),
        }
        serializer = ReactionCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "emoji_type" in serializer.errors

    def test_invalid_content_type_model_rejected(self):
        """A content_type_model not in choices is rejected."""
        data = {
            "emoji_type": "heart",
            "content_type_model": "comment",
            "object_id": str(uuid.uuid4()),
        }
        serializer = ReactionCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "content_type_model" in serializer.errors

    def test_missing_object_id_rejected(self):
        """Missing object_id fails validation."""
        data = {
            "emoji_type": "heart",
            "content_type_model": "post",
        }
        serializer = ReactionCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "object_id" in serializer.errors

    def test_invalid_uuid_rejected(self):
        """Non-UUID object_id fails."""
        data = {
            "emoji_type": "heart",
            "content_type_model": "post",
            "object_id": "not-a-uuid",
        }
        serializer = ReactionCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "object_id" in serializer.errors


class TestCommentCreateSerializer:
    """Tests for CommentCreateSerializer."""

    def test_valid_comment(self):
        """Valid comment data passes."""
        data = {
            "text": "Great post!",
            "content_type_model": "post",
            "object_id": str(uuid.uuid4()),
        }
        serializer = CommentCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_prayer_comment_valid(self):
        """Commenting on a prayer is valid."""
        data = {
            "text": "Praying for you.",
            "content_type_model": "prayer",
            "object_id": str(uuid.uuid4()),
        }
        serializer = CommentCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_missing_text_rejected(self):
        """Missing text fails."""
        data = {
            "content_type_model": "post",
            "object_id": str(uuid.uuid4()),
        }
        serializer = CommentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "text" in serializer.errors

    def test_empty_text_rejected(self):
        """Empty text fails."""
        data = {
            "text": "",
            "content_type_model": "post",
            "object_id": str(uuid.uuid4()),
        }
        serializer = CommentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "text" in serializer.errors

    def test_invalid_content_type_model_rejected(self):
        """Invalid content_type_model fails."""
        data = {
            "text": "comment",
            "content_type_model": "user",
            "object_id": str(uuid.uuid4()),
        }
        serializer = CommentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "content_type_model" in serializer.errors

    def test_text_max_length(self):
        """Text exceeding 1000 characters is rejected."""
        data = {
            "text": "x" * 1001,
            "content_type_model": "post",
            "object_id": str(uuid.uuid4()),
        }
        serializer = CommentCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "text" in serializer.errors


class TestReplyCreateSerializer:
    """Tests for ReplyCreateSerializer."""

    def test_valid_reply(self):
        """Valid reply data passes."""
        serializer = ReplyCreateSerializer(data={"text": "I agree!"})
        assert serializer.is_valid(), serializer.errors

    def test_missing_text_rejected(self):
        """Missing text fails."""
        serializer = ReplyCreateSerializer(data={})
        assert not serializer.is_valid()
        assert "text" in serializer.errors

    def test_text_max_length(self):
        """Reply text exceeding 1000 characters is rejected."""
        serializer = ReplyCreateSerializer(data={"text": "y" * 1001})
        assert not serializer.is_valid()
        assert "text" in serializer.errors


class TestReportCreateSerializer:
    """Tests for ReportCreateSerializer."""

    def test_valid_report(self):
        """Valid report data passes."""
        data = {
            "reason": "spam",
            "content_type_model": "post",
            "object_id": str(uuid.uuid4()),
        }
        serializer = ReportCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_all_reason_choices_accepted(self):
        """All Report.Reason choices are accepted."""

        for choice_value, _ in Report.Reason.choices:
            data = {
                "reason": choice_value,
                "content_type_model": "post",
                "object_id": str(uuid.uuid4()),
            }
            serializer = ReportCreateSerializer(data=data)
            assert (
                serializer.is_valid()
            ), f"Failed for reason={choice_value}: {serializer.errors}"

    def test_all_content_type_models_accepted(self):
        """All allowed content_type_model values are accepted."""

        for model_value in ["post", "prayer", "comment", "user"]:
            data = {
                "reason": "spam",
                "content_type_model": model_value,
                "object_id": str(uuid.uuid4()),
            }
            serializer = ReportCreateSerializer(data=data)
            assert (
                serializer.is_valid()
            ), f"Failed for model={model_value}: {serializer.errors}"

    def test_invalid_reason_rejected(self):
        """Invalid reason is rejected."""
        data = {
            "reason": "boring",
            "content_type_model": "post",
            "object_id": str(uuid.uuid4()),
        }
        serializer = ReportCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "reason" in serializer.errors

    def test_description_optional(self):
        """Description is optional."""
        data = {
            "reason": "other",
            "content_type_model": "post",
            "object_id": str(uuid.uuid4()),
        }
        serializer = ReportCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_description_accepted(self):
        """Description with text is accepted."""
        data = {
            "reason": "other",
            "description": "This post contains harmful content.",
            "content_type_model": "user",
            "object_id": str(uuid.uuid4()),
        }
        serializer = ReportCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_missing_reason_rejected(self):
        """Missing reason fails."""
        data = {
            "content_type_model": "post",
            "object_id": str(uuid.uuid4()),
        }
        serializer = ReportCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "reason" in serializer.errors

    def test_missing_object_id_rejected(self):
        """Missing object_id fails."""
        data = {
            "reason": "spam",
            "content_type_model": "post",
        }
        serializer = ReportCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "object_id" in serializer.errors
