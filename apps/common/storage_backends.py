"""S3-compatible storage backends using Railway Object Storage.

Railway provides an S3-compatible bucket.  We use ``django-storages``
with the ``S3Boto3Storage`` backend, pointed at the Railway endpoint.
"""

from django.utils.deconstruct import deconstructible
from storages.backends.s3boto3 import S3Boto3Storage


@deconstructible
class PublicMediaStorage(S3Boto3Storage):
    """For publicly accessible media: profile photos, post images, etc."""

    default_acl = "public-read"
    querystring_auth = False


@deconstructible
class PrivateMediaStorage(S3Boto3Storage):
    """For private files: shop downloads, voice notes.

    Generates time-limited pre-signed URLs so files cannot be accessed
    without going through the Django API (DownloadView checks purchase
    status before returning URLs).
    """

    default_acl = "private"
    querystring_auth = True
    querystring_expire = 3600  # 1 hour
