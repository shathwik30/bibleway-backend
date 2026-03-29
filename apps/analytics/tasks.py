from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
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


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def generate_boost_snapshots(self):
    """Generate daily analytics snapshots for all active boosts.

    Should be scheduled to run once per day (e.g., at midnight UTC).
    Creates a BoostAnalyticSnapshot for each active boost with aggregated
    view/engagement data for the day.
    """
    try:
        from apps.analytics.models import BoostAnalyticSnapshot, PostBoost, PostView
        from apps.social.models import Post

        today = timezone.now().date()
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        active_boosts = PostBoost.objects.filter(is_active=True).select_related("post")
        post_ct = ContentType.objects.get_for_model(Post)

        snapshots_created = 0
        for boost in active_boosts:
            daily_views = PostView.objects.filter(
                content_type=post_ct,
                object_id=boost.post_id,
                created_at__gte=today_start,
            )
            impressions = daily_views.count()
            reach = daily_views.filter(
                viewer__isnull=False,
            ).values("viewer_id").distinct().count()

            post = boost.post
            daily_reactions = 0
            daily_comments = 0
            if hasattr(post, "reactions"):
                daily_reactions = post.reactions.filter(
                    created_at__gte=today_start
                ).count()
            if hasattr(post, "comments"):
                daily_comments = post.comments.filter(
                    created_at__gte=today_start
                ).count()

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

        logger.info(
            "Generated %d boost snapshots for %s.", snapshots_created, today
        )
        return snapshots_created
    except Exception as exc:
        logger.error("generate_boost_snapshots task failed: %s", exc)
        raise self.retry(exc=exc)
