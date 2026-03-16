from __future__ import annotations

from typing import Any
from uuid import UUID

from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import Count, IntegerField, OuterRef, Prefetch, QuerySet, Subquery
from django.db.models.functions import Coalesce

from apps.accounts.models import User
from apps.common.exceptions import BadRequestError, ForbiddenError, NotFoundError
from apps.common.services import BaseService
from apps.common.utils import get_blocked_user_ids

from .models import (
    Comment,
    Post,
    PostMedia,
    Prayer,
    PrayerMedia,
    Reaction,
    Reply,
    Report,
)
from .validators import validate_media_constraints


# ---------------------------------------------------------------------------
# Content-type resolution helpers
# ---------------------------------------------------------------------------

CONTENT_TYPE_MODEL_MAP: dict[str, type] = {
    "post": Post,
    "prayer": Prayer,
    "comment": Comment,
    "user": User,
}

REACTABLE_MODELS: set[str] = {"post", "prayer"}
COMMENTABLE_MODELS: set[str] = {"post", "prayer"}
REPORTABLE_MODELS: set[str] = {"post", "prayer", "comment", "user"}


def _resolve_content_type(model_name: str, allowed: set[str]) -> ContentType:
    """Resolve a model name string to a Django ContentType.

    Raises BadRequestError if the model name is not in the allowed set.
    """
    model_name = model_name.lower()
    if model_name not in allowed:
        raise BadRequestError(
            detail=f"Invalid content type '{model_name}'. "
            f"Must be one of: {', '.join(sorted(allowed))}."
        )
    model_class = CONTENT_TYPE_MODEL_MAP[model_name]
    return ContentType.objects.get_for_model(model_class)


def _validate_object_exists(content_type: ContentType, object_id: UUID) -> None:
    """Verify the target object actually exists."""
    model_class = content_type.model_class()
    if model_class is None or not model_class.objects.filter(pk=object_id).exists():
        raise NotFoundError(
            detail=f"{content_type.model.capitalize()} with id '{object_id}' not found."
        )


def _get_content_author_id(content_type: ContentType, object_id: UUID) -> UUID | None:
    """Return the author/user FK for a piece of content, or None."""
    model_class = content_type.model_class()
    if model_class is None:
        return None

    # Determine the author field name.
    if hasattr(model_class, "author"):
        field_name = "author_id"
    elif hasattr(model_class, "user"):
        field_name = "user_id"
    else:
        return None

    obj = model_class.objects.filter(pk=object_id).values_list(field_name, flat=True).first()
    return obj


def _check_block_for_content(user: User, content_type: ContentType, object_id: UUID) -> None:
    """Raise ForbiddenError if *user* is blocked by the content's author."""
    author_id = _get_content_author_id(content_type, object_id)
    if author_id is None:
        return
    blocked_ids = get_blocked_user_ids(user.id)
    if author_id in blocked_ids:
        raise ForbiddenError(
            detail="You cannot interact with this content."
        )


# ---------------------------------------------------------------------------
# PostService
# ---------------------------------------------------------------------------


