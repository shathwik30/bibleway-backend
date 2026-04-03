import json as _json
import ssl as _ssl
from datetime import timedelta
from pathlib import Path
import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv()
)

DJANGO_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "channels",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.social",
    "apps.bible",
    "apps.shop",
    "apps.notifications",
    "apps.analytics",
    "apps.verse_of_day",
    "apps.admin_panel",
    "apps.chat",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"

ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        config("DATABASE_URL"),
        conn_max_age=300,
        conn_health_checks=True,
        ssl_require=True,
    )
}

DATABASES["default"]["OPTIONS"] = DATABASES["default"].get("OPTIONS", {})

DATABASES["default"]["OPTIONS"]["connect_timeout"] = 10

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",
        "user": "120/minute",
        "auth": "10/minute",
        "otp": "5/minute",
        "purchase": "10/minute",
        "boost": "10/minute",
        "device_token": "10/minute",
        "feed": "60/minute",
        "social_create": "20/minute",
    },
    "EXCEPTION_HANDLER": "apps.common.exceptions.custom_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

REDIS_URL = config("UPSTASH_REDIS_URL", default="") or config(
    "UPSTASHREDIS_URL", default=""
)

UPSTASH_SSL_OPTS = {}

if REDIS_URL.startswith("rediss://"):
    UPSTASH_SSL_OPTS = {
        "ssl_cert_reqs": _ssl.CERT_NONE,
    }

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [
                    {
                        "address": REDIS_URL,
                        **UPSTASH_SSL_OPTS,
                    }
                ],
            },
        },
    }

else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

CELERY_BROKER_URL = REDIS_URL or "memory://"

CELERY_RESULT_BACKEND = REDIS_URL or "cache+memory://"

CELERY_ACCEPT_CONTENT = ["json"]

CELERY_TASK_SERIALIZER = "json"

CELERY_RESULT_SERIALIZER = "json"

CELERY_TIMEZONE = "UTC"

if UPSTASH_SSL_OPTS:
    CELERY_BROKER_USE_SSL = UPSTASH_SSL_OPTS

    CELERY_REDIS_BACKEND_USE_SSL = UPSTASH_SSL_OPTS

CELERY_TASK_ACKS_LATE = True

CELERY_WORKER_PREFETCH_MULTIPLIER = 1

CELERY_TASK_REJECT_ON_WORKER_LOST = True

CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": 3600,
    "max_retries": 3,
    "interval_start": 0.1,
    "interval_step": 0.2,
    "interval_max": 0.5,
}

CELERY_BEAT_SCHEDULE = {
    "deactivate-expired-boosts": {
        "task": "apps.analytics.tasks.deactivate_expired_boosts",
        "schedule": 300.0,
    },
    "generate-boost-snapshots": {
        "task": "apps.analytics.tasks.generate_boost_snapshots",
        "schedule": 86400.0,
    },
    "archive-old-post-views": {
        "task": "apps.analytics.tasks.archive_old_post_views",
        "schedule": 86400.0,
    },
}

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "bibleway",
            "TIMEOUT": 300,
            "OPTIONS": UPSTASH_SSL_OPTS if UPSTASH_SSL_OPTS else {},
        },
    }

else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
    }

UPLOADTHING_TOKEN = config("UPLOADTHING_TOKEN", default="")

UPLOADTHING_APP_ID = config("UPLOADTHING_APP_ID", default="")

if UPLOADTHING_TOKEN and UPLOADTHING_APP_ID:
    STORAGES = {
        "default": {
            "BACKEND": "apps.common.storage_backends.PublicMediaStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = ""

DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600

FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

API_BIBLE_KEY = config("API_BIBLE_KEY", default="")

RESEND_API_KEY = config("RESEND_API_KEY", default="")

GOOGLE_TRANSLATE_API_KEY = config("GOOGLE_TRANSLATE_API_KEY", default="")

GOOGLE_OAUTH_CLIENT_IDS = [
    cid.strip()
    for cid in config("GOOGLE_OAUTH_CLIENT_IDS", default="").split(",")
    if cid.strip()
]

APPLE_SHARED_SECRET = config("APPLE_SHARED_SECRET", default="")

APPLE_BUNDLE_ID = config("APPLE_BUNDLE_ID", default="com.bibleway.io")

ANDROID_PACKAGE_NAME = config("ANDROID_PACKAGE_NAME", default="com.bibleway.io")


def _parse_json_setting(raw: str) -> dict | None:
    if not raw or not raw.strip().startswith("{"):
        return None

    try:
        return _json.loads(raw)

    except _json.JSONDecodeError:
        return None


GOOGLE_PLAY_CREDENTIALS = _parse_json_setting(
    config("GOOGLE_PLAY_CREDENTIALS_JSON", default="")
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}',
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"level": "WARNING", "propagate": True},
        "apps": {"level": "INFO", "propagate": True},
        "celery": {"level": "INFO", "propagate": True},
    },
}
