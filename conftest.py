"""Root conftest — factories & shared fixtures for the entire test suite."""

from __future__ import annotations

import datetime
import uuid

import factory
import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "accounts.User"
        skip_postgeneration_save = True

    email = factory.LazyAttribute(lambda o: f"{uuid.uuid4().hex[:8]}@test.com")
    full_name = factory.Faker("name")
    date_of_birth = factory.LazyFunction(lambda: datetime.date(2000, 1, 15))
    gender = "male"
    preferred_language = "en"
    country = "US"
    is_active = True
    is_email_verified = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or "TestPass1!")
        if create:
            self.save(update_fields=["password"])


class OTPTokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "accounts.OTPToken"

    user = factory.SubFactory(UserFactory)
    hashed_code = factory.LazyFunction(lambda: "dummyhash")
    purpose = "register"
    expires_at = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(minutes=10))
    used = False
    attempts = 0


class FollowRelationshipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "accounts.FollowRelationship"

    follower = factory.SubFactory(UserFactory)
    following = factory.SubFactory(UserFactory)


class BlockRelationshipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "accounts.BlockRelationship"

    blocker = factory.SubFactory(UserFactory)
    blocked = factory.SubFactory(UserFactory)


class PostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "social.Post"

    author = factory.SubFactory(UserFactory)
    text_content = factory.Faker("sentence")


class PrayerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "social.Prayer"

    author = factory.SubFactory(UserFactory)
    title = factory.Faker("sentence", nb_words=4)
    description = factory.Faker("paragraph")


class CommentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "social.Comment"

    user = factory.SubFactory(UserFactory)
    content_type = factory.LazyFunction(
        lambda: ContentType.objects.get(app_label="social", model="post")
    )
    object_id = factory.LazyAttribute(lambda o: uuid.uuid4())
    text = factory.Faker("sentence")


class ReplyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "social.Reply"

    user = factory.SubFactory(UserFactory)
    comment = factory.SubFactory(CommentFactory)
    text = factory.Faker("sentence")


class ReactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "social.Reaction"

    user = factory.SubFactory(UserFactory)
    content_type = factory.LazyFunction(
        lambda: ContentType.objects.get(app_label="social", model="post")
    )
    object_id = factory.LazyAttribute(lambda o: uuid.uuid4())
    emoji_type = "heart"


class ReportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "social.Report"

    reporter = factory.SubFactory(UserFactory)
    content_type = factory.LazyFunction(
        lambda: ContentType.objects.get(app_label="social", model="post")
    )
    object_id = factory.LazyAttribute(lambda o: uuid.uuid4())
    reason = "spam"


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "notifications.Notification"

    recipient = factory.SubFactory(UserFactory)
    sender = factory.SubFactory(UserFactory)
    notification_type = "follow"
    title = factory.Faker("sentence", nb_words=4)
    body = factory.Faker("sentence")
    is_read = False


class DevicePushTokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "notifications.DevicePushToken"

    user = factory.SubFactory(UserFactory)
    token = factory.LazyFunction(lambda: uuid.uuid4().hex)
    platform = "ios"
    is_active = True


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "shop.Product"

    title = factory.Faker("sentence", nb_words=3)
    description = factory.Faker("paragraph")
    cover_image = factory.django.ImageField(filename="cover.jpg")
    product_file = factory.django.FileField(filename="product.pdf")
    price_tier = "tier_1"
    is_free = False
    category = "books"
    is_active = True


class PurchaseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "shop.Purchase"

    user = factory.SubFactory(UserFactory)
    product = factory.SubFactory(ProductFactory)
    platform = "ios"
    receipt_data = "test-receipt-data"
    transaction_id = factory.LazyFunction(lambda: f"txn_{uuid.uuid4().hex[:16]}")
    is_validated = True


class DownloadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "shop.Download"

    user = factory.SubFactory(UserFactory)
    product = factory.SubFactory(ProductFactory)
    purchase = None


class PostBoostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "analytics.PostBoost"

    post = factory.SubFactory(PostFactory)
    user = factory.LazyAttribute(lambda o: o.post.author)
    tier = "boost_tier_1"
    platform = "ios"
    transaction_id = factory.LazyFunction(lambda: f"boost_{uuid.uuid4().hex[:16]}")
    duration_days = 7
    is_active = True
    activated_at = factory.LazyFunction(timezone.now)
    expires_at = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(days=7))


class BoostAnalyticSnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "analytics.BoostAnalyticSnapshot"

    boost = factory.SubFactory(PostBoostFactory)
    impressions = 100
    reach = 80
    engagement_rate = 3.50
    link_clicks = 10
    profile_visits = 5
    snapshot_date = factory.LazyFunction(lambda: timezone.now().date())


class VerseOfDayFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "verse_of_day.VerseOfDay"

    bible_reference = "John 3:16"
    verse_text = "For God so loved the world..."
    display_date = factory.LazyFunction(lambda: timezone.now().date())
    is_active = True


class VerseFallbackPoolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "verse_of_day.VerseFallbackPool"

    bible_reference = "Psalm 23:1"
    verse_text = "The Lord is my shepherd..."
    is_active = True


class AdminRoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "admin_panel.AdminRole"

    user = factory.SubFactory(UserFactory, is_staff=True)
    role = "super_admin"


class AdminLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "admin_panel.AdminLog"

    admin_user = factory.SubFactory(UserFactory, is_staff=True)
    action = "create"
    target_model = "accounts.User"
    target_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    detail = "Test log entry"


class BoostTierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "admin_panel.BoostTier"

    name = factory.Sequence(lambda n: f"Tier {n}")
    apple_product_id = factory.Sequence(lambda n: f"apple_boost_{n}")
    google_product_id = factory.Sequence(lambda n: f"google_boost_{n}")
    duration_days = 7
    display_price = "$5.00"
    is_active = True


@pytest.fixture
def user(db):
    """Create and return a verified user."""
    return UserFactory()


@pytest.fixture
def user2(db):
    """Create and return a second verified user."""
    return UserFactory()


@pytest.fixture
def admin_user(db):
    """Create and return a staff/admin user."""
    return UserFactory(is_staff=True, is_email_verified=True)


@pytest.fixture
def api_client():
    """Return a DRF APIClient."""
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    """Return an authenticated APIClient (JWT Bearer token)."""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def auth_client_user2(user2):
    """Return an authenticated APIClient for user2."""
    client = APIClient()
    refresh = RefreshToken.for_user(user2)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Return an authenticated APIClient for an admin user."""
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client
