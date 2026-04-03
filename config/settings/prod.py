from .base import *


def _build_csrf_trusted_origins(origins: list[str]) -> list[str]:
    """Return trusted CSRF origins derived from configured frontend origins."""

    trusted = {"https://*.up.railway.app"}

    for origin in origins:
        if origin.startswith(("http://", "https://")):
            trusted.add(origin)

    return sorted(trusted)


DEBUG = False

CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="https://bibleway.io",
    cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
)

CSRF_TRUSTED_ORIGINS = _build_csrf_trusted_origins(CORS_ALLOWED_ORIGINS)

SECURE_SSL_REDIRECT = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_HSTS_SECONDS = 31536000

SECURE_HSTS_INCLUDE_SUBDOMAINS = True

SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True

CSRF_COOKIE_SECURE = True

if REDIS_URL:
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"

    SESSION_CACHE_ALIAS = "default"

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

STORAGES["staticfiles"] = {
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
}
