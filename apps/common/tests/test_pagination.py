"""Tests for apps.common.pagination — StandardPageNumberPagination and FeedCursorPagination."""

from __future__ import annotations

import pytest
from django.test import RequestFactory
from rest_framework.request import Request

from apps.common.pagination import FeedCursorPagination, StandardPageNumberPagination


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

rf = RequestFactory()


def _drf_request(path="/test/", method="get", query_params=None):
    """Build a DRF Request from a Django request factory."""
    url = path
    if query_params:
        url += "?" + "&".join(f"{k}={v}" for k, v in query_params.items())
    django_request = rf.get(url)
    return Request(django_request)


# ---------------------------------------------------------------------------
# StandardPageNumberPagination
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStandardPageNumberPagination:
    def test_envelope_structure(self, user):
        """Paginated response should have the expected envelope keys."""
        from conftest import PostFactory

        # Create enough items to fill a page
        posts = [PostFactory(author=user) for _ in range(3)]

        from apps.social.models import Post

        paginator = StandardPageNumberPagination()
        paginator.page_size = 20

        request = _drf_request("/api/v1/social/posts/")
        qs = Post.objects.all()
        page = paginator.paginate_queryset(qs, request)

        # Simulate serialized data
        serialized_data = [{"id": str(p.pk)} for p in page]
        response = paginator.get_paginated_response(serialized_data)

        assert response.data["message"] == "Success"
        data = response.data["data"]
        assert "count" in data
        assert "next" in data
        assert "previous" in data
        assert "total_pages" in data
        assert "current_page" in data
        assert "results" in data

    def test_count_matches(self, user):
        from conftest import PostFactory

        for _ in range(5):
            PostFactory(author=user)

        from apps.social.models import Post

        paginator = StandardPageNumberPagination()
        paginator.page_size = 20
        request = _drf_request("/api/v1/social/posts/")
        qs = Post.objects.all()
        page = paginator.paginate_queryset(qs, request)
        response = paginator.get_paginated_response([{"id": str(p.pk)} for p in page])
        assert response.data["data"]["count"] == 5

    def test_current_page_is_1(self, user):
        from conftest import PostFactory

        PostFactory(author=user)

        from apps.social.models import Post

        paginator = StandardPageNumberPagination()
        request = _drf_request("/api/v1/social/posts/")
        qs = Post.objects.all()
        page = paginator.paginate_queryset(qs, request)
        response = paginator.get_paginated_response([{"id": str(p.pk)} for p in page])
        assert response.data["data"]["current_page"] == 1

    def test_total_pages_calculation(self, user):
        from conftest import PostFactory

        for _ in range(25):
            PostFactory(author=user)

        from apps.social.models import Post

        paginator = StandardPageNumberPagination()
        paginator.page_size = 10
        request = _drf_request("/api/v1/social/posts/")
        qs = Post.objects.all()
        page = paginator.paginate_queryset(qs, request)
        response = paginator.get_paginated_response([{"id": str(p.pk)} for p in page])
        assert response.data["data"]["total_pages"] == 3  # 25/10 = 2.5 -> 3

    def test_next_link_present_when_more_pages(self, user):
        from conftest import PostFactory

        for _ in range(25):
            PostFactory(author=user)

        from apps.social.models import Post

        paginator = StandardPageNumberPagination()
        paginator.page_size = 10
        request = _drf_request("/api/v1/social/posts/")
        qs = Post.objects.all()
        page = paginator.paginate_queryset(qs, request)
        response = paginator.get_paginated_response([{"id": str(p.pk)} for p in page])
        assert response.data["data"]["next"] is not None

    def test_previous_link_none_on_first_page(self, user):
        from conftest import PostFactory

        PostFactory(author=user)

        from apps.social.models import Post

        paginator = StandardPageNumberPagination()
        request = _drf_request("/api/v1/social/posts/")
        qs = Post.objects.all()
        page = paginator.paginate_queryset(qs, request)
        response = paginator.get_paginated_response([{"id": str(p.pk)} for p in page])
        assert response.data["data"]["previous"] is None

    def test_results_matches_serialized_data(self, user):
        from conftest import PostFactory

        p = PostFactory(author=user)

        from apps.social.models import Post

        paginator = StandardPageNumberPagination()
        request = _drf_request("/api/v1/social/posts/")
        qs = Post.objects.all()
        page = paginator.paginate_queryset(qs, request)
        serialized = [{"id": str(item.pk)} for item in page]
        response = paginator.get_paginated_response(serialized)
        assert response.data["data"]["results"] == serialized


# ---------------------------------------------------------------------------
# FeedCursorPagination
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFeedCursorPagination:
    def test_envelope_structure(self, user):
        from conftest import PostFactory

        PostFactory(author=user)

        from apps.social.models import Post

        paginator = FeedCursorPagination()
        paginator.page_size = 20
        request = _drf_request("/api/v1/social/posts/")
        qs = Post.objects.all()
        page = paginator.paginate_queryset(qs, request)
        response = paginator.get_paginated_response([{"id": str(p.pk)} for p in page])

        assert response.data["message"] == "Success"
        data = response.data["data"]
        assert "next" in data
        assert "previous" in data
        assert "results" in data

    def test_no_count_or_total_pages(self, user):
        """Cursor pagination should NOT include count/total_pages."""
        from conftest import PostFactory

        PostFactory(author=user)

        from apps.social.models import Post

        paginator = FeedCursorPagination()
        request = _drf_request("/api/v1/social/posts/")
        qs = Post.objects.all()
        page = paginator.paginate_queryset(qs, request)
        response = paginator.get_paginated_response([{"id": str(p.pk)} for p in page])
        data = response.data["data"]
        assert "count" not in data
        assert "total_pages" not in data
        assert "current_page" not in data

    def test_results_returned(self, user):
        from conftest import PostFactory

        PostFactory(author=user)

        from apps.social.models import Post

        paginator = FeedCursorPagination()
        request = _drf_request("/api/v1/social/posts/")
        qs = Post.objects.all()
        page = paginator.paginate_queryset(qs, request)
        serialized = [{"id": str(item.pk)} for item in page]
        response = paginator.get_paginated_response(serialized)
        assert response.data["data"]["results"] == serialized
