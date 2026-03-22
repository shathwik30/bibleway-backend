from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.exceptions import ForbiddenError, NotFoundError
from apps.common.pagination import StandardPageNumberPagination
from apps.common.throttles import BoostRateThrottle
from apps.common.views import BaseAPIView

from .models import PostBoost
from .models import PostView
from .serializers import (
    BoostAnalyticSnapshotSerializer,
    PostAnalyticsSerializer,
    PostBoostCreateSerializer,
    PostBoostSerializer,
    RecordViewSerializer,
)
from .services import AnalyticsService, PostBoostService, PostViewService


# ---------------------------------------------------------------------------
# Post analytics views
# ---------------------------------------------------------------------------


class PostAnalyticsView(BaseAPIView):
    """GET /analytics/posts/<uuid:post_id>/ -- analytics for a specific post."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._analytics_service = AnalyticsService()

    def get(self, request: Request, post_id: UUID) -> Response:
        data = self._analytics_service.get_post_analytics(
            post_id=post_id,
            requesting_user_id=request.user.id,
        )
        serializer = PostAnalyticsSerializer(data)
        return self.success_response(data=serializer.data)


class UserAnalyticsView(BaseAPIView):
    """GET /analytics/me/ -- aggregate analytics for the current user."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._analytics_service = AnalyticsService()

    def get(self, request: Request) -> Response:
        data = self._analytics_service.get_user_analytics(
            user_id=request.user.id,
        )
        return self.success_response(data=data)


# ---------------------------------------------------------------------------
# View / share recording
# ---------------------------------------------------------------------------


class RecordViewView(BaseAPIView):
    """POST /analytics/views/ -- record a content view or share."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._view_service = PostViewService()

    def post(self, request: Request) -> Response:
        serializer = RecordViewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        self._view_service.record_view(
            content_type_model=data["content_type_model"],
            object_id=data["object_id"],
            viewer_id=request.user.id,
            view_type=data.get("view_type", PostView.ViewType.VIEW),
        )
        return self.success_response(message="Recorded.")


# ---------------------------------------------------------------------------
# Boost views
# ---------------------------------------------------------------------------


class PostBoostCreateView(BaseAPIView):
    """POST /analytics/boosts/ -- activate a post boost."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [BoostRateThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._boost_service = PostBoostService()

    def post(self, request: Request) -> Response:
        serializer = PostBoostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        boost = self._boost_service.activate_boost(
            post_id=data["post_id"],
            user_id=request.user.id,
            tier=data["tier"],
            platform=data["platform"],
            receipt_data=data.get("receipt_data", ""),
            transaction_id=data["transaction_id"],
            duration_days=data["duration_days"],
        )

        out = PostBoostSerializer(boost)
        return self.created_response(
            data=out.data,
            message="Post boost activated successfully.",
        )


class PostBoostListView(BaseAPIView):
    """GET /analytics/boosts/list/ -- list current user's boosts.

    Query params:
        active_only (bool): If "true", only return active boosts.
                            Defaults to false (returns all boosts).
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._boost_service = PostBoostService()

    def get(self, request: Request) -> Response:
        active_only = request.query_params.get("active_only", "").lower() == "true"
        boosts = self._boost_service.get_user_boosts(
            user_id=request.user.id,
            active_only=active_only,
        )

        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(boosts, request, view=self)
        if page is not None:
            serializer = PostBoostSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = PostBoostSerializer(boosts, many=True)
        return self.success_response(data=serializer.data)


class BoostAnalyticsView(BaseAPIView):
    """GET /analytics/boosts/<uuid:boost_id>/analytics/ -- analytics for a boost."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._boost_service = PostBoostService()

    def get(self, request: Request, boost_id: UUID) -> Response:
        # Ownership check: verify the boost belongs to the requesting user's post
        try:
            boost = PostBoost.objects.select_related("post").get(pk=boost_id)
        except PostBoost.DoesNotExist:
            raise NotFoundError(detail=f"Boost with id '{boost_id}' not found.")

        if boost.user_id != request.user.id:
            raise ForbiddenError(
                detail="You can only view analytics for your own boosts."
            )

        snapshots = self._boost_service.get_boost_analytics(boost_id=boost_id)

        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(snapshots, request, view=self)
        if page is not None:
            serializer = BoostAnalyticSnapshotSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = BoostAnalyticSnapshotSerializer(snapshots, many=True)
        return self.success_response(data=serializer.data)
