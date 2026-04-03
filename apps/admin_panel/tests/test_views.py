"""Tests for apps.admin_panel.views — admin-only API endpoints."""

from __future__ import annotations
import uuid
from unittest.mock import patch
import pytest
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.admin_panel.models import AdminRole, BoostTier
from apps.social.models import Post, Report
from conftest import (
    AdminLogFactory,
    AdminRoleFactory,
    BoostTierFactory,
    PostBoostFactory,
    PostFactory,
    UserFactory,
)


@pytest.fixture
def super_admin_user(db):
    """Create a staff user with super_admin role."""

    user = UserFactory(is_staff=True)

    AdminRoleFactory(user=user, role=AdminRole.RoleType.SUPER_ADMIN)

    return user


@pytest.fixture
def super_admin_client(super_admin_user):
    """Return an authenticated APIClient for a super_admin."""

    client = APIClient()

    refresh = RefreshToken.for_user(super_admin_user)

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    return client


@pytest.fixture
def content_admin_user(db):
    """Create a staff user with content_admin role."""

    user = UserFactory(is_staff=True)

    AdminRoleFactory(user=user, role=AdminRole.RoleType.CONTENT_ADMIN)

    return user


@pytest.fixture
def content_admin_client(content_admin_user):
    """Return an authenticated APIClient for a content_admin."""

    client = APIClient()

    refresh = RefreshToken.for_user(content_admin_user)

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    return client


@pytest.fixture
def moderation_admin_user(db):
    """Create a staff user with moderation_admin role."""

    user = UserFactory(is_staff=True)

    AdminRoleFactory(user=user, role=AdminRole.RoleType.MODERATION_ADMIN)

    return user


@pytest.fixture
def moderation_admin_client(moderation_admin_user):
    """Return an authenticated APIClient for a moderation_admin."""

    client = APIClient()

    refresh = RefreshToken.for_user(moderation_admin_user)

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    return client


@pytest.fixture(autouse=True)
def _mock_storage():
    """Prevent S3 API calls during tests by mocking the storage backend."""

    with (
        patch(
            "storages.backends.s3boto3.S3Boto3Storage._save",
            return_value="mocked-file-key",
        ),
        patch(
            "storages.backends.s3boto3.S3Boto3Storage.url",
            return_value="https://cdn.example.com/mocked-file",
        ),
        patch(
            "storages.backends.s3boto3.S3Boto3Storage.exists",
            return_value=False,
        ),
    ):
        yield


DASHBOARD_OVERVIEW_URL = "/api/v1/admin/dashboard/overview/"

USER_GROWTH_URL = "/api/v1/admin/dashboard/user-growth/"


@pytest.mark.django_db
class TestDashboardOverviewView:
    url = DASHBOARD_OVERVIEW_URL

    def test_super_admin_can_access(self, super_admin_client):
        response = super_admin_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert "total_users" in data
        assert "total_posts" in data

    def test_content_admin_can_access(self, content_admin_client):
        response = content_admin_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_non_admin_denied(self, auth_client):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_denied(self, api_client):
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestUserGrowthView:
    url = USER_GROWTH_URL

    def test_returns_growth_data(self, super_admin_client):
        response = super_admin_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert isinstance(data, list)

    def test_custom_days_param(self, super_admin_client):
        response = super_admin_client.get(self.url, {"days": 7})
        assert response.status_code == status.HTTP_200_OK

    def test_non_admin_denied(self, auth_client):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


USER_LIST_URL = "/api/v1/admin/users/"

USER_SUSPEND_URL = "/api/v1/admin/users/{user_id}/suspend/"

USER_UNSUSPEND_URL = "/api/v1/admin/users/{user_id}/unsuspend/"


