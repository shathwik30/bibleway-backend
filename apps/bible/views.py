from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import requests
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.exceptions import BadRequestError
from apps.common.pagination import StandardPageNumberPagination
from apps.common.permissions import IsOwner
from apps.common.views import BaseAPIView, BaseModelViewSet

from .models import Bookmark, Highlight, Note
from .serializers import (
    BookmarkCreateSerializer,
    BookmarkSerializer,
    HighlightCreateSerializer,
    HighlightSerializer,
    NoteCreateSerializer,
    NoteSerializer,
    NoteUpdateSerializer,
    SegregatedChapterListSerializer,
    SegregatedPageDetailSerializer,
    SegregatedPageListSerializer,
    SegregatedSectionListSerializer,
    TranslatedPageSerializer,
)
from .services import (
    BibleTranslationService,
    BookmarkService,
    HighlightService,
    NoteService,
    SegregatedBibleService,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Segregated Bible content views
# ---------------------------------------------------------------------------


class SegregatedSectionListView(BaseAPIView):
    """GET /bible/sections/

    Returns active sections, optionally prioritized by the authenticated
    user's age.
    """

    def get(self, request: Request) -> Response:
        service = SegregatedBibleService()

        user_age: int | None = None
        if hasattr(request.user, "age"):
            user_age = request.user.age

        sections = service.get_sections(user_age=user_age)
        serializer = SegregatedSectionListSerializer(sections, many=True)
        return self.success_response(data=serializer.data)


class ChapterListView(BaseAPIView):
    """GET /bible/sections/<section_id>/chapters/

    Returns active chapters for a section.
    """

    def get(self, request: Request, section_id: UUID) -> Response:
        service = SegregatedBibleService()
        chapters = service.get_chapters_for_section(section_id)
        serializer = SegregatedChapterListSerializer(chapters, many=True)
        return self.success_response(data=serializer.data)


class PageListView(BaseAPIView):
    """GET /bible/chapters/<chapter_id>/pages/

    Returns active pages (without full content) for a chapter.
    """

    def get(self, request: Request, chapter_id: UUID) -> Response:
        service = SegregatedBibleService()
        pages = service.get_pages_for_chapter(chapter_id)
        serializer = SegregatedPageListSerializer(pages, many=True)
        return self.success_response(data=serializer.data)


class PageDetailView(BaseAPIView):
    """GET /bible/pages/<page_id>/

    Returns full page detail with optional translation.
    Query param: ``?lang=es`` to get translated content.
    """

    def get(self, request: Request, page_id: UUID) -> Response:
        language_code: str | None = request.query_params.get("lang")
        service = SegregatedBibleService()

        # If a non-English language is requested and no cached translation
        # exists, trigger translation first.
        if language_code and language_code != "en":
            translation_service = BibleTranslationService()
            translation_service.translate_page(page_id, language_code)

        page = service.get_page_detail(page_id, language_code=language_code)
        serializer = SegregatedPageDetailSerializer(page)
        return self.success_response(data=serializer.data)


class BibleSearchView(BaseAPIView):
    """GET /bible/search/?q=<query>&section=<uuid>

    Full-text search across active pages.
    """

    pagination_class = StandardPageNumberPagination

    def get(self, request: Request) -> Response:
        query: str = request.query_params.get("q", "").strip()
        section_id_str: str | None = request.query_params.get("section")
        section_id: UUID | None = None
        if section_id_str:
            try:
                section_id = UUID(section_id_str)
            except ValueError:
                raise BadRequestError(
                    detail="Invalid section UUID."
                )

        service = SegregatedBibleService()
        pages = service.search_content(query, section_id=section_id)

        paginator = StandardPageNumberPagination()
        paginated_pages = paginator.paginate_queryset(pages, request)
        serializer = SegregatedPageListSerializer(paginated_pages, many=True)
        return paginator.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# Bookmark ViewSet
# ---------------------------------------------------------------------------


class BookmarkViewSet(BaseModelViewSet):
    """CRUD for bookmarks.

    list:   GET /bible/bookmarks/
    create: POST /bible/bookmarks/
    delete: DELETE /bible/bookmarks/<id>/
    """

    http_method_names = ["get", "post", "delete", "head", "options"]
    serializer_class = BookmarkSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = BookmarkService()

    def get_queryset(self):  # type: ignore[override]
        return self.service.list_bookmarks(
            self.request.user.id,
            bookmark_type=self.request.query_params.get("type"),
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = BookmarkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data

        bookmark = self.service.create_bookmark(
            request.user.id,
            bookmark_type=data["bookmark_type"],
            verse_reference=data.get("verse_reference", ""),
            content_type_id=data.get("content_type"),
            object_id=data.get("object_id"),
        )

        output = BookmarkSerializer(bookmark)
        return Response(
            {"message": "Bookmark created successfully.", "data": output.data},
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.service.delete_bookmark(request.user.id, kwargs["pk"])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Highlight ViewSet
# ---------------------------------------------------------------------------


class HighlightViewSet(BaseModelViewSet):
    """CRUD for highlights.

    list:   GET /bible/highlights/
    create: POST /bible/highlights/
    delete: DELETE /bible/highlights/<id>/
    """

    http_method_names = ["get", "post", "delete", "head", "options"]
    serializer_class = HighlightSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = HighlightService()

    def get_queryset(self):  # type: ignore[override]
        qs_params = self.request.query_params
        content_type_id: str | None = qs_params.get("content_type")
        object_id: str | None = qs_params.get("object_id")

        # If both content_type and object_id are supplied, scope to content.
        if content_type_id and object_id:
            return self.service.list_highlights_for_content(
                self.request.user.id,
                content_type_id=int(content_type_id),
                object_id=UUID(object_id),
            )

        return self.service.list_highlights(
            self.request.user.id,
            highlight_type=qs_params.get("type"),
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = HighlightCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data

        highlight = self.service.create_highlight(
            request.user.id,
            highlight_type=data["highlight_type"],
            color=data.get("color", "yellow"),
            verse_reference=data.get("verse_reference", ""),
            content_type_id=data.get("content_type"),
            object_id=data.get("object_id"),
            selection_start=data.get("selection_start"),
            selection_end=data.get("selection_end"),
        )

        output = HighlightSerializer(highlight)
        return Response(
            {"message": "Highlight created successfully.", "data": output.data},
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.service.delete_highlight(request.user.id, kwargs["pk"])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Note ViewSet
# ---------------------------------------------------------------------------


class NoteViewSet(BaseModelViewSet):
    """CRUD for notes.

    list:    GET /bible/notes/
    create:  POST /bible/notes/
    update:  PATCH /bible/notes/<id>/
    delete:  DELETE /bible/notes/<id>/
    """

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service = NoteService()

    def get_queryset(self):  # type: ignore[override]
        qs_params = self.request.query_params
        content_type_id: str | None = qs_params.get("content_type")
        object_id: str | None = qs_params.get("object_id")

        if content_type_id and object_id:
            return self.service.get_notes_for_content(
                self.request.user.id,
                content_type_id=int(content_type_id),
                object_id=UUID(object_id),
            )

        return self.service.list_notes(
            self.request.user.id,
            note_type=qs_params.get("type"),
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = NoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data

        note = self.service.create_note(
            request.user.id,
            note_type=data["note_type"],
            text=data["text"],
            verse_reference=data.get("verse_reference", ""),
            content_type_id=data.get("content_type"),
            object_id=data.get("object_id"),
        )

        output = NoteSerializer(note)
        return Response(
            {"message": "Note created successfully.", "data": output.data},
            status=status.HTTP_201_CREATED,
        )

    def partial_update(
        self, request: Request, *args: Any, **kwargs: Any,
    ) -> Response:
        serializer = NoteUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        note = self.service.update_note(
            request.user.id,
            kwargs["pk"],
            text=serializer.validated_data["text"],
        )

        output = NoteSerializer(note)
        return self.success_response(data=output.data, message="Note updated.")

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.service.delete_note(request.user.id, kwargs["pk"])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# API Bible Proxy
# ---------------------------------------------------------------------------


class ApiBibleProxyView(BaseAPIView):
    """GET /bible/api-bible/<path>/

    Proxies authenticated requests to the api.bible REST API, injecting the
    server-side API key so it is never exposed to mobile clients.

    Example:
        GET /bible/api-bible/bibles/
        GET /bible/api-bible/bibles/<bible_id>/books/
    """

    API_BIBLE_BASE_URL: str = "https://rest.api.bible/v1"

    # Allowlist of valid top-level path prefixes for the upstream API.
    ALLOWED_PATH_PREFIXES: tuple[str, ...] = ("bibles", "audio-bibles")

    def get(self, request: Request, path: str = "") -> Response:
        api_key: str = getattr(settings, "API_BIBLE_KEY", "")
        if not api_key:
            raise BadRequestError(
                detail="API Bible integration is not configured."
            )

        # SSRF prevention: only allow paths that start with known prefixes.
        normalized_path = path.strip("/")
        if not normalized_path or not normalized_path.startswith(
            self.ALLOWED_PATH_PREFIXES
        ):
            raise BadRequestError(
                detail="Invalid API Bible path."
            )

        url: str = f"{self.API_BIBLE_BASE_URL}/{normalized_path}"

        headers: dict[str, str] = {
            "api-key": api_key,
            "Accept": "application/json",
        }

        # Forward query params from the client request.
        params: dict[str, str] = {
            k: v for k, v in request.query_params.items()
        }

        try:
            upstream_response = requests.get(
                url, headers=headers, params=params, timeout=30,
            )
        except requests.RequestException as exc:
            logger.exception("API Bible proxy request failed: %s", exc)
            raise BadRequestError(
                detail="API Bible service is temporarily unavailable."
            )

        try:
            body = upstream_response.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            logger.error(
                "API Bible returned non-JSON response (status %s)",
                upstream_response.status_code,
            )
            raise BadRequestError(
                detail="API Bible returned an unexpected response format."
            )

        # If upstream returned an error, forward it.
        if upstream_response.status_code >= 400:
            return Response(body, status=upstream_response.status_code)

        # Unwrap the API Bible envelope ({"data": ..., "meta": ...})
        # and re-wrap in our standard {message, data} format so the
        # frontend response interceptor can handle it uniformly.
        api_data = body.get("data", body)
        return self.success_response(data=api_data)
