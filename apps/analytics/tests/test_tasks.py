"""Tests for analytics Celery tasks.

Covers:
- archive_old_post_views: creates summaries from old views, purges raw rows,
  returns 0 when no old views exist.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.analytics.models import PostView, PostViewDailySummary
from apps.analytics.tasks import archive_old_post_views
from apps.social.models import Post

from conftest import PostFactory, UserFactory


@pytest.mark.django_db
class TestArchiveOldPostViews:
    """Tests for the archive_old_post_views Celery task."""

    def _create_old_view(self, post, viewer=None, days_old=31, view_type="view"):
        """Helper to create a PostView with a created_at in the past."""
        ct = ContentType.objects.get_for_model(Post)
        pv = PostView.objects.create(
            content_type=ct,
            object_id=post.pk,
            viewer=viewer,
            view_type=view_type,
        )

        old_date = timezone.now() - timedelta(days=days_old)
        PostView.objects.filter(pk=pv.pk).update(created_at=old_date)
        return pv

    def test_archive_creates_summaries_from_old_views(self):
        """Old views should be aggregated into PostViewDailySummary records."""
        post = PostFactory()
        viewer = UserFactory()

        self._create_old_view(post, viewer=viewer, days_old=35, view_type="view")
        self._create_old_view(post, viewer=viewer, days_old=35, view_type="view")
        self._create_old_view(post, viewer=viewer, days_old=35, view_type="share")

        result = archive_old_post_views(retention_days=30)
        assert result["summaries"] >= 1

        ct = ContentType.objects.get_for_model(Post)
        summaries = PostViewDailySummary.objects.filter(
            content_type=ct, object_id=post.pk
        )
        assert summaries.exists()
        summary = summaries.first()
        assert summary.view_count >= 2
        assert summary.share_count >= 1

    def test_archive_purges_old_raw_rows(self):
        """After archiving, raw PostView records older than retention_days are deleted."""
        post = PostFactory()

        self._create_old_view(post, days_old=35)
        self._create_old_view(post, days_old=35)

        ct = ContentType.objects.get_for_model(Post)
        PostView.objects.create(
            content_type=ct,
            object_id=post.pk,
            viewer=UserFactory(),
            view_type="view",
        )

        assert PostView.objects.count() == 3
        result = archive_old_post_views(retention_days=30)
        assert result["purged"] == 2

        assert PostView.objects.count() == 1

    def test_archive_with_no_old_views_returns_zero(self):
        """When there are no old views, the task should return 0 summaries and 0 purged."""

        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        PostView.objects.create(
            content_type=ct,
            object_id=post.pk,
            viewer=UserFactory(),
            view_type="view",
        )

        result = archive_old_post_views(retention_days=30)
        assert result["summaries"] == 0
        assert result["purged"] == 0

        assert PostView.objects.count() == 1

    def test_archive_no_views_at_all_returns_zero(self):
        """When there are no views at all, the task returns zeros."""
        result = archive_old_post_views(retention_days=30)
        assert result["summaries"] == 0
        assert result["purged"] == 0

    def test_archive_multiple_posts_creates_separate_summaries(self):
        """Each post should get its own summary row per day."""
        post1 = PostFactory()
        post2 = PostFactory()
        self._create_old_view(post1, days_old=40)
        self._create_old_view(post2, days_old=40)

        result = archive_old_post_views(retention_days=30)
        assert result["summaries"] >= 2
        assert result["purged"] == 2

        ct = ContentType.objects.get_for_model(Post)
        assert PostViewDailySummary.objects.filter(
            content_type=ct, object_id=post1.pk
        ).exists()
        assert PostViewDailySummary.objects.filter(
            content_type=ct, object_id=post2.pk
        ).exists()

    def test_archive_unique_viewers_counted(self):
        """unique_viewers in summary should count distinct viewer IDs."""
        post = PostFactory()
        viewer1 = UserFactory()
        viewer2 = UserFactory()
        self._create_old_view(post, viewer=viewer1, days_old=35)
        self._create_old_view(post, viewer=viewer1, days_old=35)
        self._create_old_view(post, viewer=viewer2, days_old=35)

        archive_old_post_views(retention_days=30)

        ct = ContentType.objects.get_for_model(Post)
        summary = PostViewDailySummary.objects.get(content_type=ct, object_id=post.pk)
        assert summary.unique_viewers == 2
