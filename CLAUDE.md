# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Django REST Framework backend for Bibleway, a Christian social/Bible app with real-time support via Django Channels. Python 3.12, Django 5.1+, PostgreSQL (Neon), Redis (Upstash), deployed via Daphne on Railway.

## Common Commands

```bash
# Install dependencies
pip install -r requirements/dev.txt

# Run development server
python manage.py runserver
# Or with ASGI (channels support):
daphne -b 0.0.0.0 -p 8000 config.asgi:application

# Database
python manage.py makemigrations
python manage.py migrate

# Tests
pytest
pytest apps/accounts/tests/  # single app
pytest -x                    # stop on first failure
pytest --cov                 # with coverage

# Linting
ruff check .
ruff format .

# Celery worker
celery -A config worker --loglevel=info
```

## Architecture

**Settings split**: `config/settings/{base,dev,prod}.py` — selected via `DJANGO_ENV` env var.

**Service layer pattern**: Business logic lives in `apps/*/services.py`, not in views. Each service extends `BaseService[ModelType]` or `BaseUserScopedService` from `apps/common/services.py`.

**API response envelope**: All responses use `{"message": "...", "data": {...}}` format. Views extend `BaseAPIView` or `BaseModelViewSet` from `apps/common/views.py` which provide `success_response()`, `created_response()`, `no_content_response()` helpers. Custom exception handler in `apps/common/exceptions.py` wraps DRF errors into this envelope.

**Apps** (`apps/` directory):
- `accounts` — CustomUser (UUID PK, email-based auth), follow/block, OTP
- `bible` — Age-segregated Bible content, translated page caching, bookmarks
- `social` — Posts, prayers, comments, reactions, reports (uses ContentType for generic relations)
- `shop` — Products, purchases, downloads, Apple/Google IAP validation
- `notifications` — In-app notifications + FCM push via firebase-admin
- `analytics` — Post views, paid boosts, boost snapshots
- `verse_of_day` — Scheduled daily verses with fallback pool
- `admin_panel` — RBAC admin roles, audit logging
- `common` — Shared base classes, permissions, validators, exceptions, utilities

**Auth**: JWT via SimpleJWT (15min access, 30d refresh with rotation). OTP uses HMAC-SHA256 hashed 6-digit codes with `select_for_update()` for race protection. WebSocket auth via JWT in query string (`config/middleware.py`).

**Permissions** (`apps/common/permissions.py`): IsOwner, IsOwnerOrReadOnly, IsNotBlocked. Throttling: AuthRateThrottle (10/min), OTPRateThrottle (5/min).

**Pagination**: `StandardPageNumberPagination` (20/page) for lists, `FeedCursorPagination` for infinite-scroll feeds.

**Media storage**: UploadThing via custom Django Storage backend. Two storage classes: `PublicMediaStorage` and `PrivateMediaStorage` (both public on free plan; download access control enforced at Django API level).

**Background tasks**: Celery with Redis broker. Beat schedule runs `deactivate_expired_boosts` every 5 minutes. Task modules in each app's `tasks.py`.

**URL structure**: All API routes under `/api/v1/` — see `config/urls.py`.

## Key Integrations

Firebase (push), Resend (email), Google Translate (Bible translation), API Bible (verse data), Apple/Google IAP (receipt validation), UploadThing (file storage), Google OAuth (sign-in).

## Environment

Copy `.env.example` to `.env`. Key vars: `DJANGO_ENV`, `DATABASE_URL`, `UPSTASH_REDIS_URL`, `UPLOADTHING_TOKEN`, `UPLOADTHING_APP_ID`, `FIREBASE_CREDENTIALS_JSON`, `RESEND_API_KEY`.