class PostService(BaseService[Post]):
    """Business logic for creating, reading, and managing posts."""

    model = Post

    def get_queryset(self) -> QuerySet[Post]:
        return (
            super()
            .get_queryset()
            .select_related("author")
            .prefetch_related(
                Prefetch("media", queryset=PostMedia.objects.order_by("order")),
            )
        )

    def _annotate_counts(self, qs: QuerySet[Post]) -> QuerySet[Post]:
        """Add reaction_count and comment_count via efficient subqueries.

        Uses correlated subqueries instead of JOINed Count to avoid the
        Cartesian-product problem when annotating multiple GenericRelations.
        """
        ct = ContentType.objects.get_for_model(Post)
        reaction_sq = (
            Reaction.objects.filter(content_type=ct, object_id=OuterRef("pk"))
            .order_by()
            .values("object_id")
            .annotate(c=Count("id"))
            .values("c")
        )
        comment_sq = (
            Comment.objects.filter(content_type=ct, object_id=OuterRef("pk"))
            .order_by()
            .values("object_id")
            .annotate(c=Count("id"))
            .values("c")
        )
        return qs.annotate(
            reaction_count=Coalesce(Subquery(reaction_sq), 0, output_field=IntegerField()),
            comment_count=Coalesce(Subquery(comment_sq), 0, output_field=IntegerField()),
        )

    def _get_annotated_queryset(self, *, requesting_user: User) -> QuerySet[Post]:
        """Base queryset with block filtering and count annotations."""
        blocked_user_ids = get_blocked_user_ids(requesting_user.id)
        return self._annotate_counts(
            self.get_queryset().exclude(author_id__in=blocked_user_ids)
        )

    def get_feed(
        self,
        *,
        requesting_user: User,
    ) -> QuerySet[Post]:
        """Return the main post feed for a user.

        - Excludes posts from users who have blocked (or are blocked by) the
          requesting user.
        - Boosted posts are included regardless of follow status; they are
          surfaced by the default ``-created_at`` ordering (cursor pagination
          handles the rest).
        """
        return self._get_annotated_queryset(requesting_user=requesting_user)

    def get_by_id_for_user(self, pk: UUID, *, requesting_user: User) -> Post:
        """Retrieve a single post with block filtering and count annotations."""
        blocked_user_ids = get_blocked_user_ids(requesting_user.id)
        try:
            return self._annotate_counts(
                self.get_queryset().exclude(author_id__in=blocked_user_ids)
            ).get(pk=pk)
        except Post.DoesNotExist:
            raise NotFoundError(
                detail=f"Post with id '{pk}' not found."
            )

    def get_user_posts(
        self,
        *,
        user_id: UUID,
        requesting_user: User,
    ) -> QuerySet[Post]:
        """Return posts by a specific user, respecting block rules."""
        blocked_user_ids = get_blocked_user_ids(requesting_user.id)
        if user_id in blocked_user_ids:
            return Post.objects.none()
        return self._annotate_counts(
            self.get_queryset().filter(author_id=user_id)
        )

    @transaction.atomic
    def create_post(
        self,
        *,
        author: User,
        text_content: str = "",
        media_files: list[UploadedFile] | None = None,
        media_types: list[str] | None = None,
    ) -> Post:
        """Create a post with optional media attachments.

        ``media_files`` and ``media_types`` must be equal-length lists when
        provided.  Validation of counts/types is left to the serializer layer;
        this service focuses on persistence.
        """
        if not text_content and not media_files:
            raise BadRequestError(
                detail="A post must have text content or at least one media file."
            )

        if media_files and media_types:
            validate_media_constraints(media_files, media_types, label="post")

        post = Post.objects.create(author=author, text_content=text_content)

        if media_files and media_types:
            post_media_items = [
                PostMedia(
                    post=post,
                    file=file,
                    media_type=media_type,
                    order=idx,
                )
                for idx, (file, media_type) in enumerate(
                    zip(media_files, media_types)
                )
            ]
            PostMedia.objects.bulk_create(post_media_items)

        return self.get_by_id(post.pk)

    def delete_post(self, *, post_id: UUID, requesting_user: User) -> None:
        """Delete a post. Only the author may delete."""
        post = self.get_by_id(post_id)
        if post.author_id != requesting_user.id:
            raise ForbiddenError(detail="You can only delete your own posts.")
        self.delete(post)

    def share_post(self, *, post_id: UUID) -> dict[str, str]:
        """Generate shareable deep-link data for a post."""
        post = self.get_by_id(post_id)
        return {
            "type": "post",
            "id": str(post.pk),
            "deep_link": f"bibleway://posts/{post.pk}",
            "preview": post.text_content[:100] if post.text_content else "",
        }


# ---------------------------------------------------------------------------
# PrayerService
# ---------------------------------------------------------------------------


