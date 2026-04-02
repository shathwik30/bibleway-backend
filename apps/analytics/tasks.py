from __future__ import annotations
import logging
from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=120,
    time_limit=180,
)
def deactivate_expired_boosts(self):
    """Deactivate all boosts that have passed their expiry date.

    Should be scheduled to run periodically (e.g., every 15 minutes).
    """

    try:
        from apps.analytics.services import PostBoostService

        service = PostBoostService()
        count = service.deactivate_expired_boosts()
        logger.info("Celery task deactivated %d expired boosts.", count)

        return count

    except Exception as exc:
        logger.error("deactivate_expired_boosts task failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    soft_time_limit=300,
    time_limit=600,
)
def generate_boost_snapshots(self):
    """Generate daily analytics snapshots for all active boosts.

    Should be scheduled to run once per day (e.g., at midnight UTC).
    Creates a BoostAnalyticSnapshot for each active boost with aggregated
    view/engagement data for the day.
    """

    try:
        from django.db.models import Count, Q
        from apps.analytics.models import BoostAnalyticSnapshot, PostBoost, PostView
        from apps.social.models import Post

        today = timezone.now().date()
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        post_ct = ContentType.objects.get_for_model(Post)
        active_boosts = PostBoost.objects.filter(is_active=True).select_related("post")
        post_ids = list(active_boosts.values_list("post_id", flat=True))

        if not post_ids:
            logger.info("No active boosts to generate snapshots for %s.", today)

            return 0

        view_stats = {}

        for row in (
            PostView.objects.filter(
                content_type=post_ct,
                object_id__in=post_ids,
                created_at__gte=today_start,
            )
            .values("object_id")
            .annotate(
                impressions=Count("pk", filter=Q(view_type=PostView.ViewType.VIEW)),
                reach=Count(
                    "viewer_id", filter=Q(viewer_id__isnull=False), distinct=True
                ),
            )
        ):
            view_stats[row["object_id"]] = row

        from apps.social.models import Reaction, Comment

        reaction_stats = dict(
            Reaction.objects.filter(
                content_type=post_ct,
                object_id__in=post_ids,
                created_at__gte=today_start,
            )
            .values("object_id")
            .annotate(cnt=Count("pk"))
            .values_list("object_id", "cnt")
        )
        comment_stats = dict(
            Comment.objects.filter(
                content_type=post_ct,
                object_id__in=post_ids,
                created_at__gte=today_start,
            )
            .values("object_id")
            .annotate(cnt=Count("pk"))
            .values_list("object_id", "cnt")
        )
        snapshots_created = 0

        for boost in active_boosts:
            vs = view_stats.get(boost.post_id, {})
            impressions = vs.get("impressions", 0)
            reach = vs.get("reach", 0)
            daily_reactions = reaction_stats.get(boost.post_id, 0)
            daily_comments = comment_stats.get(boost.post_id, 0)
            engagement_rate = 0.0

            if impressions > 0:
                engagement_rate = round(
                    ((daily_reactions + daily_comments) / impressions) * 100, 2
                )

            _, created = BoostAnalyticSnapshot.objects.get_or_create(
                boost=boost,
                snapshot_date=today,
                defaults={
                    "impressions": impressions,
                    "reach": reach,
                    "engagement_rate": engagement_rate,
                    "link_clicks": 0,
                    "profile_visits": 0,
                },
            )

            if created:
                snapshots_created += 1

        logger.info("Generated %d boost snapshots for %s.", snapshots_created, today)

        return snapshots_created

    except Exception as exc:
        logger.error("generate_boost_snapshots task failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=600,
    time_limit=900,
)
def archive_old_post_views(self, retention_days: int = 30, batch_size: int = 5000):
    """Roll up PostView records older than ``retention_days`` into daily summaries, then purge.

    Runs in batches to avoid long-running transactions and excessive memory usage.
    Scheduled nightly via Celery Beat.
    """

    from datetime import timedelta
    from django.db.models import Count, Q
    from apps.analytics.models import PostView, PostViewDailySummary

    try:
        cutoff = timezone.now() - timedelta(days=retention_days)
        old_views = (
            PostView.objects.filter(created_at__lt=cutoff)
            .values("content_type_id", "object_id", "created_at__date")
            .annotate(
                views=Count("pk", filter=Q(view_type=PostView.ViewType.VIEW)),
                shares=Count("pk", filter=Q(view_type=PostView.ViewType.SHARE)),
                unique_viewers=Count(
                    "viewer_id", filter=Q(viewer_id__isnull=False), distinct=True
                ),
            )
        )
        summaries_created = 0

        for row in old_views.iterator(chunk_size=1000):
            _, created = PostViewDailySummary.objects.update_or_create(
                content_type_id=row["content_type_id"],
                object_id=row["object_id"],
                summary_date=row["created_at__date"],
                defaults={
                    "view_count": row["views"],
                    "share_count": row["shares"],
                    "unique_viewers": row["unique_viewers"],
                },
            )

            if created:
                summaries_created += 1

        total_deleted = 0

        while True:
            batch_ids = list(
                PostView.objects.filter(created_at__lt=cutoff).values_list(
                    "pk", flat=True
                )[:batch_size]
            )

            if not batch_ids:
                break

            deleted, _ = PostView.objects.filter(pk__in=batch_ids).delete()
            total_deleted += deleted

        logger.info(
            "Archived PostViews: %d summaries created/updated, %d raw rows purged (cutoff=%s).",
            summaries_created,
            total_deleted,
            cutoff.date(),
        )

        return {"summaries": summaries_created, "purged": total_deleted}

    except Exception as exc:
        logger.error("archive_old_post_views task failed: %s", exc)
        raise self.retry(exc=exc)
