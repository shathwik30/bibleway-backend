import io
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


@deconstructible
class UploadThingStorage(Storage):
    """Django Storage backend that uses UploadThing's REST API.

    Stores files via UploadThing and serves them from their CDN.
    Uses `customId` set to the Django file name so lookups work by name.
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
            self._session.headers.update(
                {
                    "x-uploadthing-api-key": settings.UPLOADTHING_TOKEN,
                }
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

        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"

        # Step 1: Request a presigned upload URL
        payload = {
            "files": [
                {
                    "name": name.split("/")[-1],
                    "size": file_size,
                    "type": content_type,
                    "customId": name,
                }
            ],
            "acl": self.acl,
            "contentDisposition": "inline",
        }

        result = self._api("/v6/uploadFiles", payload)
        upload_data = result["data"][0]
        presigned_url = upload_data["url"]
        file_key = upload_data["key"]
        fields = upload_data.get("fields", {})

        # Step 2: Upload the file
        if fields:
            # Multipart form upload
            form_data = {k: (None, v) for k, v in fields.items()}
            form_data["file"] = (name.split("/")[-1], io.BytesIO(file_bytes), content_type)
            upload_resp = self.session.post(presigned_url, files=form_data)
        else:
            # Direct PUT upload
            upload_resp = self.session.put(
                presigned_url,
                data=file_bytes,
                headers={"Content-Type": content_type},
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
            self._api("/v6/deleteFiles", {"fileKeys": [name]})
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
                "/v6/listFiles",
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
