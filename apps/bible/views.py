from __future__ import annotations
import logging
from typing import Any
from uuid import UUID
import requests
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from apps.common.exceptions import BadRequestError
from apps.common.pagination import StandardPageNumberPagination
from apps.common.permissions import IsOwner
from apps.common.views import BaseAPIView, BaseModelViewSet
from .serializers import (
    BookmarkCreateSerializer,
    BookmarkSerializer,
    HighlightCreateSerializer,
    HighlightSerializer,
    NoteCreateSerializer,
    NoteSerializer,
    NoteUpdateSerializer,
    PageCommentCreateSerializer,
    SegregatedChapterListSerializer,
    SegregatedPageDetailSerializer,
    SegregatedPageListSerializer,
    SegregatedSectionListSerializer,
)

from .models import SegregatedPageComment
from .services import (
    BookmarkService,
    HighlightService,
    NoteService,
    SegregatedBibleService,
)

logger = logging.getLogger(__name__)


PREVIEW_CONTENT_MAX_CHARS: int = 500
PREVIEW_LIST_LIMIT: int = 3


def _is_authenticated(request: Request) -> bool:
    return getattr(request, "user", None) is not None and request.user.is_authenticated


class SegregatedSectionListView(BaseAPIView):
    """GET /bible/sections/

    Returns active sections, optionally prioritized by the authenticated
    user's age. Cached for 1 hour per age bracket. Supports ETag for 304.
    Unauthenticated users see a limited preview (first few sections).
    """

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        import hashlib
        from django.core.cache import cache as django_cache

        user_age: int | None = None

        if hasattr(request.user, "age"):
            user_age = request.user.age

        cache_key = f"bible_sections:age={user_age}"
        cached = django_cache.get(cache_key)

        if cached is not None:
            etag = hashlib.md5(str(cached).encode()).hexdigest()

            if request.META.get("HTTP_IF_NONE_MATCH") == etag:
                return Response(status=304)

            data = cached
            if not _is_authenticated(request):
                data = data[:PREVIEW_LIST_LIMIT]
                resp = self.success_response(
                    data=data,
                    message="Preview — sign in to view all sections.",
                )
                resp["ETag"] = etag
                return resp

            resp = self.success_response(data=data)
            resp["ETag"] = etag

            return resp

        service = SegregatedBibleService()
        sections = service.get_sections(user_age=user_age)
        serializer = SegregatedSectionListSerializer(sections, many=True)
        from apps.common.constants import CACHE_TIMEOUT_BIBLE_SECTIONS

        django_cache.set(
            cache_key, serializer.data, timeout=CACHE_TIMEOUT_BIBLE_SECTIONS
        )
        etag = hashlib.md5(str(serializer.data).encode()).hexdigest()

        data = serializer.data
        if not _is_authenticated(request):
            data = data[:PREVIEW_LIST_LIMIT]
            resp = self.success_response(
                data=data,
                message="Preview — sign in to view all sections.",
            )
            resp["ETag"] = etag
            return resp

        resp = self.success_response(data=data)
        resp["ETag"] = etag

        return resp


class ChapterListView(BaseAPIView):
    """GET /bible/sections/<section_id>/chapters/

    Returns active chapters for a section.
    Unauthenticated users see a limited preview.
    """

    permission_classes = [AllowAny]

    def get(self, request: Request, section_id: UUID) -> Response:
        service = SegregatedBibleService()
        chapters = service.get_chapters_for_section(section_id)
        serializer = SegregatedChapterListSerializer(chapters, many=True)

        if not _is_authenticated(request):
            return self.success_response(
                data=serializer.data[:PREVIEW_LIST_LIMIT],
                message="Preview — sign in to view all chapters.",
            )

        return self.success_response(data=serializer.data)


class PageListView(BaseAPIView):
    """GET /bible/chapters/<chapter_id>/pages/

    Returns active pages (without full content) for a chapter.
    Unauthenticated users see a limited preview.
    """

    permission_classes = [AllowAny]

    def get(self, request: Request, chapter_id: UUID) -> Response:
        service = SegregatedBibleService()
        pages = service.get_pages_for_chapter(chapter_id)
        serializer = SegregatedPageListSerializer(pages, many=True)

        if not _is_authenticated(request):
            return self.success_response(
                data=serializer.data[:PREVIEW_LIST_LIMIT],
                message="Preview — sign in to view all pages.",
            )

        return self.success_response(data=serializer.data)


