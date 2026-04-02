from __future__ import annotations
import logging
from datetime import timedelta
from typing import Any
from uuid import UUID
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, QuerySet, Subquery
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.common.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

from apps.common.services import BaseService
from apps.social.models import Post
from .models import BoostAnalyticSnapshot, PostBoost, PostView
from ..shop.validators import validate_apple_receipt, validate_google_receipt

logger = logging.getLogger(__name__)

VIEWABLE_MODELS: dict[str, type] = {
    "post": Post,
}

try:
    from apps.social.models import Prayer

    VIEWABLE_MODELS["prayer"] = Prayer

except ImportError:  # pragma: no cover
    pass


def _resolve_viewable_content_type(model_name: str) -> ContentType:
    """Resolve a model name to a ContentType for view tracking."""

    model_name = model_name.lower()

    model_class = VIEWABLE_MODELS.get(model_name)

    if model_class is None:
        raise BadRequestError(
            detail=f"Invalid content type '{model_name}'. "
            f"Must be one of: {', '.join(sorted(VIEWABLE_MODELS.keys()))}."
        )

    return ContentType.objects.get_for_model(model_class)


class PostViewService(BaseService[PostView]):
    """Business logic for recording and counting content views."""

    model = PostView

    def record_view(
        self,
        *,
        content_type_model: str,
        object_id: UUID,
        viewer_id: UUID | None = None,
        view_type: str = PostView.ViewType.VIEW,
    ) -> PostView:
        """Record a view or share on a post or prayer.
        Anonymous views are allowed (viewer_id=None).
        De-duplicates views from the same user on the same content
        within a 1-hour window to avoid inflated counts.
        Shares are never de-duplicated (each share is a distinct action).
        """
        ct = _resolve_viewable_content_type(content_type_model)
        model_class = ct.model_class()

        if (
            model_class is not None
            and not model_class.objects.filter(pk=object_id).exists()
        ):
            raise NotFoundError(
                detail=f"{content_type_model.capitalize()} with id '{object_id}' not found."
            )

        if view_type == PostView.ViewType.VIEW and viewer_id is not None:
            one_hour_ago = timezone.now() - timedelta(hours=1)
            existing = PostView.objects.filter(
                content_type=ct,
                object_id=object_id,
                viewer_id=viewer_id,
                view_type=PostView.ViewType.VIEW,
                created_at__gte=one_hour_ago,
            ).exists()

            if existing:
                return (
                    PostView.objects.filter(
                        content_type=ct,
                        object_id=object_id,
                        viewer_id=viewer_id,
                        view_type=PostView.ViewType.VIEW,
                    )
                    .order_by("-created_at")
                    .first()
                )

        view = PostView.objects.create(
            content_type=ct,
            object_id=object_id,
            viewer_id=viewer_id,
            view_type=view_type,
        )

        return view

    def get_view_count(
        self,
        *,
        content_type_model: str,
        object_id: UUID,
    ) -> int:
        """Return total view count for a piece of content."""
        ct = _resolve_viewable_content_type(content_type_model)

        return PostView.objects.filter(
            content_type=ct,
            object_id=object_id,
            view_type=PostView.ViewType.VIEW,
        ).count()

    def get_share_count(
        self,
        *,
        content_type_model: str,
        object_id: UUID,
    ) -> int:
        """Return total share count for a piece of content."""
        ct = _resolve_viewable_content_type(content_type_model)

        return PostView.objects.filter(
            content_type=ct,
            object_id=object_id,
            view_type=PostView.ViewType.SHARE,
        ).count()


