"""Tests for apps.common.validators — file validation (size, extension, magic bytes, content type)."""

from __future__ import annotations
from io import BytesIO
from unittest.mock import MagicMock
import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.common.validators import (
    _verify_magic_bytes,
    _IMAGE_MAGIC,
    _VIDEO_MAGIC,
    _AUDIO_MAGIC,
    validate_bio_length,
    validate_file_size,
    validate_image_file,
    validate_video_file,
    validate_voice_note_file,
)


def _make_file(
    name: str,
    magic_bytes: bytes,
    size: int | None = None,
    content_type: str = "",
) -> SimpleUploadedFile:
    """Create a SimpleUploadedFile with specific magic bytes in the header."""

    content = magic_bytes + b"\x00" * max(0, 16 - len(magic_bytes))

    if size is not None:
        if len(content) < size:
            content = content + b"\x00" * (size - len(content))

        else:
            content = content[:size]

    f = SimpleUploadedFile(name, content, content_type=content_type)

    return f


JPEG_MAGIC = b"\xff\xd8\xff\xe0"

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

WEBP_MAGIC = b"RIFF\x00\x00\x00\x00WEBP"

MP4_MAGIC = b"\x00\x00\x00\x1cftypisom"

MOV_MAGIC = b"\x00\x00\x00\x14ftypqt  "

MP3_MAGIC = b"ID3\x04\x00\x00\x00\x00\x00\x00"

OGG_MAGIC = b"OggS\x00\x02\x00\x00"

WAV_MAGIC = b"RIFF\x00\x00\x00\x00WAVE"


class TestValidateFileSize:
    def test_under_limit_passes(self):
        f = _make_file("file.bin", b"\x00", size=1024)
        validate_file_size(f, max_size_mb=1)

    def test_over_limit_raises(self):
        f = _make_file("file.bin", b"\x00", size=2 * 1024 * 1024 + 1)

        with pytest.raises(ValidationError, match="must not exceed 1 MB"):
            validate_file_size(f, max_size_mb=1)

    def test_exact_limit_passes(self):
        exact_size = 5 * 1024 * 1024
        f = _make_file("file.bin", b"\x00", size=exact_size)
        validate_file_size(f, max_size_mb=5)


class TestValidateImageFile:
    def test_valid_jpeg(self):
        f = _make_file("photo.jpg", JPEG_MAGIC, content_type="image/jpeg")
        validate_image_file(f)

    def test_valid_png(self):
        f = _make_file("image.png", PNG_MAGIC, content_type="image/png")
        validate_image_file(f)

    def test_valid_webp(self):
        f = _make_file("image.webp", WEBP_MAGIC, content_type="image/webp")
        validate_image_file(f)

    def test_bad_extension_raises(self):
        f = _make_file("image.bmp", JPEG_MAGIC, content_type="image/jpeg")

        with pytest.raises(ValidationError, match="Unsupported image format"):
            validate_image_file(f)

    def test_bad_magic_bytes_raises(self):
        f = _make_file("image.jpg", b"\x00\x00\x00\x00", content_type="image/jpeg")

        with pytest.raises(ValidationError, match="does not match a valid image"):
            validate_image_file(f)

    def test_bad_content_type_raises(self):
        f = _make_file("photo.jpg", JPEG_MAGIC, content_type="application/pdf")

        with pytest.raises(ValidationError, match="Invalid image content type"):
            validate_image_file(f)

    def test_oversized_image_raises(self):
        f = _make_file(
            "photo.jpg", JPEG_MAGIC, size=11 * 1024 * 1024, content_type="image/jpeg"
        )

        with pytest.raises(ValidationError, match="must not exceed 10 MB"):
            validate_image_file(f)

    def test_no_content_type_still_passes(self):
        """When content_type is empty, only extension and magic are checked."""
        f = _make_file("photo.jpg", JPEG_MAGIC, content_type="")
        validate_image_file(f)


class TestValidateVideoFile:
    def test_valid_mp4(self):
        f = _make_file("clip.mp4", MP4_MAGIC, content_type="video/mp4")
        validate_video_file(f)

    def test_valid_mov(self):
        f = _make_file("clip.mov", MOV_MAGIC, content_type="video/quicktime")
        validate_video_file(f)

    def test_bad_extension_raises(self):
        f = _make_file("clip.avi", MP4_MAGIC, content_type="video/mp4")

        with pytest.raises(ValidationError, match="Unsupported video format"):
            validate_video_file(f)

    def test_bad_magic_raises(self):
        f = _make_file(
            "clip.mp4", b"\xff\xff\xff\xff\xff\xff", content_type="video/mp4"
        )

        with pytest.raises(ValidationError, match="does not match a valid video"):
            validate_video_file(f)

    def test_bad_content_type_raises(self):
        f = _make_file("clip.mp4", MP4_MAGIC, content_type="video/avi")

        with pytest.raises(ValidationError, match="Invalid video content type"):
            validate_video_file(f)

    def test_oversized_video_raises(self):
        f = _make_file(
            "clip.mp4", MP4_MAGIC, size=101 * 1024 * 1024, content_type="video/mp4"
        )

        with pytest.raises(ValidationError, match="must not exceed 100 MB"):
            validate_video_file(f)