class PageDetailView(BaseAPIView):
    """GET /bible/pages/<page_id>/

    Returns full page detail with optional translation.
    Query param: ``?lang=es`` to get translated content.
    Unauthenticated users receive truncated content (500 chars preview).
    """

    permission_classes = [AllowAny]

    def get(self, request: Request, page_id: UUID) -> Response:
        language_code: str | None = request.query_params.get("lang")
        service = SegregatedBibleService()

        if language_code and language_code != "en":
            from apps.bible.models import TranslatedPageCache

            has_cache = TranslatedPageCache.objects.filter(
                page_id=page_id, language_code=language_code
            ).exists()

            if not has_cache:
                from apps.bible.tasks import translate_page_async

                translate_page_async.delay(str(page_id), language_code)
                language_code = None

        page = service.get_page_detail(page_id, language_code=language_code)
        serializer = SegregatedPageDetailSerializer(page)
        data = serializer.data

        if not _is_authenticated(request):
            import copy

            data = copy.copy(data)
            content = data.get("content", "")
            if isinstance(content, str) and len(content) > PREVIEW_CONTENT_MAX_CHARS:
                data["content"] = content[:PREVIEW_CONTENT_MAX_CHARS] + "…"
            data["is_preview"] = True
            return self.success_response(
                data=data,
                message="Preview — sign in to view full content.",
            )

        return self.success_response(data=data)


class PageCommentCreateView(BaseAPIView):
    """POST /bible/pages/<page_id>/comments/"""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._bible_service = SegregatedBibleService()

    def post(self, request: Request, page_id: UUID) -> Response:
        serializer: PageCommentCreateSerializer = PageCommentCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        page = self._bible_service.get_page_detail(page_id)
        SegregatedPageComment.objects.create(
            user=request.user,
            page=page,
            content=serializer.validated_data["content"],
        )

        return self.created_response(message="Comment submitted.")


class BibleSearchView(BaseAPIView):
    """GET /bible/search/?q=<query>&section=<uuid>

    Full-text search across active pages.
    Unauthenticated users see limited results.
    """

    permission_classes = [AllowAny]

    pagination_class = StandardPageNumberPagination

    def get(self, request: Request) -> Response:
        query: str = request.query_params.get("q", "").strip()
        section_id_str: str | None = request.query_params.get("section")
        section_id: UUID | None = None

        if section_id_str:
            try:
                section_id = UUID(section_id_str)

            except ValueError:
                raise BadRequestError(detail="Invalid section UUID.")

        service = SegregatedBibleService()
        pages = service.search_content(query, section_id=section_id)

        if not _is_authenticated(request):
            pages = pages[:PREVIEW_LIST_LIMIT]
            serializer = SegregatedPageListSerializer(pages, many=True)
            return self.success_response(
                data=serializer.data,
                message="Preview — sign in to view all results.",
            )

        paginator = StandardPageNumberPagination()
        paginated_pages = paginator.paginate_queryset(pages, request)
        serializer = SegregatedPageListSerializer(paginated_pages, many=True)

        return paginator.get_paginated_response(serializer.data)


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

    def get_queryset(self):

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

    def get_queryset(self):

        qs_params = self.request.query_params
        content_type_id: str | None = qs_params.get("content_type")
        object_id: str | None = qs_params.get("object_id")

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

    def get_queryset(self):

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
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
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


