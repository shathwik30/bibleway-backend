from __future__ import annotations
from collections import OrderedDict
from typing import Any
from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.response import Response


class StandardPageNumberPagination(PageNumberPagination):
    """Standard page-based pagination for list endpoints."""

    page_size: int = 20

    page_size_query_param: str = "page_size"

    max_page_size: int = 100

    def get_paginated_response(self, data: list[Any]) -> Response:
        return Response(
            {
                "message": "Success",
                "data": OrderedDict(
                    [
                        ("count", self.page.paginator.count),
                        ("next", self.get_next_link()),
                        ("previous", self.get_previous_link()),
                        ("total_pages", self.page.paginator.num_pages),
                        ("current_page", self.page.number),
                        ("results", data),
                    ]
                ),
            }
        )


class FeedCursorPagination(CursorPagination):
    """Cursor-based pagination for feed endpoints (Posts, Prayers)."""

    page_size: int = 20

    ordering: str = "-created_at"

    cursor_query_param: str = "cursor"

    def get_paginated_response(self, data: list[Any]) -> Response:
        return Response(
            {
                "message": "Success",
                "data": OrderedDict(
                    [
                        ("next", self.get_next_link()),
                        ("previous", self.get_previous_link()),
                        ("results", data),
                    ]
                ),
            }
        )


class BoostedFeedCursorPagination(FeedCursorPagination):
    """Cursor pagination that orders by boost-aware feed_rank.

    Expects the queryset to be annotated with a ``feed_rank`` DateTimeField
    that gives boosted posts a time-shifted advantage.
    """

    ordering: str = "-feed_rank"
