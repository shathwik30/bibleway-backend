from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.common.models import CreatedAtModel, TimeStampedModel
from apps.common.storage_backends import PublicMediaStorage
from apps.common.validators import validate_file_size_100mb


def post_media_upload_path(instance, filename):
    return f"posts/{instance.post_id}/{filename}"


def prayer_media_upload_path(instance, filename):
    return f"prayers/{instance.prayer_id}/{filename}"


class Post(TimeStampedModel):
    """A user-created post in the social feed."""

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    text_content = models.TextField(max_length=2000, blank=True, default="")
    is_boosted = models.BooleanField(default=False, db_index=True)

    # Reverse generic relations
    reactions = GenericRelation("social.Reaction", related_query_name="post")
    comments = GenericRelation("social.Comment", related_query_name="post")
    reports = GenericRelation("social.Report", related_query_name="post")

    class Meta:
        verbose_name = "post"
        verbose_name_plural = "posts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["-created_at", "is_boosted"]),
        ]

    def __str__(self):
        preview = self.text_content[:50] if self.text_content else "(media only)"
        return f"Post by {self.author.full_name}: {preview}"


class PostMedia(CreatedAtModel):
    """Media attachment for a Post. Max 10 images or 1 video per post."""

    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="media",
    )
    file = models.FileField(
        upload_to=post_media_upload_path,
        storage=PublicMediaStorage(),
        validators=[validate_file_size_100mb],
    )
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "post media"
        verbose_name_plural = "post media"
        ordering = ["order"]
        indexes = [
            models.Index(fields=["post", "order"]),
        ]

    def __str__(self):
        return f"{self.media_type} for Post {self.post_id} (order: {self.order})"


class Prayer(TimeStampedModel):
    """A prayer request. Structurally similar to Post but displayed separately."""

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="prayers",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(max_length=2000, blank=True, default="")

    # Reverse generic relations
    reactions = GenericRelation("social.Reaction", related_query_name="prayer")
    comments = GenericRelation("social.Comment", related_query_name="prayer")
    reports = GenericRelation("social.Report", related_query_name="prayer")

    class Meta:
        verbose_name = "prayer"
        verbose_name_plural = "prayers"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["author", "-created_at"]),
        ]

    def __str__(self):
        return f"Prayer by {self.author.full_name}: {self.title}"


class PrayerMedia(CreatedAtModel):
    """Media attachment for a Prayer."""

    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    prayer = models.ForeignKey(
        Prayer,
        on_delete=models.CASCADE,
        related_name="media",
    )
    file = models.FileField(
        upload_to=prayer_media_upload_path,
        storage=PublicMediaStorage(),
        validators=[validate_file_size_100mb],
    )
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "prayer media"
        verbose_name_plural = "prayer media"
        ordering = ["order"]
        indexes = [
            models.Index(fields=["prayer", "order"]),
        ]

    def __str__(self):
        return f"{self.media_type} for Prayer {self.prayer_id} (order: {self.order})"


class Reaction(CreatedAtModel):
    """Faith-themed emoji reaction on a Post or Prayer.

    One reaction per user per content object (enforced via unique constraint).
    """

    class EmojiType(models.TextChoices):
        PRAYING_HANDS = "praying_hands", "Praying Hands"
        HEART = "heart", "Heart"
        FIRE = "fire", "Fire"
        AMEN = "amen", "Amen"
        CROSS = "cross", "Cross"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(app_label="social", model__in=["post", "prayer"]),
    )
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")

    emoji_type = models.CharField(max_length=20, choices=EmojiType.choices)

    class Meta:
        verbose_name = "reaction"
        verbose_name_plural = "reactions"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                name="unique_reaction_per_user_per_content",
            ),
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user.full_name} reacted {self.emoji_type}"


class Comment(TimeStampedModel):
    """Comment on a Post or Prayer."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(app_label="social", model__in=["post", "prayer"]),
    )
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")

    text = models.TextField(max_length=1000)

    class Meta:
        verbose_name = "comment"
        verbose_name_plural = "comments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id", "-created_at"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"Comment by {self.user.full_name} on {self.content_type.model}"


class Reply(TimeStampedModel):
    """Reply to a Comment. One level of nesting only."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    text = models.TextField(max_length=1000)

    class Meta:
        verbose_name = "reply"
        verbose_name_plural = "replies"
        ordering = ["created_at"]  # Oldest first within a comment thread
        indexes = [
            models.Index(fields=["comment", "created_at"]),
        ]

    def __str__(self):
        return f"Reply by {self.user.full_name} to Comment {self.comment_id}"


class Report(TimeStampedModel):
    """Report filed against a Post, Prayer, Comment, or User."""

    class Reason(models.TextChoices):
        INAPPROPRIATE = "inappropriate", "Inappropriate"
        SPAM = "spam", "Spam"
        FALSE_TEACHING = "false_teaching", "False Teaching"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        REVIEWED = "reviewed", "Reviewed"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_filed",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(
            app_label="social", model__in=["post", "prayer", "comment"]
        )
        | models.Q(app_label="accounts", model="user"),
    )
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")

    reason = models.CharField(max_length=20, choices=Reason.choices)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "report"
        verbose_name_plural = "reports"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["reporter"]),
        ]

    def __str__(self):
        return f"Report by {self.reporter.full_name}: {self.reason}"