class PrayerService(BaseService[Prayer]):
    """Business logic for prayer requests."""

    model = Prayer

    def get_queryset(self) -> QuerySet[Prayer]:
        return (
            super()
            .get_queryset()
            .select_related("author")
            .prefetch_related(
                Prefetch("media", queryset=PrayerMedia.objects.order_by("order")),
            )
        )

    def _annotate_counts(self, qs: QuerySet[Prayer]) -> QuerySet[Prayer]:
        """Add reaction_count and comment_count via efficient subqueries."""
        ct = ContentType.objects.get_for_model(Prayer)
        reaction_sq = (
            Reaction.objects.filter(content_type=ct, object_id=OuterRef("pk"))
            .order_by()
            .values("object_id")
            .annotate(c=Count("id"))
            .values("c")
        )
        comment_sq = (
            Comment.objects.filter(content_type=ct, object_id=OuterRef("pk"))
            .order_by()
            .values("object_id")
            .annotate(c=Count("id"))
            .values("c")
        )
        return qs.annotate(
            reaction_count=Coalesce(Subquery(reaction_sq), 0, output_field=IntegerField()),
            comment_count=Coalesce(Subquery(comment_sq), 0, output_field=IntegerField()),
        )

    def _get_annotated_queryset(self, *, requesting_user: User) -> QuerySet[Prayer]:
        """Base queryset with block filtering and count annotations."""
        blocked_user_ids = get_blocked_user_ids(requesting_user.id)
        return self._annotate_counts(
            self.get_queryset().exclude(author_id__in=blocked_user_ids)
        )

    def get_feed(
        self,
        *,
        requesting_user: User,
    ) -> QuerySet[Prayer]:
        """Return the prayer feed, excluding blocked users."""
        return self._get_annotated_queryset(requesting_user=requesting_user)

    def get_by_id_for_user(self, pk: UUID, *, requesting_user: User) -> Prayer:
        """Retrieve a single prayer with block filtering and count annotations."""
        blocked_user_ids = get_blocked_user_ids(requesting_user.id)
        try:
            return self._annotate_counts(
                self.get_queryset().exclude(author_id__in=blocked_user_ids)
            ).get(pk=pk)
        except Prayer.DoesNotExist:
            raise NotFoundError(
                detail=f"Prayer with id '{pk}' not found."
            )

    def get_user_prayers(
        self,
        *,
        user_id: UUID,
        requesting_user: User,
    ) -> QuerySet[Prayer]:
        """Return prayers by a specific user, respecting block rules."""
        blocked_user_ids = get_blocked_user_ids(requesting_user.id)
        if user_id in blocked_user_ids:
            return Prayer.objects.none()
        return self._annotate_counts(
            self.get_queryset().filter(author_id=user_id)
        )

    @transaction.atomic
    def create_prayer(
        self,
        *,
        author: User,
        title: str,
        description: str = "",
        media_files: list[UploadedFile] | None = None,
        media_types: list[str] | None = None,
    ) -> Prayer:
        """Create a prayer request with optional media."""
        if media_files and media_types:
            validate_media_constraints(media_files, media_types, label="prayer")

        prayer = Prayer.objects.create(
            author=author,
            title=title,
            description=description,
        )

        if media_files and media_types:
            prayer_media_items = [
                PrayerMedia(
                    prayer=prayer,
                    file=file,
                    media_type=media_type,
                    order=idx,
                )
                for idx, (file, media_type) in enumerate(
                    zip(media_files, media_types)
                )
            ]
            PrayerMedia.objects.bulk_create(prayer_media_items)

        return self.get_by_id(prayer.pk)

    def delete_prayer(self, *, prayer_id: UUID, requesting_user: User) -> None:
        """Delete a prayer. Only the author may delete."""
        prayer = self.get_by_id(prayer_id)
        if prayer.author_id != requesting_user.id:
            raise ForbiddenError(detail="You can only delete your own prayers.")
        self.delete(prayer)

    def share_prayer(self, *, prayer_id: UUID) -> dict[str, str]:
        """Generate shareable deep-link data for a prayer."""
        prayer = self.get_by_id(prayer_id)
        return {
            "type": "prayer",
            "id": str(prayer.pk),
            "deep_link": f"bibleway://prayers/{prayer.pk}",
            "preview": prayer.title[:100] if prayer.title else "",
        }


