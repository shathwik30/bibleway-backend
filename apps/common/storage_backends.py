"""S3-compatible storage backends using Railway Object Storage.

Railway provides an S3-compatible bucket (Tigris).  We use ``django-storages``
with the ``S3Boto3Storage`` backend, pointed at the Railway endpoint.

Tigris does not support public bucket ACLs, so all files use pre-signed URLs.
"""

from django.utils.deconstruct import deconstructible
from storages.backends.s3boto3 import S3Boto3Storage


@deconstructible
class PublicMediaStorage(S3Boto3Storage):
    """For publicly accessible media: profile photos, post images, etc.

    Uses long-lived pre-signed URLs (7 days) since Tigris does not
    support public-read ACLs.
    """

    default_acl = None
    querystring_auth = True
    querystring_expire = 604800  # 7 days


@deconstructible
class PrivateMediaStorage(S3Boto3Storage):
    """For private files: shop downloads, voice notes.

    Generates short-lived pre-signed URLs (1 hour) so files cannot be
    accessed without going through the Django API.
    """

    default_acl = None
    querystring_auth = True
    querystring_expire = 3600  # 1 hour