class ApiBibleProxyView(BaseAPIView):
    """GET /bible/api-bible/<path>/

    Proxies requests to the api.bible REST API, injecting the server-side
    API key so it is never exposed to mobile clients. Responses are cached
    server-side in Redis to reduce API quota usage and latency.

    Unauthenticated users receive a preview: list endpoints return only the
    first few items, and content endpoints truncate the HTML body. The
    response includes ``is_preview: true`` so the client can prompt sign-in.

    Cache TTLs by path pattern:
        bibles/                         → 24 hours  (version list rarely changes)
        bibles/<id>/books/              → 7 days    (book list never changes)
        bibles/<id>/books/<id>/chapters → 7 days    (chapter list never changes)
        bibles/<id>/chapters/<id>       → 1 day     (verse content, stable)
        bibles/<id>/search              → 1 hour    (search results)
        audio-bibles/                   → 24 hours
        everything else                 → 1 hour

    Example:
        GET /bible/api-bible/bibles/
        GET /bible/api-bible/bibles/<bible_id>/books/
    """

    permission_classes = [AllowAny]

    API_BIBLE_BASE_URL: str = "https://rest.api.bible/v1"

    ALLOWED_PATH_PREFIXES: tuple[str, ...] = ("bibles", "audio-bibles")

    PREVIEW_LIST_LIMIT: int = 3
    PREVIEW_CONTENT_MAX_CHARS: int = 500

    CACHE_TTL_1H: int = 3600
    CACHE_TTL_24H: int = 86400
    CACHE_TTL_7D: int = 604800

    def _get_cache_ttl(self, path: str) -> int:
        """Determine cache TTL based on the API path pattern."""
        parts: list[str] = path.strip("/").split("/")
        depth: int = len(parts)

        if depth == 1:
            return self.CACHE_TTL_24H

        if depth >= 3 and parts[2] in ("books", "chapters"):
            return self.CACHE_TTL_7D

        if depth >= 3 and parts[2] == "search":
            return self.CACHE_TTL_1H

        if depth >= 4 and parts[2] == "chapters":
            return self.CACHE_TTL_24H

        return self.CACHE_TTL_1H

    def _truncate_for_preview(self, data: Any) -> Any:
        """Return a trimmed copy of *data* suitable for unauthenticated users.

        * If the top-level value is a list, only the first few items are kept.
        * If it is a dict with a ``content`` key (chapter / verse HTML), the
          HTML is truncated.
        * If it is a dict with a ``verses`` key (search results), the list of
          verses is trimmed.
        """
        import copy

        if isinstance(data, list):
            return data[: self.PREVIEW_LIST_LIMIT]

        if not isinstance(data, dict):
            return data

        preview = copy.copy(data)

        if "content" in preview and isinstance(preview["content"], str):
            content: str = preview["content"]
            if len(content) > self.PREVIEW_CONTENT_MAX_CHARS:
                preview["content"] = content[: self.PREVIEW_CONTENT_MAX_CHARS] + "…"

        if "verses" in preview and isinstance(preview["verses"], list):
            preview["verses"] = preview["verses"][: self.PREVIEW_LIST_LIMIT]

        return preview

    @staticmethod
    def _build_cache_key(path: str, params: dict[str, str]) -> str:
        """Build a deterministic cache key from path and query params."""
        import hashlib

        sorted_params: str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        raw: str = f"api_bible:{path}?{sorted_params}"
        return f"api_bible:{hashlib.sha256(raw.encode()).hexdigest()}"

    def get(self, request: Request, path: str = "") -> Response:
        from django.core.cache import cache as django_cache

        is_authenticated: bool = (
            getattr(request, "user", None) is not None and request.user.is_authenticated
        )

        api_key: str = getattr(settings, "API_BIBLE_KEY", "")

        if not api_key:
            raise BadRequestError(detail="API Bible integration is not configured.")

        normalized_path: str = path.strip("/")

        if not normalized_path or not normalized_path.startswith(
            self.ALLOWED_PATH_PREFIXES
        ):
            raise BadRequestError(detail="Invalid API Bible path.")

        params: dict[str, str] = {k: v for k, v in request.query_params.items()}
        cache_key: str = self._build_cache_key(normalized_path, params)
        cached_data = django_cache.get(cache_key)

        if cached_data is not None:
            if is_authenticated:
                return self.success_response(data=cached_data)
            return self.success_response(
                data=self._truncate_for_preview(cached_data),
                message="Preview — sign in to view full content.",
            )

        url: str = f"{self.API_BIBLE_BASE_URL}/{normalized_path}"
        headers: dict[str, str] = {
            "api-key": api_key,
            "Accept": "application/json",
        }

        try:
            upstream_response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30,
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

        if upstream_response.status_code >= 400:
            return Response(body, status=upstream_response.status_code)

        api_data = body.get("data", body)

        ttl: int = self._get_cache_ttl(normalized_path)
        django_cache.set(cache_key, api_data, timeout=ttl)

        if is_authenticated:
            return self.success_response(data=api_data)

        return self.success_response(
            data=self._truncate_for_preview(api_data),
            message="Preview — sign in to view full content.",
        )
