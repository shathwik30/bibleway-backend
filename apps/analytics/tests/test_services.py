"""Tests for apps.analytics.services — PostViewService, PostBoostService, AnalyticsService."""

from __future__ import annotations
import datetime
from uuid import uuid4
import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from apps.analytics.models import PostView
from apps.analytics.services import AnalyticsService, PostBoostService, PostViewService
from apps.common.exceptions import BadRequestError, ForbiddenError, NotFoundError
from apps.social.models import Post


@pytest.mark.django_db
class TestPostViewServiceRecordView:
    def setup_method(self):
        self.service = PostViewService()

    def test_record_view_creates_view(self, user, user2):
        from conftest import PostFactory

        post = PostFactory(author=user)
        view = self.service.record_view(
            content_type_model="post",
            object_id=post.id,
            viewer_id=user2.id,
        )
        assert isinstance(view, PostView)
        assert view.viewer_id == user2.id

    def test_record_view_anonymous(self, user):
        from conftest import PostFactory

        post = PostFactory(author=user)
        view = self.service.record_view(
            content_type_model="post",
            object_id=post.id,
            viewer_id=None,
        )
        assert view.viewer is None

    def test_deduplicates_within_one_hour(self, user, user2):
        from conftest import PostFactory

        post = PostFactory(author=user)
        view1 = self.service.record_view(
            content_type_model="post",
            object_id=post.id,
            viewer_id=user2.id,
        )
        view2 = self.service.record_view(
            content_type_model="post",
            object_id=post.id,
            viewer_id=user2.id,
        )
        assert view1.pk == view2.pk
        ct = ContentType.objects.get_for_model(Post)
        assert (
            PostView.objects.filter(
                content_type=ct, object_id=post.id, viewer_id=user2.id
            ).count()
            == 1
        )

    def test_allows_new_view_after_one_hour(self, user, user2):
        from conftest import PostFactory

        post = PostFactory(author=user)
        view1 = self.service.record_view(
            content_type_model="post",
            object_id=post.id,
            viewer_id=user2.id,
        )
        PostView.objects.filter(pk=view1.pk).update(
            created_at=timezone.now() - datetime.timedelta(hours=2)
        )
        view2 = self.service.record_view(
            content_type_model="post",
            object_id=post.id,
            viewer_id=user2.id,
        )
        assert view1.pk != view2.pk

    def test_anonymous_views_not_deduplicated(self, user):
        from conftest import PostFactory

        post = PostFactory(author=user)
        self.service.record_view(
            content_type_model="post", object_id=post.id, viewer_id=None
        )
        self.service.record_view(
            content_type_model="post", object_id=post.id, viewer_id=None
        )
        ct = ContentType.objects.get_for_model(Post)
        assert PostView.objects.filter(content_type=ct, object_id=post.id).count() == 2

    def test_invalid_content_type_raises(self, user):
        with pytest.raises(BadRequestError, match="Invalid content type"):
            self.service.record_view(
                content_type_model="invalid_model",
                object_id=uuid4(),
                viewer_id=user.id,
            )

    def test_nonexistent_post_raises(self, user):
        with pytest.raises(NotFoundError):
            self.service.record_view(
                content_type_model="post",
                object_id=uuid4(),
                viewer_id=user.id,
            )


@pytest.mark.django_db
class TestPostViewServiceGetViewCount:
    def setup_method(self):
        self.service = PostViewService()

    def test_get_view_count(self, user, user2):
        from conftest import PostFactory, UserFactory

        post = PostFactory(author=user)
        user3 = UserFactory()
        self.service.record_view(
            content_type_model="post", object_id=post.id, viewer_id=user2.id
        )
        self.service.record_view(
            content_type_model="post", object_id=post.id, viewer_id=user3.id
        )
        count = self.service.get_view_count(
            content_type_model="post", object_id=post.id
        )
        assert count == 2

    def test_get_view_count_zero(self, user):
        from conftest import PostFactory

        post = PostFactory(author=user)
        count = self.service.get_view_count(
            content_type_model="post", object_id=post.id
        )
        assert count == 0


@pytest.mark.django_db
class TestPostBoostServiceDeactivateExpired:
    def setup_method(self):
        self.service = PostBoostService()

    def test_deactivate_expired_boosts(self, user):
        from conftest import PostBoostFactory, PostFactory

        post = PostFactory(author=user, is_boosted=True)
        PostBoostFactory(
            post=post,
            user=user,
            is_active=True,
            expires_at=timezone.now() - datetime.timedelta(days=1),
        )
        count = self.service.deactivate_expired_boosts()
        assert count == 1
        post.refresh_from_db()
        assert post.is_boosted is False

    def test_does_not_deactivate_unexpired(self, user):
        from conftest import PostBoostFactory, PostFactory

        post = PostFactory(author=user, is_boosted=True)
        PostBoostFactory(
            post=post,
            user=user,
            is_active=True,
            expires_at=timezone.now() + datetime.timedelta(days=3),
        )
        count = self.service.deactivate_expired_boosts()
        assert count == 0
        post.refresh_from_db()
        assert post.is_boosted is True

    def test_post_stays_boosted_if_other_active_boosts_exist(self, user):
        from conftest import PostBoostFactory, PostFactory

        post = PostFactory(author=user, is_boosted=True)
        PostBoostFactory(
            post=post,
            user=user,
            is_active=True,
            expires_at=timezone.now() - datetime.timedelta(hours=1),
            transaction_id=f"expired_{uuid4().hex[:8]}",
        )
        PostBoostFactory(
            post=post,
            user=user,
            is_active=True,
            expires_at=timezone.now() + datetime.timedelta(days=5),
            transaction_id=f"active_{uuid4().hex[:8]}",
        )
        count = self.service.deactivate_expired_boosts()
        assert count == 1
        post.refresh_from_db()
        assert post.is_boosted is True

    def test_returns_zero_when_nothing_expired(self, user):
        count = self.service.deactivate_expired_boosts()
        assert count == 0


