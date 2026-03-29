from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from .pagination import FeedCursorPagination, StandardPageNumberPagination


class BaseAPIView(APIView):
    """Base API view with standard permission and response helpers."""

    permission_classes = [IsAuthenticated]

    def success_response(
        self,
        data: Any = None,
        message: str = "Success",
        status_code: int = status.HTTP_200_OK,
    ) -> Response:
        return Response(
            {"message": message, "data": data},
            status=status_code,
        )

    def created_response(
        self,
        data: Any = None,
        message: str = "Created successfully",
    ) -> Response:
        return self.success_response(
            data=data, message=message, status_code=status.HTTP_201_CREATED
        )

    def no_content_response(self) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)

    def paginated_response(
        self,
        queryset: Any,
        serializer_class: type,
        request: Request,
    ) -> Response:
        """Paginate a queryset and return a standard response."""
        paginator: StandardPageNumberPagination = self.pagination_class()
        page: Any = paginator.paginate_queryset(queryset, request, view=self)

        if page is not None:
            serializer = serializer_class(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = serializer_class(queryset, many=True)
        return self.success_response(data=serializer.data)


class BaseModelViewSet(ModelViewSet):
    """Base viewset with standard pagination and permissions."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPageNumberPagination

    def get_serializer_context(self) -> dict[str, Any]:
        context = super().get_serializer_context()
        user = self.request.user
        if user and user.is_authenticated:
            context["user"] = user
        else:
            context["user"] = None
        return context


class FeedViewSet(BaseModelViewSet):
    """Viewset with cursor-based pagination for feed endpoints."""

    pagination_class = FeedCursorPagination
