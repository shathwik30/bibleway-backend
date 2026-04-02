from __future__ import annotations
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

ALLOWED_IMAGE_EXTENSIONS: set[str] = {"jpg", "jpeg", "png", "webp"}

ALLOWED_VIDEO_EXTENSIONS: set[str] = {"mp4", "mov"}

ALLOWED_SHOP_EXTENSIONS: set[str] = {"pdf", "png", "jpg", "zip", "mp3", "mp4"}

ALLOWED_AUDIO_EXTENSIONS: set[str] = {"m4a", "mp3", "ogg", "wav", "aac"}

IMAGE_CONTENT_TYPES: set[str] = {"image/jpeg", "image/png", "image/webp"}

VIDEO_CONTENT_TYPES: set[str] = {"video/mp4", "video/quicktime"}

AUDIO_CONTENT_TYPES: set[str] = {
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
    "audio/wav",
    "audio/aac",
    "audio/x-m4a",
}

_IMAGE_MAGIC: list[tuple[int, bytes]] = [
    (0, b"\xff\xd8\xff"),
    (0, b"\x89PNG\r\n\x1a\n"),
    (0, b"RIFF"),
]

_VIDEO_MAGIC: list[tuple[int, bytes]] = [
    (4, b"ftyp"),
    (0, b"\x00\x00\x00"),
]

_AUDIO_MAGIC: list[tuple[int, bytes]] = [
    (0, b"\xff\xfb"),
    (0, b"\xff\xf3"),
    (0, b"\xff\xf2"),
    (0, b"ID3"),
    (0, b"OggS"),
    (0, b"RIFF"),
    (4, b"ftyp"),
]


def _verify_magic_bytes(
    file: UploadedFile,
    signatures: list[tuple[int, bytes]],
) -> bool:
    """Check that the file header matches at least one known magic signature."""

    try:
        pos = file.tell()
        header = file.read(16)
        file.seek(pos)

    except Exception:
        return False

    if not header:
        return False

    for offset, magic in signatures:
        end = offset + len(magic)

        if len(header) >= end and header[offset:end] == magic:
            return True

    return False


def validate_file_size(file: UploadedFile, max_size_mb: int) -> None:
    """Validate file size against a maximum in megabytes."""

    max_size_bytes: int = max_size_mb * 1024 * 1024

    if file.size > max_size_bytes:
        raise ValidationError(
            f"File size must not exceed {max_size_mb} MB. "
            f"Got {file.size / (1024 * 1024):.1f} MB."
        )


def validate_file_size_10mb(file: UploadedFile) -> None:
    """Validate file size does not exceed 10 MB."""

    validate_file_size(file, max_size_mb=10)


def validate_file_size_100mb(file: UploadedFile) -> None:
    """Validate file size does not exceed 100 MB."""

    validate_file_size(file, max_size_mb=100)


def _get_extension(file: UploadedFile) -> str:
    name = file.name or ""

    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def validate_image_file(file: UploadedFile) -> None:
    """Validate image: extension + magic bytes + content type + size (10 MB)."""

    ext = _get_extension(file)

    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Unsupported image format '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."
        )

    if not _verify_magic_bytes(file, _IMAGE_MAGIC):
        raise ValidationError("File content does not match a valid image format.")

    content_type = getattr(file, "content_type", "")

    if content_type and content_type not in IMAGE_CONTENT_TYPES:
        raise ValidationError(f"Invalid image content type '{content_type}'.")

    validate_file_size(file, max_size_mb=10)


def validate_video_file(file: UploadedFile) -> None:
    """Validate video: extension + magic bytes + content type + size (100 MB)."""

    ext = _get_extension(file)

    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValidationError(
            f"Unsupported video format '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}."
        )

    if not _verify_magic_bytes(file, _VIDEO_MAGIC):
        raise ValidationError("File content does not match a valid video format.")

    content_type = getattr(file, "content_type", "")

    if content_type and content_type not in VIDEO_CONTENT_TYPES:
        raise ValidationError(f"Invalid video content type '{content_type}'.")

    validate_file_size(file, max_size_mb=100)


def validate_voice_note_file(file: UploadedFile) -> None:
    """Validate voice note: extension + magic bytes + content type + size (5 MB)."""

    ext = _get_extension(file)

    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValidationError(
            f"Unsupported audio format '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}."
        )

    if not _verify_magic_bytes(file, _AUDIO_MAGIC):
        raise ValidationError("File content does not match a valid audio format.")

    content_type = getattr(file, "content_type", "")

    if content_type and content_type not in AUDIO_CONTENT_TYPES:
        raise ValidationError(f"Invalid audio content type '{content_type}'.")

    validate_file_size(file, max_size_mb=5)


def validate_image_extension(file: UploadedFile) -> None:
    """Validate that the file has an allowed image extension."""

    ext = _get_extension(file)

    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Unsupported image format '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."
        )


def validate_video_extension(file: UploadedFile) -> None:
    """Validate that the file has an allowed video extension."""

    ext = _get_extension(file)

    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValidationError(
            f"Unsupported video format '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}."
        )


def validate_bio_length(value: str) -> None:
    """Validate that bio does not exceed 250 characters."""

    if len(value) > 250:
        raise ValidationError("Bio must not exceed 250 characters.")