# ---------------------------------------------------------------------------
# ReactionService
# ---------------------------------------------------------------------------


class ReactionService:
    """Toggle-style reactions on posts and prayers."""

    @staticmethod
    @transaction.atomic
    def toggle_reaction(
        *,
        user: User,
        content_type_model: str,
        object_id: UUID,
        emoji_type: str,
    ) -> Reaction | None:
        """Create or update a reaction.

        - If the user has no reaction on this content, create one.
        - If the user already reacted with the *same* emoji, remove it (toggle off)
          and return ``None``.
        - If the user already reacted with a *different* emoji, update it.
        """
        ct = _resolve_content_type(content_type_model, REACTABLE_MODELS)
        _validate_object_exists(ct, object_id)
        _check_block_for_content(user, ct, object_id)

        existing = (
            Reaction.objects.select_for_update()
            .filter(user=user, content_type=ct, object_id=object_id)
            .first()
        )

        if existing is None:
            return Reaction.objects.create(
                user=user,
                content_type=ct,
                object_id=object_id,
                emoji_type=emoji_type,
            )

        if existing.emoji_type == emoji_type:
            existing.delete()
            return None

        existing.emoji_type = emoji_type
        existing.save(update_fields=["emoji_type"])
        return existing

    @staticmethod
    def remove_reaction(
        *,
        user: User,
        content_type_model: str,
        object_id: UUID,
    ) -> None:
        """Explicitly remove a user's reaction from content."""
        ct = _resolve_content_type(content_type_model, REACTABLE_MODELS)
        deleted_count, _ = Reaction.objects.filter(
            user=user, content_type=ct, object_id=object_id
        ).delete()
        if deleted_count == 0:
            raise NotFoundError(detail="No reaction found to remove.")

    @staticmethod
    def get_reactions_for_content(
        *,
        content_type_model: str,
        object_id: UUID,
    ) -> QuerySet[Reaction]:
        """Return all reactions for a given piece of content."""
        ct = _resolve_content_type(content_type_model, REACTABLE_MODELS)
        return (
            Reaction.objects.filter(content_type=ct, object_id=object_id)
            .select_related("user")
            .order_by("-created_at")
        )

    @staticmethod
    def get_reaction_count(
        *,
        content_type_model: str,
        object_id: UUID,
    ) -> dict[str, int]:
        """Return per-emoji counts for a piece of content."""
        ct = _resolve_content_type(content_type_model, REACTABLE_MODELS)
        qs = (
            Reaction.objects.filter(content_type=ct, object_id=object_id)
            .values("emoji_type")
            .annotate(count=Count("id"))
        )
        counts: dict[str, int] = {row["emoji_type"]: row["count"] for row in qs}
        total = sum(counts.values())
        counts["total"] = total
        return counts


# ---------------------------------------------------------------------------
# CommentService
# ---------------------------------------------------------------------------


class CommentService(BaseService[Comment]):
    """Comments on posts and prayers."""

    model = Comment

    def get_queryset(self) -> QuerySet[Comment]:
        reply_sq = (
            Reply.objects.filter(comment_id=OuterRef("pk"))
            .order_by()
            .values("comment_id")
            .annotate(c=Count("id"))
            .values("c")
        )
        return (
            super()
            .get_queryset()
            .select_related("user")
            .annotate(
                reply_count=Coalesce(Subquery(reply_sq), 0, output_field=IntegerField())
            )
        )

    def create_comment(
        self,
        *,
        user: User,
        content_type_model: str,
        object_id: UUID,
        text: str,
    ) -> Comment:
        """Add a comment to a post or prayer."""
        ct = _resolve_content_type(content_type_model, COMMENTABLE_MODELS)
        _validate_object_exists(ct, object_id)
        _check_block_for_content(user, ct, object_id)

        comment = Comment.objects.create(
            user=user,
            content_type=ct,
            object_id=object_id,
            text=text,
        )
        return self.get_by_id(comment.pk)

    def list_comments_for_content(
        self,
        *,
        content_type_model: str,
        object_id: UUID,
    ) -> QuerySet[Comment]:
        """Return comments for a given post or prayer."""
        ct = _resolve_content_type(content_type_model, COMMENTABLE_MODELS)
        _validate_object_exists(ct, object_id)
        return self.get_queryset().filter(content_type=ct, object_id=object_id)

    def delete_comment(self, *, comment_id: UUID, requesting_user: User) -> None:
        """Delete a comment. Only the commenter may delete."""
        comment = self.get_by_id(comment_id)
        if comment.user_id != requesting_user.id:
            raise ForbiddenError(detail="You can only delete your own comments.")
        self.delete(comment)