@pytest.mark.django_db
class TestPostBoostServiceGetActive:
    def setup_method(self):
        self.service = PostBoostService()

    def test_get_active_boosts(self, user):
        from conftest import PostBoostFactory, PostFactory

        post = PostFactory(author=user)
        PostBoostFactory(post=post, user=user, is_active=True)
        PostBoostFactory(
            post=post,
            user=user,
            is_active=False,
            transaction_id=f"inactive_{uuid4().hex[:8]}",
        )
        active = self.service.get_user_boosts(user_id=user.id, active_only=True)
        assert active.count() == 1

    def test_get_active_boosts_empty(self, user):
        active = self.service.get_user_boosts(user_id=user.id, active_only=True)
        assert active.count() == 0


@pytest.mark.django_db
class TestPostBoostServiceGetBoostAnalytics:
    def setup_method(self):
        self.service = PostBoostService()

    def test_get_boost_analytics(self, user):
        from conftest import BoostAnalyticSnapshotFactory, PostBoostFactory, PostFactory

        post = PostFactory(author=user)
        boost = PostBoostFactory(post=post, user=user, is_active=True)
        BoostAnalyticSnapshotFactory(boost=boost, snapshot_date=timezone.now().date())
        BoostAnalyticSnapshotFactory(
            boost=boost,
            snapshot_date=timezone.now().date() - datetime.timedelta(days=1),
        )
        snapshots = self.service.get_boost_analytics(boost_id=boost.id)
        assert snapshots.count() == 2

    def test_get_boost_analytics_nonexistent_raises(self):
        with pytest.raises(NotFoundError):
            self.service.get_boost_analytics(boost_id=uuid4())


@pytest.mark.django_db
class TestAnalyticsServicePostAnalytics:
    def setup_method(self):
        self.analytics_service = AnalyticsService()
        self.view_service = PostViewService()

    def test_get_post_analytics_as_author(self, user, user2):
        """get_post_analytics returns view/reaction/comment counts for the post author."""
        from conftest import PostFactory

        post = PostFactory(author=user)
        self.view_service.record_view(
            content_type_model="post", object_id=post.id, viewer_id=user2.id
        )
        result = self.analytics_service.get_post_analytics(
            post_id=post.id, requesting_user_id=user.id
        )
        assert result["views"] == 1
        assert result["reactions"] == 0
        assert result["comments"] == 0
        assert result["shares"] == 0

    def test_get_post_analytics_forbidden_for_non_author(self, user, user2):
        from conftest import PostFactory

        post = PostFactory(author=user)

        with pytest.raises(ForbiddenError, match="only view analytics for your own"):
            self.analytics_service.get_post_analytics(
                post_id=post.id, requesting_user_id=user2.id
            )

    def test_get_post_analytics_forbidden_when_none(self, user):
        from conftest import PostFactory

        post = PostFactory(author=user)

        with pytest.raises(ForbiddenError):
            self.analytics_service.get_post_analytics(
                post_id=post.id, requesting_user_id=None
            )

    def test_nonexistent_post_raises(self, user):
        with pytest.raises(NotFoundError):
            self.analytics_service.get_post_analytics(
                post_id=uuid4(), requesting_user_id=user.id
            )


@pytest.mark.django_db
class TestAnalyticsServiceUserAnalytics:
    def setup_method(self):
        self.analytics_service = AnalyticsService()
        self.view_service = PostViewService()

    def test_get_user_analytics(self, user, user2):
        from conftest import PostFactory

        post1 = PostFactory(author=user)
        post2 = PostFactory(author=user)
        self.view_service.record_view(
            content_type_model="post", object_id=post1.id, viewer_id=user2.id
        )
        self.view_service.record_view(
            content_type_model="post", object_id=post2.id, viewer_id=user2.id
        )
        analytics = self.analytics_service.get_user_analytics(user_id=user.id)
        assert analytics["post_count"] == 2
        assert analytics["total_views"] == 2
        assert "total_reactions" in analytics
        assert "total_comments" in analytics

    def test_get_user_analytics_no_posts(self, user):
        analytics = self.analytics_service.get_user_analytics(user_id=user.id)
        assert analytics == {
            "post_count": 0,
            "total_views": 0,
            "total_reactions": 0,
            "total_comments": 0,
        }

    def test_get_user_analytics_counts_only_own_posts(self, user, user2):
        from conftest import PostFactory

        PostFactory(author=user)
        PostFactory(author=user2)
        analytics = self.analytics_service.get_user_analytics(user_id=user.id)
        assert analytics["post_count"] == 1
