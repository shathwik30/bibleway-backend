from __future__ import annotations
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from apps.common.validators import validate_image_file, validate_video_file


def validate_media_constraints(
    media_files: list[UploadedFile],
    media_types: list[str],
    *,
    label: str = "content",
) -> None:
    """Validate media constraints for posts and prayers.

    Rules:
      - ``media_files`` and ``media_types`` must be equal-length lists.
      - At most 1 video.
      - Cannot mix video and images.
      - At most 10 images.
      - Images max 10 MB, videos max 100 MB.

    ``label`` is used in error messages (e.g. "post", "prayer").
    """

    if len(media_files) != len(media_types):
        raise ValidationError("media_files and media_types must have the same length.")

    video_count = sum(1 for mt in media_types if mt == "video")

    image_count = sum(1 for mt in media_types if mt == "image")

    if video_count > 1:
        raise ValidationError(f"A {label} can have at most 1 video.")

    if video_count > 0 and image_count > 0:
        raise ValidationError(f"A {label} with a video cannot also have images.")

    if image_count > 10:
        raise ValidationError(f"A {label} can have at most 10 images.")

    for file, media_type in zip(media_files, media_types):
        if media_type == "image":
            validate_image_file(file)

        elif media_type == "video":
            validate_video_file(file)
