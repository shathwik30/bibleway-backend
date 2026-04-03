from __future__ import annotations
from typing import TYPE_CHECKING, Any
from uuid import UUID
from django.db.models import QuerySet
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from apps.common.pagination import (
    BoostedFeedCursorPagination,
    FeedCursorPagination,
    StandardPageNumberPagination,
)

from apps.common.permissions import IsAdminUser, IsOwnerOrReadOnly
from apps.common.storage_backends import PublicMediaStorage
from apps.common.utils import get_blocked_user_ids
from apps.common.views import BaseAPIView, BaseModelViewSet, FeedViewSet
from .serializers import (
    CommentCreateSerializer,
    CommentSerializer,
    PostCreateSerializer,
    PostDetailSerializer,
    PostListSerializer,
    PrayerCreateSerializer,
    PrayerDetailSerializer,
    PrayerListSerializer,
    ReactionCreateSerializer,
    ReactionSerializer,
    ReplyCreateSerializer,
    ReplySerializer,
    ReportCreateSerializer,
)

from .services import (
    CommentService,
    PostService,
    PrayerService,
    ReactionService,
    ReplyService,
    ReportService,
)

if TYPE_CHECKING:
    from .models import Comment, Post, Prayer, Reply


class PostViewSet(FeedViewSet):
    """CRUD and engagement endpoints for posts.

    list   – GET  /posts/                (feed, cursor-paginated)
    create – POST /posts/
    retrieve – GET  /posts/{id}/
    destroy – DELETE /posts/{id}/
    react  – POST /posts/{id}/react/
    comments – GET|POST /posts/{id}/comments/
    share  – GET  /posts/{id}/share/
    """

    http_method_names = ["get", "post", "delete", "head", "options"]

    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    pagination_class = BoostedFeedCursorPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._post_service = PostService()
        self._reaction_service = ReactionService()
        self._comment_service = CommentService()

    def get_queryset(self) -> QuerySet[Post]:

        return self._post_service.get_feed(requesting_user=self.request.user)

    def get_serializer_class(self) -> type[BaseSerializer]:

        if self.action == "create":
            return PostCreateSerializer

        if self.action == "list":
            return PostListSerializer

        if self.action == "react":
            return ReactionCreateSerializer

        if self.action in ("comments", "list_comments"):
            return CommentCreateSerializer

        return PostDetailSerializer

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        author_id = request.query_params.get("author")

        if author_id:
            try:
                author_uuid = UUID(author_id)

            except ValueError:
                return Response(
                    {"message": "Invalid author UUID.", "data": None},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = self._post_service.get_user_posts(
                user_id=author_uuid,
                requesting_user=request.user,
            )

        else:
            queryset = self.get_queryset()

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = PostListSerializer(
                page, many=True, context=self.get_serializer_context()
            )

            return self.get_paginated_response(serializer.data)

        serializer = PostListSerializer(
            queryset, many=True, context=self.get_serializer_context()
        )

        return Response(serializer.data)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = PostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        post = self._post_service.create_post(
            author=request.user,
            text_content=data.get("text_content", ""),
            media_keys=data.get("media_keys"),
            media_types=data.get("media_types"),
            media_files=data.get("media_files"),
        )
        out = PostDetailSerializer(post, context=self.get_serializer_context())

        return Response(out.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        post = self._post_service.get_by_id_for_user(
            kwargs["pk"], requesting_user=request.user
        )
        serializer = PostDetailSerializer(post, context=self.get_serializer_context())

        return Response(serializer.data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self._post_service.delete_post(
            post_id=kwargs["pk"], requesting_user=request.user
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="react")
    def react(self, request: Request, pk: UUID | None = None) -> Response:
        """Toggle a reaction on this post."""
        serializer = ReactionCreateSerializer(
            data={
                "emoji_type": request.data.get("emoji_type"),
                "content_type_model": "post",
                "object_id": str(pk),
            }
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        reaction = self._reaction_service.toggle_reaction(
            user=request.user,
            content_type_model=data["content_type_model"],
            object_id=data["object_id"],
            emoji_type=data["emoji_type"],
        )

        if reaction is None:
            return Response(
                {"message": "Reaction removed.", "data": None},
                status=status.HTTP_200_OK,
            )

        out = ReactionSerializer(reaction)

        return Response(
            {"message": "Reaction added.", "data": out.data},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request: Request, pk: UUID | None = None) -> Response:
        """List or create comments on this post."""

        if request.method == "GET":
            qs = self._comment_service.list_comments_for_content(
                content_type_model="post", object_id=pk
            )
            blocked_ids = get_blocked_user_ids(request.user.id)
            qs = qs.exclude(user_id__in=blocked_ids)
            paginator = StandardPageNumberPagination()
            page_data = paginator.paginate_queryset(qs, request, view=self)

            if page_data is not None:
                serializer = CommentSerializer(page_data, many=True)

                return paginator.get_paginated_response(serializer.data)

            serializer = CommentSerializer(qs, many=True)

            return Response(serializer.data)

        create_ser = CommentCreateSerializer(
            data={
                "text": request.data.get("text"),
                "content_type_model": "post",
                "object_id": str(pk),
            }
        )
        create_ser.is_valid(raise_exception=True)
        data = create_ser.validated_data
        comment = self._comment_service.create_comment(
            user=request.user,
            content_type_model=data["content_type_model"],
            object_id=data["object_id"],
            text=data["text"],
        )
        out = CommentSerializer(comment)

        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="share")
    def share(self, request: Request, pk: UUID | None = None) -> Response:
        """Return deep-link / share data for a post."""
        share_data = self._post_service.share_post(post_id=pk)

        return Response(share_data)


class PrayerViewSet(FeedViewSet):
    """CRUD and engagement endpoints for prayer requests.

    list     – GET  /prayers/
    create   – POST /prayers/
    retrieve – GET  /prayers/{id}/
    destroy  – DELETE /prayers/{id}/
    react    – POST /prayers/{id}/react/
    comments – GET|POST /prayers/{id}/comments/
    share    – GET  /prayers/{id}/share/
    """

    http_method_names = ["get", "post", "delete", "head", "options"]

    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    pagination_class = FeedCursorPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._prayer_service = PrayerService()
        self._reaction_service = ReactionService()
        self._comment_service = CommentService()

    def get_queryset(self) -> QuerySet[Prayer]:

        return self._prayer_service.get_feed(requesting_user=self.request.user)

    def get_serializer_class(self) -> type[BaseSerializer]:

        if self.action == "create":
            return PrayerCreateSerializer

        if self.action == "list":
            return PrayerListSerializer

        if self.action == "react":
            return ReactionCreateSerializer

        if self.action in ("comments", "list_comments"):
            return CommentCreateSerializer

        return PrayerDetailSerializer

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        author_id = request.query_params.get("author")

        if author_id:
            try:
                author_uuid = UUID(author_id)

            except ValueError:
                return Response(
                    {"message": "Invalid author UUID.", "data": None},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = self._prayer_service.get_user_prayers(
                user_id=author_uuid,
                requesting_user=request.user,
            )

        else:
            queryset = self.get_queryset()

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = PrayerListSerializer(
                page, many=True, context=self.get_serializer_context()
            )

            return self.get_paginated_response(serializer.data)

        serializer = PrayerListSerializer(
            queryset, many=True, context=self.get_serializer_context()
        )

        return Response(serializer.data)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = PrayerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        prayer = self._prayer_service.create_prayer(
            author=request.user,
            title=data["title"],
            description=data.get("description", ""),
            media_keys=data.get("media_keys"),
            media_types=data.get("media_types"),
            media_files=data.get("media_files"),
        )
        out = PrayerDetailSerializer(prayer, context=self.get_serializer_context())

        return Response(out.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        prayer = self._prayer_service.get_by_id_for_user(
            kwargs["pk"], requesting_user=request.user
        )
        serializer = PrayerDetailSerializer(
            prayer, context=self.get_serializer_context()
        )

        return Response(serializer.data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self._prayer_service.delete_prayer(
            prayer_id=kwargs["pk"], requesting_user=request.user
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="react")
    def react(self, request: Request, pk: UUID | None = None) -> Response:
        """Toggle a reaction on this prayer."""
        serializer = ReactionCreateSerializer(
            data={
                "emoji_type": request.data.get("emoji_type"),
                "content_type_model": "prayer",
                "object_id": str(pk),
            }
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        reaction = self._reaction_service.toggle_reaction(
            user=request.user,
            content_type_model=data["content_type_model"],
            object_id=data["object_id"],
            emoji_type=data["emoji_type"],
        )

        if reaction is None:
            return Response(
                {"message": "Reaction removed.", "data": None},
                status=status.HTTP_200_OK,
            )

        out = ReactionSerializer(reaction)

        return Response(
            {"message": "Reaction added.", "data": out.data},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request: Request, pk: UUID | None = None) -> Response:
        """List or create comments on this prayer."""

        if request.method == "GET":
            qs = self._comment_service.list_comments_for_content(
                content_type_model="prayer", object_id=pk
            )
            blocked_ids = get_blocked_user_ids(request.user.id)
            qs = qs.exclude(user_id__in=blocked_ids)
            paginator = StandardPageNumberPagination()
            page_data = paginator.paginate_queryset(qs, request, view=self)

            if page_data is not None:
                serializer = CommentSerializer(page_data, many=True)

                return paginator.get_paginated_response(serializer.data)

            serializer = CommentSerializer(qs, many=True)

            return Response(serializer.data)

        create_ser = CommentCreateSerializer(
            data={
                "text": request.data.get("text"),
                "content_type_model": "prayer",
                "object_id": str(pk),
            }
        )
        create_ser.is_valid(raise_exception=True)
        data = create_ser.validated_data
        comment = self._comment_service.create_comment(
            user=request.user,
            content_type_model=data["content_type_model"],
            object_id=data["object_id"],
            text=data["text"],
        )
        out = CommentSerializer(comment)

        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="share")
    def share(self, request: Request, pk: UUID | None = None) -> Response:
        """Return deep-link / share data for a prayer."""
        share_data = self._prayer_service.share_prayer(prayer_id=pk)

        return Response(share_data)


class CommentViewSet(BaseModelViewSet):
    """CRUD for comments (typically nested under posts/prayers via URL config).

    list    – GET    /comments/?content_type_model=post&object_id=<uuid>
    destroy – DELETE /comments/{id}/
    """

    http_method_names = ["get", "post", "delete", "head", "options"]

    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    pagination_class = StandardPageNumberPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._comment_service = CommentService()

    def get_queryset(self) -> QuerySet[Comment]:

        content_type_model = self.request.query_params.get("content_type_model", "post")
        object_id = self.request.query_params.get("object_id")

        if object_id:
            return self._comment_service.list_comments_for_content(
                content_type_model=content_type_model,
                object_id=UUID(object_id),
            )

        return self._comment_service.get_queryset()

    def get_serializer_class(self) -> type[BaseSerializer]:

        if self.action == "create":
            return CommentCreateSerializer

        return CommentSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        comment = self._comment_service.create_comment(
            user=request.user,
            content_type_model=data["content_type_model"],
            object_id=data["object_id"],
            text=data["text"],
        )
        out = CommentSerializer(comment)

        return Response(out.data, status=status.HTTP_201_CREATED)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self._comment_service.delete_comment(
            comment_id=kwargs["pk"], requesting_user=request.user
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class ReplyViewSet(BaseModelViewSet):
    """CRUD for replies, nested under a comment.

    list    – GET    /comments/{comment_pk}/replies/
    create  – POST   /comments/{comment_pk}/replies/
    destroy – DELETE /comments/{comment_pk}/replies/{id}/
    """

    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    pagination_class = StandardPageNumberPagination

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._reply_service = ReplyService()

    def get_queryset(self) -> QuerySet[Reply]:

        comment_pk = self.kwargs.get("comment_pk")

        if comment_pk:
            return self._reply_service.list_replies_for_comment(
                comment_id=UUID(str(comment_pk))
            )

        return self._reply_service.get_queryset()

    def get_serializer_class(self) -> type[BaseSerializer]:

        if self.action == "create":
            return ReplyCreateSerializer

        return ReplySerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = ReplyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment_pk = self.kwargs["comment_pk"]
        reply = self._reply_service.create_reply(
            user=request.user,
            comment_id=UUID(str(comment_pk)),
            text=serializer.validated_data["text"],
        )
        out = ReplySerializer(reply)

        return Response(out.data, status=status.HTTP_201_CREATED)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self._reply_service.delete_reply(
            reply_id=kwargs["pk"], requesting_user=request.user
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportCreateView(BaseAPIView):
    """POST /reports/ -- file a content report."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._report_service = ReportService()

    def post(self, request: Request) -> Response:
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        report = self._report_service.create_report(
            reporter=request.user,
            content_type_model=data["content_type_model"],
            object_id=data["object_id"],
            reason=data["reason"],
            description=data.get("description", ""),
        )

        return self.created_response(
            data={
                "id": str(report.pk),
                "reason": report.reason,
                "status": report.status,
            },
            message="Report submitted successfully.",
        )


class ReportListView(BaseAPIView):
    """GET /reports/ -- list pending reports (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._report_service = ReportService()

    def get(self, request: Request) -> Response:
        reports = self._report_service.list_pending_reports().select_related(
            "content_type"
        )
        data = [
            {
                "id": str(r.pk),
                "reporter": {
                    "id": str(r.reporter_id),
                    "full_name": r.reporter.full_name,
                },
                "content_type": r.content_type.model,
                "object_id": str(r.object_id),
                "reason": r.reason,
                "description": r.description,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in reports
        ]

        return self.success_response(data=data)


class BulkPostDetailView(BaseAPIView):
    """POST /posts/bulk/ -- fetch multiple posts in a single request.

    Body: {"post_ids": ["uuid1", "uuid2", ...]}
    Max 50 IDs per request.
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._post_service = PostService()

    def post(self, request: Request) -> Response:
        from apps.common.exceptions import BadRequestError

        post_ids = request.data.get("post_ids", [])

        if not post_ids or not isinstance(post_ids, list):
            raise BadRequestError(detail="Provide a list of post_ids.")

        if len(post_ids) > 50:
            raise BadRequestError(detail="Maximum 50 post_ids per request.")

        blocked_ids = get_blocked_user_ids(request.user.id)
        posts = (
            self._post_service.get_queryset()
            .filter(pk__in=post_ids)
            .exclude(author_id__in=blocked_ids)
        )
        serializer = PostDetailSerializer(
            posts, many=True, context={"request": request}
        )

        return self.success_response(data=serializer.data)


class MediaUploadView(BaseAPIView):
    """POST /media/upload/ -- upload files to UploadThing, return public URLs.

    Accepts multipart form data with one or more ``files``.
    Returns a list of ``{key, url}`` for each uploaded file.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        files = request.FILES.getlist("files")

        if not files:
            return Response(
                {"message": "No files provided.", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(files) > 10:
            return Response(
                {"message": "Maximum 10 files per upload.", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        storage = PublicMediaStorage()
        results = []

        for f in files:
            saved_key = storage.save(f"uploads/{request.user.id}/{f.name}", f)
            results.append(
                {
                    "key": saved_key,
                    "url": storage.url(saved_key),
                }
            )

        return self.success_response(data=results)
