from __future__ import annotations
from typing import Any
from rest_framework import serializers
from apps.accounts.models import User
from apps.admin_panel.models import AdminLog, AdminRole, BoostTier
from apps.analytics.models import BoostAnalyticSnapshot, PostBoost
from apps.bible.models import (
    SegregatedChapter,
    SegregatedPage,
    SegregatedPageComment,
    SegregatedSection,
)

from apps.common.serializers import BaseModelSerializer, BaseTimestampedSerializer
from apps.notifications.models import Notification
from apps.shop.models import Product, Purchase
from apps.social.models import Report
from apps.verse_of_day.models import VerseFallbackPool, VerseOfDay


class _MinimalUserSerializer(serializers.Serializer):
    """Inline read-only user representation used throughout admin serializers."""

    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)


class _MinimalPostSerializer(serializers.Serializer):
    """Inline read-only post preview used in boost serializers."""

    id = serializers.UUIDField(read_only=True)
    text_content_preview = serializers.SerializerMethodField()
    author_full_name = serializers.CharField(source="author.full_name", read_only=True)

    def get_text_content_preview(self, obj: Any) -> str:
        text: str = obj.text_content or ""

        return text[:120] + ("..." if len(text) > 120 else "")


class _MinimalProductSerializer(serializers.Serializer):
    """Inline read-only product representation."""

    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)


class DashboardOverviewSerializer(serializers.Serializer):
    """High-level KPI numbers for the admin dashboard landing page."""

    total_users = serializers.IntegerField(read_only=True)
    daily_active_users = serializers.IntegerField(read_only=True)
    new_signups_today = serializers.IntegerField(read_only=True)
    new_signups_week = serializers.IntegerField(read_only=True)
    total_posts = serializers.IntegerField(read_only=True)
    total_prayers = serializers.IntegerField(read_only=True)
    active_boosts_count = serializers.IntegerField(read_only=True)
    total_purchases = serializers.IntegerField(read_only=True)
    total_downloads = serializers.IntegerField(read_only=True)


class UserGrowthPointSerializer(serializers.Serializer):
    """Single data point for user-growth chart."""

    date = serializers.DateField()
    count = serializers.IntegerField()


class AdminUserListSerializer(BaseModelSerializer):
    """Compact user representation for paginated admin list views."""

    class Meta:
        model = User
        fields: list[str] = [
            "id",
            "email",
            "full_name",
            "profile_photo",
            "country",
            "preferred_language",
            "gender",
            "is_active",
            "is_email_verified",
            "is_staff",
            "date_joined",
        ]
        read_only_fields: list[str] = fields


class AdminUserDetailSerializer(BaseModelSerializer):
    """Full user profile with computed aggregates for admin detail view."""

    age = serializers.IntegerField(read_only=True)
    follower_count = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)
    post_count = serializers.IntegerField(read_only=True)
    prayer_count = serializers.IntegerField(read_only=True)
    admin_role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields: list[str] = [
            "id",
            "email",
            "full_name",
            "date_of_birth",
            "gender",
            "preferred_language",
            "country",
            "phone_number",
            "profile_photo",
            "bio",
            "is_active",
            "is_staff",
            "is_email_verified",
            "date_joined",
            "age",
            "follower_count",
            "following_count",
            "post_count",
            "prayer_count",
            "admin_role",
        ]
        read_only_fields: list[str] = fields

    def get_admin_role(self, obj: User) -> str | None:
        role: AdminRole | None = getattr(obj, "admin_role", None)

        if role is None:
            try:
                role = obj.admin_role

            except AdminRole.DoesNotExist:
                return None

        return role.get_role_display() if role else None


class AdminUserSuspendSerializer(serializers.Serializer):
    """Payload for suspending a user account."""

    reason = serializers.CharField(required=False, allow_blank=True, default="")


class AdminCreateAdminSerializer(serializers.Serializer):
    """Payload for creating a new admin staff user."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=150)
    date_of_birth = serializers.DateField()
    gender = serializers.ChoiceField(choices=User.Gender.choices)
    role = serializers.ChoiceField(choices=AdminRole.RoleType.choices)


class AdminRoleUpdateSerializer(serializers.Serializer):
    """Payload for changing an existing admin user's role."""

    role = serializers.ChoiceField(choices=AdminRole.RoleType.choices)


class AdminRoleSerializer(BaseModelSerializer):
    """Read representation of an AdminRole assignment."""

    user = _MinimalUserSerializer(read_only=True)

    class Meta:
        model = AdminRole
        fields: list[str] = ["id", "user", "role", "created_at"]
        read_only_fields: list[str] = fields


class AdminReportListSerializer(BaseTimestampedSerializer):
    """Report list with inline reporter / reviewer previews."""

    reporter = _MinimalUserSerializer(read_only=True)

    content_type = serializers.CharField(source="content_type.model", read_only=True)

    reviewed_by = _MinimalUserSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Report
        fields: list[str] = [
            "id",
            "reporter",
            "content_type",
            "object_id",
            "reason",
            "description",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields: list[str] = fields


class AdminReportDetailSerializer(BaseTimestampedSerializer):
    """Report detail — extends list with a preview of the reported content."""

    reporter = _MinimalUserSerializer(read_only=True)

    content_type = serializers.CharField(source="content_type.model", read_only=True)

    reviewed_by = _MinimalUserSerializer(read_only=True, allow_null=True)

    content_preview = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields: list[str] = [
            "id",
            "reporter",
            "content_type",
            "object_id",
            "reason",
            "description",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
            "content_preview",
        ]
        read_only_fields: list[str] = fields

    def get_content_preview(self, obj: Report) -> str | None:
        """Return the text/title of the reported object, if available."""

        try:
            target = obj.content_object

        except Exception:
            return None

        if target is None:
            return None

        for attr in ("text_content", "title", "text", "full_name"):
            value = getattr(target, attr, None)

            if value:
                text = str(value)

                return text[:200] + ("..." if len(text) > 200 else "")

        return None


class AdminReportActionSerializer(serializers.Serializer):
    """Payload for taking action on a report."""

    action = serializers.ChoiceField(
        choices=[
            ("dismiss", "Dismiss"),
            ("remove_content", "Remove Content"),
            ("warn", "Warn"),
            ("suspend", "Suspend"),
        ]
    )

    warning_message = serializers.CharField(
        required=False, allow_blank=True, default=""
    )


class AdminVerseOfDaySerializer(BaseTimestampedSerializer):
    """Full read representation of a VerseOfDay entry."""

    class Meta:
        model = VerseOfDay
        fields: list[str] = [
            "id",
            "bible_reference",
            "verse_text",
            "background_image",
            "display_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields: list[str] = fields


class AdminVerseOfDayCreateSerializer(serializers.Serializer):
    """Payload for scheduling a new Verse of the Day."""

    bible_reference = serializers.CharField(max_length=100)
    verse_text = serializers.CharField()
    display_date = serializers.DateField()
    background_image = serializers.ImageField(required=False)


class AdminVerseOfDayUpdateSerializer(serializers.Serializer):
    """Payload for updating an existing Verse of the Day (all fields optional)."""

    bible_reference = serializers.CharField(max_length=100, required=False)
    verse_text = serializers.CharField(required=False)
    display_date = serializers.DateField(required=False)
    background_image = serializers.ImageField(required=False)
    is_active = serializers.BooleanField(required=False)


class AdminVerseFallbackSerializer(BaseTimestampedSerializer):
    """Full read representation of a VerseFallbackPool entry."""

    class Meta:
        model = VerseFallbackPool
        fields: list[str] = [
            "id",
            "bible_reference",
            "verse_text",
            "background_image",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields: list[str] = fields


class AdminVerseFallbackCreateSerializer(serializers.Serializer):
    """Payload for adding a verse to the fallback pool."""

    bible_reference = serializers.CharField(max_length=100)
    verse_text = serializers.CharField()
    background_image = serializers.ImageField(required=False)


class AdminVerseFallbackUpdateSerializer(serializers.Serializer):
    """Payload for updating a fallback pool verse (all fields optional)."""

    bible_reference = serializers.CharField(max_length=100, required=False)
    verse_text = serializers.CharField(required=False)
    background_image = serializers.ImageField(required=False)
    is_active = serializers.BooleanField(required=False)


class _VerseBulkItemSerializer(serializers.Serializer):
    """Single item inside a bulk-create payload."""

    bible_reference = serializers.CharField(max_length=100)
    verse_text = serializers.CharField()
    display_date = serializers.DateField()


class AdminVerseBulkCreateSerializer(serializers.Serializer):
    """Payload for bulk-creating multiple Verse of the Day entries."""

    verses = serializers.ListField(child=_VerseBulkItemSerializer())


class AdminSectionSerializer(BaseTimestampedSerializer):
    """Segregated Bible section with chapter count."""

    chapter_count = serializers.SerializerMethodField()

    class Meta:
        model = SegregatedSection
        fields: list[str] = [
            "id",
            "title",
            "age_min",
            "age_max",
            "order",
            "is_active",
            "created_at",
            "updated_at",
            "chapter_count",
        ]
        read_only_fields: list[str] = fields

    def get_chapter_count(self, obj: SegregatedSection) -> int:
        return obj.chapters.count()


class AdminSectionCreateSerializer(serializers.Serializer):
    """Payload for creating a new segregated section."""

    title = serializers.CharField(max_length=255)
    age_min = serializers.IntegerField(min_value=0)
    age_max = serializers.IntegerField(min_value=0)
    order = serializers.IntegerField(default=0)


class AdminSectionUpdateSerializer(serializers.Serializer):
    """Payload for updating a section (all fields optional)."""

    title = serializers.CharField(max_length=255, required=False)
    age_min = serializers.IntegerField(min_value=0, required=False)
    age_max = serializers.IntegerField(min_value=0, required=False)
    order = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)


class AdminChapterSerializer(BaseTimestampedSerializer):
    """Segregated Bible chapter with page count and parent section title."""

    page_count = serializers.SerializerMethodField()
    section_title = serializers.CharField(source="section.title", read_only=True)

    class Meta:
        model = SegregatedChapter
        fields: list[str] = [
            "id",
            "section",
            "title",
            "order",
            "is_active",
            "created_at",
            "updated_at",
            "page_count",
            "section_title",
        ]
        read_only_fields: list[str] = fields

    def get_page_count(self, obj: SegregatedChapter) -> int:
        return obj.pages.count()


class AdminChapterCreateSerializer(serializers.Serializer):
    """Payload for creating a new chapter."""

    section_id = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    order = serializers.IntegerField(default=0)


class AdminChapterUpdateSerializer(serializers.Serializer):
    """Payload for updating a chapter (all fields optional)."""

    title = serializers.CharField(max_length=255, required=False)
    order = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)


class AdminChapterReorderSerializer(serializers.Serializer):
    """Payload for reordering chapters via drag-and-drop."""

    ordered_ids = serializers.ListField(child=serializers.UUIDField())


class AdminPageSerializer(BaseTimestampedSerializer):
    """Segregated Bible page with parent chapter and section titles."""

    chapter_title = serializers.CharField(source="chapter.title", read_only=True)
    section_title = serializers.CharField(
        source="chapter.section.title", read_only=True
    )

    class Meta:
        model = SegregatedPage
        fields: list[str] = [
            "id",
            "chapter",
            "title",
            "content",
            "youtube_url",
            "order",
            "is_active",
            "created_at",
            "updated_at",
            "chapter_title",
            "section_title",
        ]
        read_only_fields: list[str] = fields


class AdminPageCreateSerializer(serializers.Serializer):
    """Payload for creating a new page."""

    chapter_id = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    content = serializers.CharField()
    youtube_url = serializers.URLField(required=False, allow_blank=True, default="")
    order = serializers.IntegerField(default=0)


class AdminPageUpdateSerializer(serializers.Serializer):
    """Payload for updating a page (all fields optional)."""

    title = serializers.CharField(max_length=255, required=False)
    content = serializers.CharField(required=False)
    youtube_url = serializers.URLField(required=False, allow_blank=True)
    order = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)


class AdminProductSerializer(BaseTimestampedSerializer):
    """Full read representation of a shop product."""

    class Meta:
        model = Product
        fields: list[str] = [
            "id",
            "title",
            "description",
            "cover_image",
            "product_file",
            "price_tier",
            "is_free",
            "category",
            "is_active",
            "download_count",
            "apple_product_id",
            "google_product_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields: list[str] = fields


class AdminProductCreateSerializer(serializers.Serializer):
    """Payload for creating a new product."""

    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    cover_image = serializers.ImageField()
    product_file = serializers.FileField()
    category = serializers.CharField(max_length=100)
    is_free = serializers.BooleanField(default=False)
    price_tier = serializers.CharField(max_length=50, required=False, default="")
    apple_product_id = serializers.CharField(max_length=100, required=False, default="")
    google_product_id = serializers.CharField(
        max_length=100, required=False, default=""
    )


class AdminProductUpdateSerializer(serializers.Serializer):
    """Payload for updating a product (all fields optional)."""

    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False)
    cover_image = serializers.ImageField(required=False)
    product_file = serializers.FileField(required=False)
    category = serializers.CharField(max_length=100, required=False)
    is_free = serializers.BooleanField(required=False)
    price_tier = serializers.CharField(max_length=50, required=False)
    apple_product_id = serializers.CharField(max_length=100, required=False)
    google_product_id = serializers.CharField(max_length=100, required=False)
    is_active = serializers.BooleanField(required=False)


class AdminProductStatsSerializer(serializers.Serializer):
    """Aggregate stats for a single product."""

    purchase_count = serializers.IntegerField(read_only=True)
    download_count = serializers.IntegerField(read_only=True)


class AdminPurchaseSerializer(BaseModelSerializer):
    """Purchase record with nested user and product previews."""

    user = _MinimalUserSerializer(read_only=True)

    product = _MinimalProductSerializer(read_only=True)

    class Meta:
        model = Purchase
        fields: list[str] = [
            "id",
            "user",
            "product",
            "platform",
            "transaction_id",
            "is_validated",
            "created_at",
        ]
        read_only_fields: list[str] = fields


class AdminBoostSerializer(BaseModelSerializer):
    """PostBoost with nested post preview and user info."""

    post = _MinimalPostSerializer(read_only=True)

    user = _MinimalUserSerializer(read_only=True)

    class Meta:
        model = PostBoost
        fields: list[str] = [
            "id",
            "post",
            "user",
            "tier",
            "platform",
            "transaction_id",
            "duration_days",
            "is_active",
            "activated_at",
            "expires_at",
            "created_at",
        ]
        read_only_fields: list[str] = fields


class AdminBoostTierSerializer(BaseTimestampedSerializer):
    """Full read representation of a BoostTier."""

    class Meta:
        model = BoostTier
        fields: list[str] = [
            "id",
            "name",
            "apple_product_id",
            "google_product_id",
            "duration_days",
            "display_price",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields: list[str] = fields


class AdminBoostTierCreateSerializer(serializers.Serializer):
    """Payload for creating a new boost tier."""

    name = serializers.CharField(max_length=100)
    apple_product_id = serializers.CharField(max_length=100)
    google_product_id = serializers.CharField(max_length=100)
    duration_days = serializers.IntegerField(min_value=1)
    display_price = serializers.CharField(max_length=20)


class AdminBoostTierUpdateSerializer(serializers.Serializer):
    """Payload for updating a boost tier (all fields optional)."""

    name = serializers.CharField(max_length=100, required=False)
    apple_product_id = serializers.CharField(max_length=100, required=False)
    google_product_id = serializers.CharField(max_length=100, required=False)
    duration_days = serializers.IntegerField(min_value=1, required=False)
    display_price = serializers.CharField(max_length=20, required=False)
    is_active = serializers.BooleanField(required=False)


class AdminBoostRevenueSerializer(serializers.Serializer):
    """Aggregate boost revenue data."""

    total_boosts = serializers.IntegerField(read_only=True)
    active_boosts = serializers.IntegerField(read_only=True)
    revenue_by_tier = serializers.ListField(read_only=True)


class AdminBoostSnapshotSerializer(BaseModelSerializer):
    """Full read representation of a BoostAnalyticSnapshot."""

    class Meta:
        model = BoostAnalyticSnapshot
        fields: list[str] = [
            "id",
            "boost",
            "impressions",
            "reach",
            "engagement_rate",
            "link_clicks",
            "profile_visits",
            "snapshot_date",
            "created_at",
        ]
        read_only_fields: list[str] = fields


class AdminBroadcastCreateSerializer(serializers.Serializer):
    """Payload for sending a system broadcast notification."""

    title = serializers.CharField(max_length=255)
    body = serializers.CharField()
    filters = serializers.DictField(
        required=False,
        default=dict,
        help_text=(
            "Optional targeting filters: country (str), language (str), "
            "age_min (int), age_max (int)."
        ),
    )


class AdminBroadcastSerializer(BaseModelSerializer):
    """Read representation of a broadcast notification."""

    recipient_count = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields: list[str] = [
            "id",
            "notification_type",
            "title",
            "body",
            "data",
            "created_at",
            "recipient_count",
        ]
        read_only_fields: list[str] = fields

    def get_recipient_count(self, obj: Notification) -> int:
        """Return total recipients for this broadcast.
        Expects the view to annotate *recipient_count* or we fall back to
        counting notifications sharing the same title and timestamp.
        """
        count: int | None = getattr(obj, "_recipient_count", None)

        if count is not None:
            return count

        return Notification.objects.filter(
            notification_type=Notification.NotificationType.SYSTEM_BROADCAST,
            title=obj.title,
            created_at=obj.created_at,
        ).count()


class AdminDemographicsSerializer(serializers.Serializer):
    """User demographics breakdown for the analytics dashboard."""

    age_distribution = serializers.DictField(read_only=True)
    gender_split = serializers.DictField(read_only=True)
    top_countries = serializers.ListField(read_only=True)
    language_distribution = serializers.DictField(read_only=True)


class AdminContentEngagementSerializer(serializers.Serializer):
    """Daily content engagement data point."""

    date = serializers.DateField()
    posts = serializers.IntegerField()
    prayers = serializers.IntegerField()
    reactions = serializers.IntegerField()
    comments = serializers.IntegerField()


class AdminShopRevenueSerializer(serializers.Serializer):
    """Daily shop revenue data point."""

    date = serializers.DateField()
    purchase_count = serializers.IntegerField()
    product_breakdown = serializers.ListField(read_only=True)


class AdminPageCommentSerializer(BaseTimestampedSerializer):
    """Admin view of a user comment on a Bible page."""

    user = _MinimalUserSerializer(read_only=True)

    page_title = serializers.CharField(source="page.title", read_only=True)
    chapter_title = serializers.CharField(source="page.chapter.title", read_only=True)
    section_title = serializers.CharField(
        source="page.chapter.section.title", read_only=True
    )

    class Meta:
        model = SegregatedPageComment
        fields: list[str] = [
            "id",
            "user",
            "page",
            "page_title",
            "chapter_title",
            "section_title",
            "content",
            "created_at",
            "updated_at",
        ]
        read_only_fields: list[str] = fields


class AdminPageLikeStatsSerializer(serializers.Serializer):
    """Aggregated like statistics for a Bible page."""

    page_id = serializers.UUIDField(read_only=True)
    page_title = serializers.CharField(read_only=True)
    chapter_title = serializers.CharField(read_only=True)
    section_title = serializers.CharField(read_only=True)
    like_count = serializers.IntegerField(read_only=True)


class AdminBibleReadingStatsSerializer(serializers.Serializer):
    """Bible reading statistics."""

    total_bible_views = serializers.IntegerField(read_only=True)
    views_breakdown = serializers.ListField(read_only=True)


class AdminLogSerializer(BaseModelSerializer):
    """Audit log entry with nested admin user preview."""

    admin_user = _MinimalUserSerializer(read_only=True)

    class Meta:
        model = AdminLog
        fields: list[str] = [
            "id",
            "admin_user",
            "action",
            "target_model",
            "target_id",
            "detail",
            "metadata",
            "created_at",
        ]
        read_only_fields: list[str] = fields