class PostBoostService(BaseService[PostBoost]):
    """Business logic for post boosts (paid promotion)."""

    model = PostBoost

    def get_queryset(self) -> QuerySet[PostBoost]:
        return super().get_queryset().select_related("post", "user")

    @transaction.atomic
    def activate_boost(
        self,
        *,
        post_id: UUID,
        user_id: UUID,
        tier: str,
        platform: str,
        receipt_data: str = "",
        transaction_id: str,
        duration_days: int,
    ) -> PostBoost:
        """Activate a new boost for a post.
        - Validates the receipt with Apple/Google before proceeding.
        - Validates the transaction_id is unique.
        - Verifies the user owns the post.
        - Sets activation and expiry timestamps.
        - Marks the post as boosted.
        """

        try:
            post = Post.objects.get(pk=post_id)

        except Post.DoesNotExist:
            raise NotFoundError(detail=f"Post with id '{post_id}' not found.")

        if post.author_id != user_id:
            raise ForbiddenError(detail="You can only boost your own posts.")

        if PostBoost.objects.filter(transaction_id=transaction_id).exists():
            raise ConflictError(
                detail=f"Transaction '{transaction_id}' has already been processed."
            )

        if not receipt_data:
            raise ValidationError("Receipt data is required for boost activation.")

        try:
            if platform == PostBoost.Platform.IOS:
                validate_apple_receipt(
                    receipt_data,
                    expected_product_id=tier,
                )

            elif platform == PostBoost.Platform.ANDROID:
                validate_google_receipt(
                    product_id=tier,
                    purchase_token=receipt_data,
                )

            else:
                raise ValidationError(f"Unsupported platform: {platform}")

        except ValueError as exc:
            raise ValidationError(f"Receipt validation failed: {exc}")

        now = timezone.now()

        try:
            boost = PostBoost.objects.create(
                post_id=post_id,
                user_id=user_id,
                tier=tier,
                platform=platform,
                transaction_id=transaction_id,
                duration_days=duration_days,
                is_active=True,
                activated_at=now,
                expires_at=now + timedelta(days=duration_days),
            )

        except IntegrityError:
            raise ConflictError(
                detail=f"Transaction '{transaction_id}' has already been processed."
            )

        Post.objects.filter(pk=post_id).update(is_boosted=True)
        logger.info(
            "Boost activated: post=%s user=%s tier=%s duration=%dd",
            post_id,
            user_id,
            tier,
            duration_days,
        )

        try:
            from apps.common.utils import build_notification_data
            from apps.notifications.services import NotificationService

            NotificationService().create_notification(
                recipient_id=user_id,
                sender_id=None,
                notification_type="boost_live",
                title="Your boost is live!",
                body=f"Your post is now being promoted for {duration_days} days.",
                data=build_notification_data("boost_live", post_id=post_id),
            )

        except Exception:
            logger.warning(
                "Failed to send boost_live notification for post=%s",
                post_id,
                exc_info=True,
            )

        return boost

    def deactivate_expired_boosts(self) -> int:
        """Deactivate all boosts that have passed their expiry date.
        Returns the number of boosts deactivated.
        """
        now = timezone.now()
        expired_boosts = PostBoost.objects.filter(is_active=True, expires_at__lte=now)
        post_ids = list(expired_boosts.values_list("post_id", flat=True))
        count = expired_boosts.update(is_active=False)

        if post_ids:
            still_boosted_post_ids = set(
                PostBoost.objects.filter(
                    post_id__in=post_ids, is_active=True
                ).values_list("post_id", flat=True)
            )
            unboosted_post_ids = set(post_ids) - still_boosted_post_ids

            if unboosted_post_ids:
                Post.objects.filter(pk__in=unboosted_post_ids).update(is_boosted=False)

        logger.info("Deactivated %d expired boosts.", count)

        return count

    def get_user_boosts(
        self, *, user_id: UUID, active_only: bool = False
    ) -> QuerySet[PostBoost]:
        """Return boosts for a user. Optionally filter to active only."""
        qs = self.get_queryset().filter(user_id=user_id)

        if active_only:
            qs = qs.filter(is_active=True)

        return qs

    def get_boost_analytics(
        self,
        *,
        boost_id: UUID,
    ) -> QuerySet[BoostAnalyticSnapshot]:
        """Return analytics snapshots for a specific boost."""

        if not PostBoost.objects.filter(pk=boost_id).exists():
            raise NotFoundError(detail=f"Boost with id '{boost_id}' not found.")

        return BoostAnalyticSnapshot.objects.filter(boost_id=boost_id).order_by(
            "-snapshot_date"
        )


class AnalyticsService:
    """Aggregate analytics for posts and users."""

    def __init__(self) -> None:
        self._view_service = PostViewService()

    def get_post_analytics(
        self,
        *,
        post_id: UUID,
        requesting_user_id: UUID | None = None,
    ) -> dict[str, int]:
        """Return aggregate analytics for a single post.
        Returns counts for views, reactions, comments, and shares.
        Only the post author may view analytics for their post.
        """

        try:
            post_obj = Post.objects.get(pk=post_id)

        except Post.DoesNotExist:
            raise NotFoundError(detail=f"Post with id '{post_id}' not found.")

        if requesting_user_id is None or post_obj.author_id != requesting_user_id:
            raise ForbiddenError(
                detail="You can only view analytics for your own posts."
            )

        ct = ContentType.objects.get_for_model(Post)
        post = Post.objects.filter(pk=post_id).first()
        view_counts = PostView.objects.filter(
            content_type=ct,
            object_id=post_id,
        ).aggregate(
            views=Count("pk", filter=Q(view_type=PostView.ViewType.VIEW)),
            shares=Count("pk", filter=Q(view_type=PostView.ViewType.SHARE)),
        )

        return {
            "views": view_counts["views"],
            "reactions": post.reaction_count if post else 0,
            "comments": post.comment_count if post else 0,
            "shares": view_counts["shares"],
        }

    def get_user_analytics(self, *, user_id: UUID) -> dict[str, Any]:
        """Return aggregate analytics for all of a user's posts.
        Returns total views, reactions, comments, and post count.
        Uses subquery approach for better performance instead of
        materializing all post IDs.
        """
        user_posts = Post.objects.filter(author_id=user_id)
        post_count = user_posts.count()

        if post_count == 0:
            return {
                "post_count": 0,
                "total_views": 0,
                "total_reactions": 0,
                "total_comments": 0,
            }

        ct = ContentType.objects.get_for_model(Post)
        post_ids_subquery = user_posts.values("pk")
        total_views = PostView.objects.filter(
            content_type=ct, object_id__in=Subquery(post_ids_subquery)
        ).count()
        aggregates = user_posts.aggregate(
            total_reactions=Count("reactions", distinct=True),
            total_comments=Count("comments", distinct=True),
        )

        return {
            "post_count": post_count,
            "total_views": total_views,
            "total_reactions": aggregates.get("total_reactions", 0),
            "total_comments": aggregates.get("total_comments", 0),
        }
