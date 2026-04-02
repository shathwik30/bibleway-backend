"""Tests for apps.social.validators — media constraint validation."""

from __future__ import annotations
from unittest.mock import patch
import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.social.validators import validate_media_constraints


def _make_file(name: str = "test.jpg", size: int = 1024) -> SimpleUploadedFile:
    """Create a minimal SimpleUploadedFile for testing."""

    return SimpleUploadedFile(
        name, b"\x00" * size, content_type="application/octet-stream"
    )


class TestValidateMediaConstraints:
    """Tests for validate_media_constraints()."""

    @patch("apps.social.validators.validate_image_file")
    def test_equal_length_files_and_types_images(self, mock_validate_image):
        """Matching-length lists with valid images pass validation."""
        files = [_make_file("img1.jpg"), _make_file("img2.jpg")]
        types = ["image", "image"]
        validate_media_constraints(files, types)
        assert mock_validate_image.call_count == 2

    @patch("apps.social.validators.validate_video_file")
    def test_single_video_valid(self, mock_validate_video):
        """A single video file passes validation."""
        files = [_make_file("video.mp4")]
        types = ["video"]
        validate_media_constraints(files, types)
        mock_validate_video.assert_called_once()

    def test_mismatched_lengths_raises(self):
        """Different-length media_files and media_types raises ValidationError."""
        files = [_make_file("img.jpg"), _make_file("img2.jpg")]
        types = ["image"]

        with pytest.raises(ValidationError, match="same length"):
            validate_media_constraints(files, types)

    def test_more_than_one_video_raises(self):
        """More than 1 video raises ValidationError."""
        files = [_make_file("vid1.mp4"), _make_file("vid2.mp4")]
        types = ["video", "video"]

        with pytest.raises(ValidationError, match="at most 1 video"):
            validate_media_constraints(files, types)

    def test_mixed_video_and_images_raises(self):
        """A mix of video and images raises ValidationError."""
        files = [_make_file("vid.mp4"), _make_file("img.jpg")]
        types = ["video", "image"]

        with pytest.raises(ValidationError, match="cannot also have images"):
            validate_media_constraints(files, types)

    def test_more_than_10_images_raises(self):
        """More than 10 images raises ValidationError."""
        files = [_make_file(f"img{i}.jpg") for i in range(11)]
        types = ["image"] * 11

        with pytest.raises(ValidationError, match="at most 10 images"):
            validate_media_constraints(files, types)

    @patch("apps.social.validators.validate_image_file")
    def test_exactly_10_images_valid(self, mock_validate_image):
        """Exactly 10 images should pass validation."""
        files = [_make_file(f"img{i}.jpg") for i in range(10)]
        types = ["image"] * 10
        validate_media_constraints(files, types)
        assert mock_validate_image.call_count == 10

    def test_empty_lists_valid(self):
        """Empty file and type lists pass (no media)."""
        validate_media_constraints([], [])

    def test_custom_label_in_error_message(self):
        """The label kwarg appears in error messages."""
        files = [_make_file("v1.mp4"), _make_file("v2.mp4")]
        types = ["video", "video"]

        with pytest.raises(ValidationError, match="prayer can have at most 1 video"):
            validate_media_constraints(files, types, label="prayer")

    @patch("apps.social.validators.validate_image_file")
    @patch("apps.social.validators.validate_video_file")
    def test_per_file_validators_called(self, mock_validate_video, mock_validate_image):
        """validate_image_file and validate_video_file are called for their types."""
        image_file = _make_file("photo.png")
        video_file = _make_file("clip.mp4")
        validate_media_constraints([image_file], ["image"])
        mock_validate_image.assert_called_once_with(image_file)
        validate_media_constraints([video_file], ["video"])
        mock_validate_video.assert_called_once_with(video_file)

    @patch("apps.social.validators.validate_image_file")
    def test_image_validator_error_propagates(self, mock_validate_image):
        """A ValidationError from validate_image_file propagates up."""
        mock_validate_image.side_effect = ValidationError("Bad image")
        files = [_make_file("bad.jpg")]
        types = ["image"]

        with pytest.raises(ValidationError, match="Bad image"):
            validate_media_constraints(files, types)

    def test_mismatched_more_types_than_files(self):
        """More types than files raises ValidationError."""
        files = [_make_file("img.jpg")]
        types = ["image", "image", "image"]

        with pytest.raises(ValidationError, match="same length"):
            validate_media_constraints(files, types)
