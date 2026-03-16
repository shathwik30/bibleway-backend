"""Tests for apps.common.storage_backends — UploadThing storage."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import requests
from django.core.files.base import ContentFile

from apps.common.storage_backends import (
    PrivateMediaStorage,
    PublicMediaStorage,
    UploadThingStorage,
)


@pytest.fixture
def storage(settings):
    settings.UPLOADTHING_TOKEN = "test-token"
    settings.UPLOADTHING_APP_ID = "test-app-id"
    return UploadThingStorage(acl="public-read")


class TestUrl:
    def test_url_returns_cdn_path(self, storage):
        assert storage.url("abc123") == "https://test-app-id.ufs.sh/f/abc123"

    def test_url_empty_name_returns_empty(self, storage):
        assert storage.url("") == ""

    def test_url_preserves_full_key(self, storage):
        result = storage.url("shop/123/files/product.pdf")
        assert result == "https://test-app-id.ufs.sh/f/shop/123/files/product.pdf"


class TestSave:
    def test_save_with_presigned_put(self, storage):
        """_save uploads via PUT when no fields are returned."""
        mock_session = MagicMock()
        mock_session.put.return_value = MagicMock(raise_for_status=MagicMock())

        with patch.object(UploadThingStorage, "session", new_callable=PropertyMock, return_value=mock_session), \
             patch.object(storage, "_api") as mock_api:
            mock_api.return_value = {
                "data": [{"url": "https://upload.example.com/put", "key": "file-key-123", "fields": {}}]
            }
            content = ContentFile(b"hello world", name="test.txt")
            result = storage._save("uploads/test.txt", content)

        assert result == "file-key-123"
        mock_session.put.assert_called_once()

    def test_save_with_multipart_form(self, storage):
        """_save uploads via POST when fields are returned."""
        mock_session = MagicMock()
        mock_session.post.return_value = MagicMock(raise_for_status=MagicMock())

        with patch.object(UploadThingStorage, "session", new_callable=PropertyMock, return_value=mock_session), \
             patch.object(storage, "_api") as mock_api:
            mock_api.return_value = {
                "data": [{"url": "https://upload.example.com/post", "key": "file-key-456", "fields": {"policy": "xyz"}}]
            }
            content = ContentFile(b"pdf content", name="doc.pdf")
            result = storage._save("shop/doc.pdf", content)

        assert result == "file-key-456"
        mock_session.post.assert_called_once()

    def test_save_sends_correct_payload(self, storage):
        """_save sends the correct payload to the presigned upload API."""
        mock_session = MagicMock()
        mock_session.put.return_value = MagicMock(raise_for_status=MagicMock())

        with patch.object(UploadThingStorage, "session", new_callable=PropertyMock, return_value=mock_session), \
             patch.object(storage, "_api") as mock_api:
            mock_api.return_value = {
                "data": [{"url": "https://up.example.com", "key": "k", "fields": {}}]
            }
            content = ContentFile(b"data", name="img.png")
            storage._save("photos/img.png", content)

            call_args = mock_api.call_args
            assert call_args[0][0] == "/v6/uploadFiles"
            payload = call_args[0][1]
            assert payload["acl"] == "public-read"
            assert payload["files"][0]["name"] == "img.png"
            assert payload["files"][0]["size"] == 4
            assert payload["files"][0]["customId"] == "photos/img.png"


class TestDelete:
    def test_delete_calls_api(self, storage):
        with patch.object(storage, "_api") as mock_api:
            storage.delete("file-key-123")
            mock_api.assert_called_once_with("/v6/deleteFiles", {"fileKeys": ["file-key-123"]})

    def test_delete_empty_name_is_noop(self, storage):
        with patch.object(storage, "_api") as mock_api:
            storage.delete("")
            mock_api.assert_not_called()

    def test_delete_http_error_is_swallowed(self, storage):
        with patch.object(storage, "_api") as mock_api:
            mock_api.side_effect = requests.RequestException("Network error")
            storage.delete("file-key-123")  # Should not raise


class TestExists:
    def test_exists_returns_true_on_200(self, storage):
        mock_session = MagicMock()
        mock_session.head.return_value = MagicMock(status_code=200)
        with patch.object(UploadThingStorage, "session", new_callable=PropertyMock, return_value=mock_session):
            assert storage.exists("file-key") is True

    def test_exists_returns_false_on_404(self, storage):
        mock_session = MagicMock()
        mock_session.head.return_value = MagicMock(status_code=404)
        with patch.object(UploadThingStorage, "session", new_callable=PropertyMock, return_value=mock_session):
            assert storage.exists("missing-key") is False

    def test_exists_empty_name_returns_false(self, storage):
        assert storage.exists("") is False

    def test_exists_request_error_returns_false(self, storage):
        mock_session = MagicMock()
        mock_session.head.side_effect = requests.RequestException("timeout")
        with patch.object(UploadThingStorage, "session", new_callable=PropertyMock, return_value=mock_session):
            assert storage.exists("file-key") is False


class TestSize:
    def test_size_returns_file_size(self, storage):
        with patch.object(storage, "_api") as mock_api:
            mock_api.return_value = {"files": [{"size": 12345}]}
            assert storage.size("file-key") == 12345

    def test_size_returns_zero_on_error(self, storage):
        with patch.object(storage, "_api") as mock_api:
            mock_api.side_effect = requests.RequestException("fail")
            assert storage.size("file-key") == 0

    def test_size_returns_zero_when_no_files(self, storage):
        with patch.object(storage, "_api") as mock_api:
            mock_api.return_value = {"files": []}
            assert storage.size("file-key") == 0


class TestOpen:
    def test_open_returns_content_file(self, storage):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b"file content here"
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        with patch.object(UploadThingStorage, "session", new_callable=PropertyMock, return_value=mock_session):
            result = storage._open("file-key")
            assert isinstance(result, ContentFile)
            assert result.read() == b"file content here"


class TestSubclasses:
    def test_public_media_storage_acl(self, settings):
        settings.UPLOADTHING_TOKEN = "test-token"
        s = PublicMediaStorage()
        assert s.acl == "public-read"

    def test_private_media_storage_acl(self, settings):
        settings.UPLOADTHING_TOKEN = "test-token"
        s = PrivateMediaStorage()
        assert s.acl == "public-read"

    def test_custom_acl_override(self):
        s = UploadThingStorage(acl="private")
        assert s.acl == "private"


class TestSession:
    def test_session_is_lazily_created(self, storage):
        s = UploadThingStorage()
        assert s._session is None
        session = s.session
        assert session is not None
        assert s._session is session

    def test_session_is_reused(self, storage):
        s = UploadThingStorage()
        session1 = s.session
        session2 = s.session
        assert session1 is session2

    def test_session_has_auth_header(self, settings):
        settings.UPLOADTHING_TOKEN = "my-secret-token"
        s = UploadThingStorage()
        session = s.session
        assert session.headers.get("x-uploadthing-api-key") == "my-secret-token"