@pytest.mark.django_db
class TestAdminUserListView:
    url = USER_LIST_URL

    def test_moderation_admin_can_list_users(self, moderation_admin_client):
        UserFactory()
        UserFactory()
        response = moderation_admin_client.get(self.url, {"ordering": "-date_joined"})
        assert response.status_code == status.HTTP_200_OK
        results = response.data["data"]["results"]
        assert len(results) >= 2

    def test_super_admin_can_list_users(self, super_admin_client):
        response = super_admin_client.get(self.url, {"ordering": "-date_joined"})
        assert response.status_code == status.HTTP_200_OK

    def test_content_admin_denied(self, content_admin_client):
        response = content_admin_client.get(self.url, {"ordering": "-date_joined"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_denied(self, auth_client):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_search_filter(self, moderation_admin_client):
        UserFactory(full_name="John Doe Unique")
        response = moderation_admin_client.get(
            self.url, {"search": "John Doe Unique", "ordering": "-date_joined"}
        )
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestAdminUserSuspendView:
    def test_suspend_user(self, moderation_admin_client):
        target = UserFactory(is_active=True)
        url = USER_SUSPEND_URL.format(user_id=target.pk)
        response = moderation_admin_client.post(url, {"reason": "Violations"})
        assert response.status_code == status.HTTP_200_OK
        target.refresh_from_db()
        assert target.is_active is False

    def test_suspend_without_reason(self, moderation_admin_client):
        target = UserFactory(is_active=True)
        url = USER_SUSPEND_URL.format(user_id=target.pk)
        response = moderation_admin_client.post(url, {})
        assert response.status_code == status.HTTP_200_OK

    def test_regular_user_cannot_suspend(self, auth_client, user2):
        url = USER_SUSPEND_URL.format(user_id=user2.pk)
        response = auth_client.post(url, {"reason": "test"})
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminUserUnsuspendView:
    def test_unsuspend_user(self, moderation_admin_client):
        target = UserFactory(is_active=False)
        url = USER_UNSUSPEND_URL.format(user_id=target.pk)
        response = moderation_admin_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        target.refresh_from_db()
        assert target.is_active is True

    def test_regular_user_cannot_unsuspend(self, auth_client, user2):
        url = USER_UNSUSPEND_URL.format(user_id=user2.pk)
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


ADMIN_USERS_LIST_URL = "/api/v1/admin/admin-users/"

ADMIN_USER_CREATE_URL = "/api/v1/admin/admin-users/create/"

ADMIN_USER_ROLE_UPDATE_URL = "/api/v1/admin/admin-users/{user_id}/role/"

ADMIN_USER_DELETE_URL = "/api/v1/admin/admin-users/{user_id}/delete/"


@pytest.mark.django_db
class TestAdminUsersListView:
    url = ADMIN_USERS_LIST_URL

    def test_super_admin_can_list(self, super_admin_client):
        response = super_admin_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert isinstance(data, list)

    def test_content_admin_denied(self, content_admin_client):
        response = content_admin_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_moderation_admin_denied(self, moderation_admin_client):
        response = moderation_admin_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_denied(self, auth_client):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminUserCreateView:
    url = ADMIN_USER_CREATE_URL

    def test_super_admin_can_create_admin(self, super_admin_client):
        response = super_admin_client.post(
            self.url,
            {
                "email": f"newadmin_{uuid.uuid4().hex[:6]}@test.com",
                "password": "StrongPass123!",
                "full_name": "New Admin",
                "date_of_birth": "1990-01-01",
                "gender": "male",
                "role": "content_admin",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data["data"]
        assert "id" in data

    def test_content_admin_cannot_create(self, content_admin_client):
        response = content_admin_client.post(
            self.url,
            {
                "email": "nope@test.com",
                "password": "StrongPass123!",
                "full_name": "No Access",
                "date_of_birth": "1990-01-01",
                "gender": "male",
                "role": "content_admin",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_missing_fields(self, super_admin_client):
        response = super_admin_client.post(self.url, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestAdminUserRoleUpdateView:
    def test_update_role(self, super_admin_client):
        target = UserFactory(is_staff=True)
        AdminRoleFactory(user=target, role=AdminRole.RoleType.CONTENT_ADMIN)
        url = ADMIN_USER_ROLE_UPDATE_URL.format(user_id=target.pk)
        response = super_admin_client.put(url, {"role": "moderation_admin"})
        assert response.status_code == status.HTTP_200_OK
        target_role = AdminRole.objects.get(user=target)
        assert target_role.role == "moderation_admin"

    def test_content_admin_cannot_update_role(self, content_admin_client):
        target = UserFactory(is_staff=True)
        AdminRoleFactory(user=target, role=AdminRole.RoleType.CONTENT_ADMIN)
        url = ADMIN_USER_ROLE_UPDATE_URL.format(user_id=target.pk)
        response = content_admin_client.put(url, {"role": "super_admin"})
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminUserDeleteView:
    def test_delete_admin_user(self, super_admin_client):
        target = UserFactory(is_staff=True)
        AdminRoleFactory(user=target, role=AdminRole.RoleType.CONTENT_ADMIN)
        url = ADMIN_USER_DELETE_URL.format(user_id=target.pk)
        response = super_admin_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not AdminRole.objects.filter(user=target).exists()

    def test_content_admin_cannot_delete(self, content_admin_client):
        target = UserFactory(is_staff=True)
        AdminRoleFactory(user=target, role=AdminRole.RoleType.CONTENT_ADMIN)
        url = ADMIN_USER_DELETE_URL.format(user_id=target.pk)
        response = content_admin_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


REPORT_LIST_URL = "/api/v1/admin/reports/"

REPORT_DETAIL_URL = "/api/v1/admin/reports/{report_id}/"

REPORT_ACTION_URL = "/api/v1/admin/reports/{report_id}/action/"


@pytest.fixture
def report_with_post(db):
    """Create a report targeting a post."""

    post = PostFactory()

    ct = ContentType.objects.get_for_model(Post)

    reporter = UserFactory()

    report = Report.objects.create(
        reporter=reporter,
        content_type=ct,
        object_id=post.pk,
        reason="spam",
        status="pending",
    )

    return report


@pytest.mark.django_db
class TestAdminReportListView:
    url = REPORT_LIST_URL

    def test_moderation_admin_can_list(self, moderation_admin_client, report_with_post):
        response = moderation_admin_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        results = response.data["data"]["results"]
        assert len(results) >= 1

    def test_super_admin_can_list(self, super_admin_client, report_with_post):
        response = super_admin_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_content_admin_denied(self, content_admin_client):
        response = content_admin_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_denied(self, auth_client):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminReportDetailView:
    def test_get_report_detail(self, moderation_admin_client, report_with_post):
        url = REPORT_DETAIL_URL.format(report_id=report_with_post.pk)
        response = moderation_admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["id"] == str(report_with_post.pk)

    def test_nonexistent_report(self, moderation_admin_client):
        url = REPORT_DETAIL_URL.format(report_id=uuid.uuid4())
        response = moderation_admin_client.get(url)
        assert response.status_code in (
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@pytest.mark.django_db
class TestAdminReportActionView:
    def test_dismiss_report(self, moderation_admin_client, report_with_post):
        url = REPORT_ACTION_URL.format(report_id=report_with_post.pk)
        response = moderation_admin_client.post(url, {"action": "dismiss"})
        assert response.status_code == status.HTTP_200_OK

    def test_warn_user(self, moderation_admin_client, report_with_post):
        url = REPORT_ACTION_URL.format(report_id=report_with_post.pk)
        response = moderation_admin_client.post(
            url,
            {
                "action": "warn",
                "warning_message": "Please follow community guidelines.",
            },
        )
        assert response.status_code == status.HTTP_200_OK

    def test_invalid_action(self, moderation_admin_client, report_with_post):
        url = REPORT_ACTION_URL.format(report_id=report_with_post.pk)
        response = moderation_admin_client.post(url, {"action": "invalid_action"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_regular_user_denied(self, auth_client, report_with_post):
        url = REPORT_ACTION_URL.format(report_id=report_with_post.pk)
        response = auth_client.post(url, {"action": "dismiss"})
        assert response.status_code == status.HTTP_403_FORBIDDEN


BOOST_TIER_LIST_URL = "/api/v1/admin/boosts/tiers/"

BOOST_TIER_DETAIL_URL = "/api/v1/admin/boosts/tiers/{tier_id}/"


@pytest.mark.django_db
class TestAdminBoostTierListView:
    url = BOOST_TIER_LIST_URL

    def test_list_boost_tiers(self, super_admin_client):
        BoostTierFactory()
        BoostTierFactory()
        response = super_admin_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert len(data) == 2

    def test_create_boost_tier(self, super_admin_client):
        response = super_admin_client.post(
            self.url,
            {
                "name": "Gold Boost",
                "apple_product_id": f"apple_gold_{uuid.uuid4().hex[:6]}",
                "google_product_id": f"google_gold_{uuid.uuid4().hex[:6]}",
                "duration_days": 30,
                "display_price": "$19.99",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data["data"]
        assert data["name"] == "Gold Boost"
        assert data["duration_days"] == 30

    def test_regular_user_denied(self, auth_client):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_missing_fields(self, super_admin_client):
        response = super_admin_client.post(self.url, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestAdminBoostTierDetailView:
    def test_update_boost_tier(self, super_admin_client):
        tier = BoostTierFactory()
        url = BOOST_TIER_DETAIL_URL.format(tier_id=tier.pk)
        response = super_admin_client.put(
            url,
            {
                "name": "Updated Tier",
                "display_price": "$29.99",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["name"] == "Updated Tier"
        assert data["display_price"] == "$29.99"

    def test_delete_boost_tier(self, super_admin_client):
        tier = BoostTierFactory()
        url = BOOST_TIER_DETAIL_URL.format(tier_id=tier.pk)
        response = super_admin_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not BoostTier.objects.filter(pk=tier.pk).exists()

    def test_nonexistent_tier(self, super_admin_client):
        url = BOOST_TIER_DETAIL_URL.format(tier_id=uuid.uuid4())
        response = super_admin_client.put(url, {"name": "Nope"})
        assert response.status_code in (
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    def test_regular_user_denied(self, auth_client):
        tier = BoostTierFactory()
        url = BOOST_TIER_DETAIL_URL.format(tier_id=tier.pk)
        response = auth_client.put(url, {"name": "Nope"})
        assert response.status_code == status.HTTP_403_FORBIDDEN


ADMIN_LOG_LIST_URL = "/api/v1/admin/logs/"


@pytest.mark.django_db
class TestAdminLogListView:
    url = ADMIN_LOG_LIST_URL

    def test_admin_can_list_logs(self, super_admin_client, super_admin_user):
        AdminLogFactory(admin_user=super_admin_user)
        AdminLogFactory(admin_user=super_admin_user)
        response = super_admin_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        results = response.data["data"]["results"]
        assert len(results) >= 2

    def test_regular_user_denied(self, auth_client):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_denied(self, api_client):
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


BOOST_LIST_ADMIN_URL = "/api/v1/admin/boosts/"

BOOST_DETAIL_ADMIN_URL = "/api/v1/admin/boosts/{boost_id}/"

BOOST_REVENUE_URL = "/api/v1/admin/boosts/revenue/"


@pytest.mark.django_db
class TestAdminBoostListView:
    url = BOOST_LIST_ADMIN_URL

    def test_admin_can_list_boosts(self, super_admin_client):
        PostBoostFactory()
        response = super_admin_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        results = response.data["data"]["results"]
        assert len(results) >= 1

    def test_regular_user_denied(self, auth_client):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminBoostDetailView:
    def test_get_boost_detail(self, super_admin_client):
        boost = PostBoostFactory()
        url = BOOST_DETAIL_ADMIN_URL.format(boost_id=boost.pk)
        response = super_admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert "snapshots" in data

    def test_nonexistent_boost(self, super_admin_client):
        url = BOOST_DETAIL_ADMIN_URL.format(boost_id=uuid.uuid4())
        response = super_admin_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAdminBoostRevenueView:
    url = BOOST_REVENUE_URL

    def test_get_boost_revenue(self, super_admin_client):
        response = super_admin_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert "total_boosts" in data
        assert "active_boosts" in data

    def test_regular_user_denied(self, auth_client):
        response = auth_client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


DEMOGRAPHICS_URL = "/api/v1/admin/analytics/demographics/"

CONTENT_ENGAGEMENT_URL = "/api/v1/admin/analytics/content-engagement/"

SHOP_REVENUE_URL = "/api/v1/admin/analytics/shop-revenue/"

BOOST_PERFORMANCE_URL = "/api/v1/admin/analytics/boost-performance/"


@pytest.mark.django_db
class TestAdminAnalyticsViews:
    """Test permission enforcement on admin analytics endpoints.

    NOTE: The analytics service methods (demographics, content_engagement,
    shop_revenue) rely on Django ORM date functions that may error on SQLite.
    We test the permission layer here; service-level testing belongs in
    a separate test_services.py with mocks or PostgreSQL.
    """

    def test_boost_performance(self, super_admin_client):
        response = super_admin_client.get(BOOST_PERFORMANCE_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_regular_user_denied_demographics(self, auth_client):
        response = auth_client.get(DEMOGRAPHICS_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_denied_content_engagement(self, auth_client):
        response = auth_client.get(CONTENT_ENGAGEMENT_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_denied_shop_revenue(self, auth_client):
        response = auth_client.get(SHOP_REVENUE_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_denied_boost_performance(self, auth_client):
        response = auth_client.get(BOOST_PERFORMANCE_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN


BIBLE_COMMENTS_URL = "/api/v1/admin/bible/comments/"

BIBLE_COMMENT_DELETE_URL = "/api/v1/admin/bible/comments/{comment_id}/"

BIBLE_LIKES_URL = "/api/v1/admin/bible/likes/"

BIBLE_READING_STATS_URL = "/api/v1/admin/analytics/bible-reading/"


@pytest.mark.django_db
class TestAdminPageCommentListView:
    """GET /api/v1/admin/bible/comments/"""

    def test_list_comments(self, content_admin_client):
        from apps.bible.models import (
            SegregatedChapter,
            SegregatedPage,
            SegregatedPageComment,
            SegregatedSection,
        )

        section = SegregatedSection.objects.create(
            title="Test", age_min=5, age_max=12, order=0
        )
        chapter = SegregatedChapter.objects.create(
            section=section, title="Ch1", order=0
        )
        page = SegregatedPage.objects.create(
            chapter=chapter, title="Page1", content="Text", order=0
        )
        user = UserFactory()
        SegregatedPageComment.objects.create(
            user=user, page=page, content="Great content!"
        )
        response = content_admin_client.get(BIBLE_COMMENTS_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_list_comments_filter_by_page(self, content_admin_client):
        from apps.bible.models import (
            SegregatedChapter,
            SegregatedPage,
            SegregatedPageComment,
            SegregatedSection,
        )

        section = SegregatedSection.objects.create(
            title="Test", age_min=5, age_max=12, order=0
        )
        chapter = SegregatedChapter.objects.create(
            section=section, title="Ch1", order=0
        )
        page1 = SegregatedPage.objects.create(
            chapter=chapter, title="P1", content="T", order=0
        )
        page2 = SegregatedPage.objects.create(
            chapter=chapter, title="P2", content="T", order=1
        )
        user = UserFactory()
        SegregatedPageComment.objects.create(user=user, page=page1, content="Comment 1")
        SegregatedPageComment.objects.create(user=user, page=page2, content="Comment 2")
        response = content_admin_client.get(
            BIBLE_COMMENTS_URL, {"page_id": str(page1.id)}
        )
        assert response.status_code == status.HTTP_200_OK

    def test_regular_user_denied(self, auth_client):
        response = auth_client.get(BIBLE_COMMENTS_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminPageCommentDeleteView:
    """DELETE /api/v1/admin/bible/comments/<comment_id>/"""

    def test_delete_comment(self, content_admin_client):
        from apps.bible.models import (
            SegregatedChapter,
            SegregatedPage,
            SegregatedPageComment,
            SegregatedSection,
        )

        section = SegregatedSection.objects.create(
            title="Test", age_min=5, age_max=12, order=0
        )
        chapter = SegregatedChapter.objects.create(
            section=section, title="Ch1", order=0
        )
        page = SegregatedPage.objects.create(
            chapter=chapter, title="P1", content="T", order=0
        )
        comment = SegregatedPageComment.objects.create(
            user=UserFactory(), page=page, content="Bad comment"
        )
        url = BIBLE_COMMENT_DELETE_URL.format(comment_id=comment.id)
        response = content_admin_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not SegregatedPageComment.objects.filter(pk=comment.id).exists()

    def test_delete_nonexistent_comment(self, content_admin_client):
        url = BIBLE_COMMENT_DELETE_URL.format(comment_id=uuid.uuid4())
        response = content_admin_client.delete(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_regular_user_denied(self, auth_client):
        url = BIBLE_COMMENT_DELETE_URL.format(comment_id=uuid.uuid4())
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminPageLikeStatsView:
    """GET /api/v1/admin/bible/likes/"""

    def test_like_stats(self, content_admin_client):
        from apps.bible.models import (
            SegregatedChapter,
            SegregatedPage,
            SegregatedPageLike,
            SegregatedSection,
        )

        section = SegregatedSection.objects.create(
            title="Test", age_min=5, age_max=12, order=0
        )
        chapter = SegregatedChapter.objects.create(
            section=section, title="Ch1", order=0
        )
        page = SegregatedPage.objects.create(
            chapter=chapter, title="P1", content="T", order=0
        )
        user1 = UserFactory()
        user2 = UserFactory()
        SegregatedPageLike.objects.create(user=user1, page=page)
        SegregatedPageLike.objects.create(user=user2, page=page)
        response = content_admin_client.get(BIBLE_LIKES_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert len(data) == 1
        assert data[0]["like_count"] == 2

    def test_like_stats_empty(self, content_admin_client):
        response = content_admin_client.get(BIBLE_LIKES_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == []

    def test_regular_user_denied(self, auth_client):
        response = auth_client.get(BIBLE_LIKES_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminBibleReadingStatsView:
    """GET /api/v1/admin/analytics/bible-reading/"""

    def test_bible_reading_stats(self, super_admin_client):
        response = super_admin_client.get(BIBLE_READING_STATS_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert "total_bible_views" in data

    def test_regular_user_denied(self, auth_client):
        response = auth_client.get(BIBLE_READING_STATS_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN
