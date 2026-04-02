from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from apps.common.models import CreatedAtModel
from apps.social.models import Post


class PostView(CreatedAtModel):
    """Records a view or share of a Post or Prayer."""

    class ViewType(models.TextChoices):
        VIEW = "view", "View"
        SHARE = "share", "Share"

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(app_label="social", model__in=["post", "prayer"]),
    )

    object_id = models.UUIDField()

    content_object = GenericForeignKey("content_type", "object_id")

    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="post_views",
    )

    view_type = models.CharField(
        max_length=10,
        choices=ViewType.choices,
        default=ViewType.VIEW,
        db_index=True,
    )

    class Meta:
        verbose_name = "post view"
        verbose_name_plural = "post views"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id", "view_type"]),
            models.Index(fields=["viewer"]),
            models.Index(fields=["viewer", "content_type", "object_id", "created_at"]),
        ]

    def __str__(self) -> str:
        viewer_name = self.viewer.full_name if self.viewer else "Anonymous"

        return f"View by {viewer_name} on {self.content_type.model}"


class PostViewDailySummary(models.Model):
    """Aggregated daily summary of PostView records.

    Raw PostView rows older than 30 days are rolled up into these
    summaries by the ``archive_old_post_views`` Celery task, then purged.
    """

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
    )

    object_id = models.UUIDField()
    summary_date = models.DateField()
    view_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    unique_viewers = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "post view daily summary"
        verbose_name_plural = "post view daily summaries"
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "summary_date"],
                name="unique_view_summary_per_content_per_day",
            ),
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id", "summary_date"]),
            models.Index(fields=["summary_date"]),
        ]

    def __str__(self) -> str:
        return (
            f"Summary {self.summary_date}: {self.content_type.model} {self.object_id}"
        )


class PostBoost(CreatedAtModel):
    """Record of a post being boosted (paid promotion)."""

    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="boosts",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_boosts",
    )

    tier = models.CharField(
        max_length=50,
        help_text="Maps to the IAP product ID for the boost tier.",
    )

    platform = models.CharField(max_length=10, choices=Platform.choices)
    transaction_id = models.CharField(max_length=255, unique=True, db_index=True)
    duration_days = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=False, db_index=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "post boost"
        verbose_name_plural = "post boosts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["post", "is_active"]),
            models.Index(fields=["user"]),
            models.Index(fields=["is_active", "expires_at"]),
        ]

    def __str__(self) -> str:
        return f"Boost on Post {self.post_id} by {self.user.full_name} ({self.tier})"


class BoostAnalyticSnapshot(CreatedAtModel):
    """Daily analytics snapshot for an active boost."""

    boost = models.ForeignKey(
        PostBoost,
        on_delete=models.CASCADE,
        related_name="analytics_snapshots",
    )

    impressions = models.PositiveIntegerField(default=0)
    reach = models.PositiveIntegerField(default=0)
    engagement_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Engagement rate as a percentage (e.g., 3.50 = 3.5%).",
    )

    link_clicks = models.PositiveIntegerField(default=0)
    profile_visits = models.PositiveIntegerField(default=0)
    snapshot_date = models.DateField(db_index=True)

    class Meta:
        verbose_name = "boost analytic snapshot"
        verbose_name_plural = "boost analytic snapshots"
        ordering = ["-snapshot_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["boost", "snapshot_date"],
                name="unique_snapshot_per_boost_per_day",
            ),
        ]
        indexes = [
            models.Index(fields=["boost", "-snapshot_date"]),
        ]

    def __str__(self) -> str:
        return f"Snapshot for Boost {self.boost_id} on {self.snapshot_date}"