class TestValidateVoiceNoteFile:
    def test_valid_mp3(self):
        f = _make_file("note.mp3", MP3_MAGIC, content_type="audio/mpeg")
        validate_voice_note_file(f)

    def test_valid_ogg(self):
        f = _make_file("note.ogg", OGG_MAGIC, content_type="audio/ogg")
        validate_voice_note_file(f)

    def test_valid_wav(self):
        f = _make_file("note.wav", WAV_MAGIC, content_type="audio/wav")
        validate_voice_note_file(f)

    def test_valid_m4a(self):
        f = _make_file("note.m4a", MP4_MAGIC, content_type="audio/x-m4a")
        validate_voice_note_file(f)

    def test_bad_extension_raises(self):
        f = _make_file("note.flac", MP3_MAGIC, content_type="audio/mpeg")

        with pytest.raises(ValidationError, match="Unsupported audio format"):
            validate_voice_note_file(f)

    def test_over_5mb_raises(self):
        f = _make_file(
            "note.mp3", MP3_MAGIC, size=6 * 1024 * 1024, content_type="audio/mpeg"
        )

        with pytest.raises(ValidationError, match="must not exceed 5 MB"):
            validate_voice_note_file(f)

    def test_bad_magic_raises(self):
        f = _make_file("note.mp3", b"\x00\x00\x00\x00", content_type="audio/mpeg")

        with pytest.raises(ValidationError, match="does not match a valid audio"):
            validate_voice_note_file(f)

    def test_bad_content_type_raises(self):
        f = _make_file("note.mp3", MP3_MAGIC, content_type="video/mp4")

        with pytest.raises(ValidationError, match="Invalid audio content type"):
            validate_voice_note_file(f)


class TestValidateBioLength:
    def test_under_250_passes(self):
        validate_bio_length("A short bio")

    def test_exactly_250_passes(self):
        validate_bio_length("x" * 250)

    def test_over_250_raises(self):
        with pytest.raises(ValidationError, match="must not exceed 250"):
            validate_bio_length("x" * 251)

    def test_empty_passes(self):
        validate_bio_length("")


class TestVerifyMagicBytes:
    def test_matching_jpeg_magic(self):
        content = JPEG_MAGIC + b"\x00" * 12
        f = BytesIO(content)
        f.name = "test.jpg"
        assert _verify_magic_bytes(f, _IMAGE_MAGIC) is True

    def test_matching_png_magic(self):
        content = PNG_MAGIC + b"\x00" * 8
        f = BytesIO(content)
        f.name = "test.png"
        assert _verify_magic_bytes(f, _IMAGE_MAGIC) is True

    def test_no_match_returns_false(self):
        content = b"\x00" * 16
        f = BytesIO(content)
        assert _verify_magic_bytes(f, _IMAGE_MAGIC) is False

    def test_empty_file_returns_false(self):
        f = BytesIO(b"")
        assert _verify_magic_bytes(f, _IMAGE_MAGIC) is False

    def test_file_position_restored(self):
        content = JPEG_MAGIC + b"\x00" * 12
        f = BytesIO(content)
        f.seek(0)
        _verify_magic_bytes(f, _IMAGE_MAGIC)
        assert f.tell() == 0

    def test_broken_file_returns_false(self):
        """A file whose read() raises an exception should return False."""
        mock_file = MagicMock()
        mock_file.tell.side_effect = IOError("broken")
        assert _verify_magic_bytes(mock_file, _IMAGE_MAGIC) is False

    def test_offset_based_magic(self):
        """MP4/MOV magic is at offset 4 (b'ftyp')."""
        content = MP4_MAGIC + b"\x00" * 4
        f = BytesIO(content)
        assert _verify_magic_bytes(f, _VIDEO_MAGIC) is True

    def test_audio_id3_magic(self):
        content = MP3_MAGIC + b"\x00" * 6
        f = BytesIO(content)
        assert _verify_magic_bytes(f, _AUDIO_MAGIC) is True
