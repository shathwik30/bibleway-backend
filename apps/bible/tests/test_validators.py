"""Tests for apps.bible.validators — verse reference, YouTube URL, and language code validation."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.bible.validators import (
    validate_language_code,
    validate_verse_reference,
    validate_youtube_url,
)


# ════════════════════════════════════════════════════════════════
# validate_verse_reference
# ════════════════════════════════════════════════════════════════


class TestValidateVerseReference:
    """Tests for validate_verse_reference()."""

    def test_simple_reference_valid(self):
        """A simple 'GEN.1.1' reference passes."""
        validate_verse_reference("GEN.1.1")  # should not raise

    def test_john_three_sixteen_valid(self):
        """'JHN.3.16' is valid."""
        validate_verse_reference("JHN.3.16")

    def test_range_reference_valid(self):
        """A range like 'GEN.1.1-GEN.1.5' is valid."""
        validate_verse_reference("GEN.1.1-GEN.1.5")

    def test_numbered_book_valid(self):
        """Books starting with a number like '1CO.13.4' are valid."""
        validate_verse_reference("1CO.13.4")

    def test_three_digit_chapter_valid(self):
        """Three-digit chapter number like 'PSA.119.105' is valid."""
        validate_verse_reference("PSA.119.105")

    def test_lowercase_rejected(self):
        """Lowercase book codes are rejected."""
        with pytest.raises(ValidationError, match="Invalid verse reference"):
            validate_verse_reference("gen.1.1")

    def test_missing_verse_rejected(self):
        """A reference without a verse number is rejected."""
        with pytest.raises(ValidationError, match="Invalid verse reference"):
            validate_verse_reference("GEN.1")

    def test_extra_segments_rejected(self):
        """Too many dot-segments are rejected."""
        with pytest.raises(ValidationError, match="Invalid verse reference"):
            validate_verse_reference("GEN.1.1.2")

    def test_empty_string_rejected(self):
        """Empty string is rejected."""
        with pytest.raises(ValidationError, match="Invalid verse reference"):
            validate_verse_reference("")

    def test_plain_text_rejected(self):
        """Arbitrary text is rejected."""
        with pytest.raises(ValidationError, match="Invalid verse reference"):
            validate_verse_reference("Genesis chapter 1 verse 1")

    def test_range_with_different_books(self):
        """Range across different books is still valid per the regex."""
        validate_verse_reference("GEN.1.1-EXO.2.3")

    def test_five_letter_book_code_valid(self):
        """Five-character book codes are allowed by the pattern."""
        validate_verse_reference("SONGS.1.1")  # 5 chars


# ════════════════════════════════════════════════════════════════
# validate_youtube_url
# ════════════════════════════════════════════════════════════════


class TestValidateYoutubeUrl:
    """Tests for validate_youtube_url()."""

    def test_empty_string_allowed(self):
        """Empty value is allowed (early return)."""
        validate_youtube_url("")  # should not raise

    def test_standard_watch_url(self):
        """Standard youtube.com/watch?v= URL passes."""
        validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_short_url(self):
        """Short youtu.be URL passes."""
        validate_youtube_url("https://youtu.be/dQw4w9WgXcQ")

    def test_embed_url(self):
        """Embed URL passes."""
        validate_youtube_url("https://www.youtube.com/embed/dQw4w9WgXcQ")

    def test_shorts_url(self):
        """Shorts URL passes."""
        validate_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ")

    def test_http_url(self):
        """HTTP (non-HTTPS) YouTube URL passes."""
        validate_youtube_url("http://youtube.com/watch?v=dQw4w9WgXcQ")

    def test_non_youtube_url_rejected(self):
        """A non-YouTube URL is rejected."""
        with pytest.raises(ValidationError, match="valid YouTube URL"):
            validate_youtube_url("https://vimeo.com/12345")

    def test_invalid_url_format_rejected(self):
        """A non-URL string is rejected by URL validation."""
        with pytest.raises(ValidationError):
            validate_youtube_url("not-a-url-at-all")

    def test_youtube_channel_url_rejected(self):
        """A YouTube channel URL (not a video) is rejected."""
        with pytest.raises(ValidationError, match="valid YouTube URL"):
            validate_youtube_url("https://www.youtube.com/channel/UCxxxxxx")

    def test_without_www(self):
        """URL without www subdomain passes."""
        validate_youtube_url("https://youtube.com/watch?v=dQw4w9WgXcQ")


# ════════════════════════════════════════════════════════════════
# validate_language_code
# ════════════════════════════════════════════════════════════════


class TestValidateLanguageCode:
    """Tests for validate_language_code()."""

    def test_simple_two_letter_valid(self):
        """'en' is a valid language code."""
        validate_language_code("en")

    def test_spanish_valid(self):
        """'es' is valid."""
        validate_language_code("es")

    def test_with_region_valid(self):
        """'fr-FR' (language-Region) is valid."""
        validate_language_code("fr-FR")

    def test_en_us_valid(self):
        """'en-US' is valid."""
        validate_language_code("en-US")

    def test_uppercase_language_rejected(self):
        """Uppercase language part is rejected."""
        with pytest.raises(ValidationError, match="Invalid language code"):
            validate_language_code("EN")

    def test_three_letter_rejected(self):
        """Three-letter codes are rejected (ISO 639-1 is 2-letter)."""
        with pytest.raises(ValidationError, match="Invalid language code"):
            validate_language_code("eng")

    def test_lowercase_region_rejected(self):
        """Lowercase region part is rejected."""
        with pytest.raises(ValidationError, match="Invalid language code"):
            validate_language_code("en-us")

    def test_empty_string_rejected(self):
        """Empty string is rejected."""
        with pytest.raises(ValidationError, match="Invalid language code"):
            validate_language_code("")

    def test_single_letter_rejected(self):
        """Single letter is rejected."""
        with pytest.raises(ValidationError, match="Invalid language code"):
            validate_language_code("e")

    def test_number_rejected(self):
        """Numeric strings are rejected."""
        with pytest.raises(ValidationError, match="Invalid language code"):
            validate_language_code("12")
