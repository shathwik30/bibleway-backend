import base64
import io
import json
import logging
import mimetypes

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def _extract_api_key(token: str) -> str:
    """Extract the raw API key from an UploadThing token.

    UploadThing tokens can be either:
    - A raw API key starting with ``sk_``
    - A JWT whose payload contains ``{"apiKey": "sk_..."}``
    """
    if token.startswith("sk_"):
        return token
    try:
        payload_b64 = token.split(".")[0]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("apiKey", token)
    except (json.JSONDecodeError, KeyError, IndexError, ValueError):
        logger.warning("Could not parse UploadThing token as JWT, using raw value")
        return token


@deconstructible
class UploadThingStorage(Storage):
    """Django Storage backend that uses UploadThing's v7 REST API.

    Flow per file:
      1. POST /v7/prepareUpload  →  get presigned URL + file key
      2. PUT file bytes to the presigned URL
    """

    API_BASE = "https://api.uploadthing.com"
    acl = "public-read"

    def __init__(self, acl=None):
        if acl is not None:
            self.acl = acl
        self._session = None

    @property
    def session(self):
        if self._session is None:
            self._session = requests.Session()
            retry = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry)
            self._session.mount("https://", adapter)
            api_key = _extract_api_key(settings.UPLOADTHING_TOKEN)
            self._session.headers.update(
                {"x-uploadthing-api-key": api_key}
            )
        return self._session

    @property
    def _cdn_base(self):
        return f"https://{settings.UPLOADTHING_APP_ID}.ufs.sh/f"

    def _api(self, endpoint, json_data):
        """POST to an UploadThing API endpoint and return parsed JSON."""
        resp = self.session.post(
            f"{self.API_BASE}{endpoint}",
            json=json_data,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()

    # ── Django Storage interface ─────────────────────────────────

    def _save(self, name, content):
        content.seek(0)
        file_bytes = content.read()
        file_size = len(file_bytes)
        file_name = name.split("/")[-1]
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"

        # Step 1: Prepare the upload (v7 API — one file at a time)
        prepare_result = self._api("/v7/prepareUpload", {
            "fileName": file_name,
            "fileSize": file_size,
            "fileType": content_type,
            "contentDisposition": "inline",
            "acl": self.acl,
        })

        presigned_url = prepare_result["url"]
        file_key = prepare_result["key"]

        # Step 2: PUT the file as multipart form data to the presigned
        # ingest URL. Use a plain request (not self.session) because
        # the ingest server rejects the x-uploadthing-api-key header.
        upload_resp = requests.put(
            presigned_url,
            files={"file": (file_name, io.BytesIO(file_bytes), content_type)},
            timeout=120,
        )
        upload_resp.raise_for_status()

        logger.info("Uploaded file to UploadThing: %s -> %s", name, file_key)
        return file_key

    def url(self, name):
        if not name:
            return ""
        return f"{self._cdn_base}/{name}"

    def delete(self, name):
        if not name:
            return
        try:
            self._api("/v7/deleteFiles", {"fileKeys": [name]})
            logger.info("Deleted file from UploadThing: %s", name)
        except requests.RequestException:
            logger.exception("Failed to delete file from UploadThing: %s", name)

    def exists(self, name):
        if not name:
            return False
        try:
            resp = self.session.head(self.url(name), allow_redirects=True)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def size(self, name):
        try:
            result = self._api(
                "/v7/listFiles",
                {"fileKeys": [name]},
            )
            files = result.get("files", [])
            if files:
                return files[0].get("size", 0)
        except requests.RequestException:
            logger.exception("Failed to get size for file: %s", name)
        return 0

    def _open(self, name, mode="rb"):
        resp = self.session.get(self.url(name))
        resp.raise_for_status()
        return ContentFile(resp.content, name=name)


@deconstructible
class PublicMediaStorage(UploadThingStorage):
    """For publicly accessible media: profile photos, post images, etc."""

    def __init__(self):
        super().__init__(acl="public-read")


@deconstructible
class PrivateMediaStorage(UploadThingStorage):
    """For private files: shop assets, voice notes.

    On the free UploadThing plan all files are public. Download access
    control is enforced at the Django API level (DownloadView checks
    purchase status before returning URLs). Upgrade to a paid plan and
    change the acl here to enable server-side private files.
    """

    def __init__(self):
        super().__init__(acl="public-read")