# ---------------------------------------------------------------------------
# ReplyService
# ---------------------------------------------------------------------------


class ReplyService(BaseService[Reply]):
    """Replies to comments (one level of nesting)."""

    model = Reply

    def get_queryset(self) -> QuerySet[Reply]:
        return super().get_queryset().select_related("user")

    def create_reply(
        self,
        *,
        user: User,
        comment_id: UUID,
        text: str,
    ) -> Reply:
        """Add a reply to a comment."""
        try:
            comment = Comment.objects.select_related("content_type").get(pk=comment_id)
        except Comment.DoesNotExist:
            raise NotFoundError(
                detail=f"Comment with id '{comment_id}' not found."
            )

        # Block enforcement: check against the parent content's author.
        _check_block_for_content(user, comment.content_type, comment.object_id)

        reply = Reply.objects.create(
            user=user,
            comment_id=comment_id,
            text=text,
        )
        return self.get_by_id(reply.pk)

    def list_replies_for_comment(
        self,
        *,
        comment_id: UUID,
    ) -> QuerySet[Reply]:
        """Return replies for a given comment, oldest first."""
        comment_exists = Comment.objects.filter(pk=comment_id).exists()
        if not comment_exists:
            raise NotFoundError(
                detail=f"Comment with id '{comment_id}' not found."
            )
        return self.get_queryset().filter(comment_id=comment_id).order_by("created_at")

    def delete_reply(self, *, reply_id: UUID, requesting_user: User) -> None:
        """Delete a reply. Only the author may delete."""
        reply = self.get_by_id(reply_id)
        if reply.user_id != requesting_user.id:
            raise ForbiddenError(detail="You can only delete your own replies.")
        self.delete(reply)


# ---------------------------------------------------------------------------
# ReportService
# ---------------------------------------------------------------------------


class ReportService(BaseService[Report]):
    """Content reporting and admin review."""

    model = Report

    def get_queryset(self) -> QuerySet[Report]:
        return super().get_queryset().select_related("reporter", "reviewed_by")

    def create_report(
        self,
        *,
        reporter: User,
        content_type_model: str,
        object_id: UUID,
        reason: str,
        description: str = "",
    ) -> Report:
        """File a report against a post, prayer, comment, or user."""
        ct = _resolve_content_type(content_type_model, REPORTABLE_MODELS)
        _validate_object_exists(ct, object_id)

        # Prevent self-reporting.
        author_id = _get_content_author_id(ct, object_id)
        if author_id is not None and author_id == reporter.id:
            raise BadRequestError(detail="You cannot report your own content.")

        # Prevent duplicate pending reports from the same user on the same object
        already_reported = Report.objects.filter(
            reporter=reporter,
            content_type=ct,
            object_id=object_id,
            status=Report.Status.PENDING,
        ).exists()
        if already_reported:
            raise BadRequestError(
                detail="You have already filed a pending report for this content."
            )

        return Report.objects.create(
            reporter=reporter,
            content_type=ct,
            object_id=object_id,
            reason=reason,
            description=description,
        )

    def list_pending_reports(self) -> QuerySet[Report]:
        """Return all pending reports (admin-only access enforced at the view)."""
        return (
            self.get_queryset()
            .filter(status=Report.Status.PENDING)
            .select_related("content_type")
        )
