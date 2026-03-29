"""Tests for social app models."""

from __future__ import annotations

import uuid

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError

from apps.social.models import (
    Comment,
    Post,
    PostMedia,
    Prayer,
    PrayerMedia,
    Reaction,
    Reply,
    Report,
)

# Import factories from root conftest (available via pytest auto-discovery).
from conftest import (
    PostFactory,
    PrayerFactory,
    ReportFactory,
    UserFactory,
)


# ──────────────────────────────────────────────────────────────
# Post model
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPostModel:
    """Tests for the Post model."""

    def test_create_post_text_only(self):
        post = PostFactory(text_content="Hello world")
        assert post.pk is not None
        assert post.text_content == "Hello world"
        assert post.is_boosted is False
        assert post.author is not None

    def test_post_str_with_text(self):
        user = UserFactory(full_name="John Doe")
        post = PostFactory(author=user, text_content="My first post")
        assert "John Doe" in str(post)
        assert "My first post" in str(post)

    def test_post_str_media_only(self):
        user = UserFactory(full_name="Jane Smith")
        post = PostFactory(author=user, text_content="")
        assert "(media only)" in str(post)

    def test_post_str_truncates_long_text(self):
        long_text = "A" * 100
        post = PostFactory(text_content=long_text)
        # __str__ truncates to first 50 chars
        assert str(post).endswith(long_text[:50])

    def test_post_uuid_pk(self):
        post = PostFactory()
        assert isinstance(post.pk, uuid.UUID)

    def test_post_ordering_newest_first(self):
        user = UserFactory()
        post1 = PostFactory(author=user, text_content="First")
        post2 = PostFactory(author=user, text_content="Second")
        posts = list(Post.objects.filter(author=user))
        # Newest first
        assert posts[0].pk == post2.pk
        assert posts[1].pk == post1.pk

    def test_post_cascade_delete_with_author(self):
        user = UserFactory()
        PostFactory(author=user)
        user_pk = user.pk
        assert Post.objects.filter(author_id=user_pk).count() == 1
        user.delete()
        assert Post.objects.filter(author_id=user_pk).count() == 0

    def test_post_default_values(self):
        post = PostFactory()
        assert post.is_boosted is False
        assert post.created_at is not None
        assert post.updated_at is not None

    def test_post_generic_relations_exist(self):
        """Post should have reactions, comments, and reports generic relations."""
        post = PostFactory()
        assert hasattr(post, "reactions")
        assert hasattr(post, "comments")
        assert hasattr(post, "reports")


# ──────────────────────────────────────────────────────────────
# PostMedia model
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPostMediaModel:
    """Tests for the PostMedia model."""

    def test_post_media_str(self):
        post = PostFactory()
        media = PostMedia.objects.create(
            post=post,
            file="test.jpg",
            media_type=PostMedia.MediaType.IMAGE,
            order=0,
        )
        assert "image" in str(media)
        assert str(post.pk) in str(media)

    def test_post_media_ordering(self):
        post = PostFactory()
        m2 = PostMedia.objects.create(
            post=post, file="b.jpg", media_type="image", order=1
        )
        m1 = PostMedia.objects.create(
            post=post, file="a.jpg", media_type="image", order=0
        )
        media = list(post.media.all())
        assert media[0].pk == m1.pk
        assert media[1].pk == m2.pk

    def test_post_media_cascade_delete(self):
        post = PostFactory()
        post_pk = post.pk
        PostMedia.objects.create(
            post=post, file="test.jpg", media_type="image", order=0
        )
        assert PostMedia.objects.filter(post_id=post_pk).count() == 1
        post.delete()
        assert PostMedia.objects.filter(post_id=post_pk).count() == 0

    def test_post_media_type_choices(self):
        assert PostMedia.MediaType.IMAGE == "image"
        assert PostMedia.MediaType.VIDEO == "video"


# ──────────────────────────────────────────────────────────────
# Prayer model
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPrayerModel:
    """Tests for the Prayer model."""

    def test_create_prayer(self):
        prayer = PrayerFactory(title="Pray for healing")
        assert prayer.pk is not None
        assert prayer.title == "Pray for healing"
        assert prayer.author is not None

    def test_prayer_str(self):
        user = UserFactory(full_name="John Doe")
        prayer = PrayerFactory(author=user, title="Healing request")
        assert "John Doe" in str(prayer)
        assert "Healing request" in str(prayer)

    def test_prayer_uuid_pk(self):
        prayer = PrayerFactory()
        assert isinstance(prayer.pk, uuid.UUID)

    def test_prayer_ordering_newest_first(self):
        user = UserFactory()
        p1 = PrayerFactory(author=user, title="First")
        p2 = PrayerFactory(author=user, title="Second")
        prayers = list(Prayer.objects.filter(author=user))
        assert prayers[0].pk == p2.pk
        assert prayers[1].pk == p1.pk

    def test_prayer_default_description(self):
        prayer = PrayerFactory(description="")
        assert prayer.description == ""

    def test_prayer_cascade_delete_with_author(self):
        user = UserFactory()
        PrayerFactory(author=user)
        assert Prayer.objects.filter(author=user).count() == 1
        user.delete()
        assert Prayer.objects.count() == 0

    def test_prayer_generic_relations_exist(self):
        prayer = PrayerFactory()
        assert hasattr(prayer, "reactions")
        assert hasattr(prayer, "comments")
        assert hasattr(prayer, "reports")


# ──────────────────────────────────────────────────────────────
# PrayerMedia model
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPrayerMediaModel:
    """Tests for the PrayerMedia model."""

    def test_prayer_media_str(self):
        prayer = PrayerFactory()
        media = PrayerMedia.objects.create(
            prayer=prayer,
            file="test.jpg",
            media_type=PrayerMedia.MediaType.IMAGE,
            order=0,
        )
        assert "image" in str(media)
        assert str(prayer.pk) in str(media)

    def test_prayer_media_ordering(self):
        prayer = PrayerFactory()
        m2 = PrayerMedia.objects.create(
            prayer=prayer, file="b.jpg", media_type="image", order=1
        )
        m1 = PrayerMedia.objects.create(
            prayer=prayer, file="a.jpg", media_type="image", order=0
        )
        media = list(prayer.media.all())
        assert media[0].pk == m1.pk
        assert media[1].pk == m2.pk

    def test_prayer_media_cascade_delete(self):
        prayer = PrayerFactory()
        prayer_pk = prayer.pk
        PrayerMedia.objects.create(
            prayer=prayer, file="test.jpg", media_type="image", order=0
        )
        assert PrayerMedia.objects.filter(prayer_id=prayer_pk).count() == 1
        prayer.delete()
        assert PrayerMedia.objects.filter(prayer_id=prayer_pk).count() == 0

    def test_prayer_media_type_choices(self):
        assert PrayerMedia.MediaType.IMAGE == "image"
        assert PrayerMedia.MediaType.VIDEO == "video"


# ──────────────────────────────────────────────────────────────
# Reaction model
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestReactionModel:
    """Tests for the Reaction model."""

    def test_create_reaction(self):
        user = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        reaction = Reaction.objects.create(
            user=user,
            content_type=ct,
            object_id=post.pk,
            emoji_type=Reaction.EmojiType.HEART,
        )
        assert reaction.pk is not None
        assert reaction.emoji_type == "heart"

    def test_reaction_str(self):
        user = UserFactory(full_name="John Doe")
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        reaction = Reaction.objects.create(
            user=user,
            content_type=ct,
            object_id=post.pk,
            emoji_type=Reaction.EmojiType.FIRE,
        )
        assert "John Doe" in str(reaction)
        assert "fire" in str(reaction)

    def test_emoji_type_choices(self):
        assert Reaction.EmojiType.PRAYING_HANDS == "praying_hands"
        assert Reaction.EmojiType.HEART == "heart"
        assert Reaction.EmojiType.FIRE == "fire"
        assert Reaction.EmojiType.AMEN == "amen"
        assert Reaction.EmojiType.CROSS == "cross"

    def test_unique_constraint_one_reaction_per_user_per_content(self):
        user = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Reaction.objects.create(
            user=user,
            content_type=ct,
            object_id=post.pk,
            emoji_type=Reaction.EmojiType.HEART,
        )
        with pytest.raises(IntegrityError):
            Reaction.objects.create(
                user=user,
                content_type=ct,
                object_id=post.pk,
                emoji_type=Reaction.EmojiType.FIRE,
            )

    def test_different_users_can_react_to_same_content(self):
        user1 = UserFactory()
        user2 = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Reaction.objects.create(
            user=user1, content_type=ct, object_id=post.pk, emoji_type="heart"
        )
        Reaction.objects.create(
            user=user2, content_type=ct, object_id=post.pk, emoji_type="heart"
        )
        assert Reaction.objects.filter(content_type=ct, object_id=post.pk).count() == 2

    def test_reaction_on_prayer(self):
        user = UserFactory()
        prayer = PrayerFactory()
        ct = ContentType.objects.get_for_model(Prayer)
        reaction = Reaction.objects.create(
            user=user, content_type=ct, object_id=prayer.pk, emoji_type="amen"
        )
        assert reaction.content_type.model == "prayer"

    def test_reaction_cascade_delete_with_user(self):
        user = UserFactory()
        user_pk = user.pk
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Reaction.objects.create(
            user=user, content_type=ct, object_id=post.pk, emoji_type="heart"
        )
        assert Reaction.objects.filter(user_id=user_pk).count() == 1
        user.delete()
        assert Reaction.objects.filter(user_id=user_pk).count() == 0

    def test_reaction_via_generic_relation(self):
        user = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Reaction.objects.create(
            user=user, content_type=ct, object_id=post.pk, emoji_type="heart"
        )
        assert post.reactions.count() == 1


# ──────────────────────────────────────────────────────────────
# Comment model
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCommentModel:
    """Tests for the Comment model."""

    def test_create_comment(self):
        user = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Nice post!"
        )
        assert comment.pk is not None
        assert comment.text == "Nice post!"

    def test_comment_str(self):
        user = UserFactory(full_name="John Doe")
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Test"
        )
        assert "John Doe" in str(comment)
        assert "post" in str(comment)

    def test_comment_ordering_newest_first(self):
        user = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        c1 = Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="First"
        )
        c2 = Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Second"
        )
        comments = list(Comment.objects.all())
        assert comments[0].pk == c2.pk
        assert comments[1].pk == c1.pk

    def test_comment_on_prayer(self):
        user = UserFactory()
        prayer = PrayerFactory()
        ct = ContentType.objects.get_for_model(Prayer)
        comment = Comment.objects.create(
            user=user, content_type=ct, object_id=prayer.pk, text="Praying!"
        )
        assert comment.content_type.model == "prayer"

    def test_comment_via_generic_relation(self):
        user = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Hello"
        )
        assert post.comments.count() == 1

    def test_comment_cascade_delete_with_user(self):
        user = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Test"
        )
        user.delete()
        assert Comment.objects.count() == 0


# ──────────────────────────────────────────────────────────────
# Reply model
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestReplyModel:
    """Tests for the Reply model."""

    def test_create_reply(self):
        user = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Test"
        )
        reply = Reply.objects.create(user=user, comment=comment, text="My reply")
        assert reply.pk is not None
        assert reply.text == "My reply"
        assert reply.comment == comment

    def test_reply_str(self):
        user = UserFactory(full_name="Jane Smith")
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Test"
        )
        reply = Reply.objects.create(user=user, comment=comment, text="Reply")
        assert "Jane Smith" in str(reply)
        assert str(comment.pk) in str(reply)

    def test_reply_ordering_oldest_first(self):
        user = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Test"
        )
        r1 = Reply.objects.create(user=user, comment=comment, text="First")
        r2 = Reply.objects.create(user=user, comment=comment, text="Second")
        replies = list(Reply.objects.filter(comment=comment))
        # Oldest first
        assert replies[0].pk == r1.pk
        assert replies[1].pk == r2.pk

    def test_reply_cascade_delete_with_comment(self):
        user = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Test"
        )
        Reply.objects.create(user=user, comment=comment, text="Reply")
        assert Reply.objects.count() == 1
        comment.delete()
        assert Reply.objects.count() == 0

    def test_reply_related_name(self):
        user = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Test"
        )
        Reply.objects.create(user=user, comment=comment, text="Reply 1")
        Reply.objects.create(user=user, comment=comment, text="Reply 2")
        assert comment.replies.count() == 2


# ──────────────────────────────────────────────────────────────
# Report model
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestReportModel:
    """Tests for the Report model."""

    def test_create_report(self):
        reporter = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        report = Report.objects.create(
            reporter=reporter,
            content_type=ct,
            object_id=post.pk,
            reason=Report.Reason.SPAM,
        )
        assert report.pk is not None
        assert report.reason == "spam"
        assert report.status == Report.Status.PENDING

    def test_report_str(self):
        reporter = UserFactory(full_name="Reporter User")
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        report = Report.objects.create(
            reporter=reporter,
            content_type=ct,
            object_id=post.pk,
            reason=Report.Reason.INAPPROPRIATE,
        )
        assert "Reporter User" in str(report)
        assert "inappropriate" in str(report)

    def test_report_reason_choices(self):
        assert Report.Reason.INAPPROPRIATE == "inappropriate"
        assert Report.Reason.SPAM == "spam"
        assert Report.Reason.FALSE_TEACHING == "false_teaching"
        assert Report.Reason.OTHER == "other"

    def test_report_status_choices(self):
        assert Report.Status.PENDING == "pending"
        assert Report.Status.REVIEWED == "reviewed"
        assert Report.Status.DISMISSED == "dismissed"

    def test_report_default_status_is_pending(self):
        report = ReportFactory()
        assert report.status == Report.Status.PENDING

    def test_report_reviewed_by_nullable(self):
        report = ReportFactory()
        assert report.reviewed_by is None
        assert report.reviewed_at is None

    def test_report_cascade_delete_with_reporter(self):
        reporter = UserFactory()
        reporter_pk = reporter.pk
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Report.objects.create(
            reporter=reporter,
            content_type=ct,
            object_id=post.pk,
            reason="spam",
        )
        assert Report.objects.filter(reporter_id=reporter_pk).count() == 1
        reporter.delete()
        assert Report.objects.filter(reporter_id=reporter_pk).count() == 0

    def test_report_reviewed_by_set_null_on_delete(self):
        """When the reviewing admin is deleted, reviewed_by becomes null."""
        reporter = UserFactory()
        admin = UserFactory(is_staff=True)
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        report = Report.objects.create(
            reporter=reporter,
            content_type=ct,
            object_id=post.pk,
            reason="spam",
            reviewed_by=admin,
        )
        admin.delete()
        report.refresh_from_db()
        assert report.reviewed_by is None

    def test_report_via_generic_relation_on_post(self):
        reporter = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Report.objects.create(
            reporter=reporter,
            content_type=ct,
            object_id=post.pk,
            reason="spam",
        )
        assert post.reports.count() == 1

    def test_report_on_prayer(self):
        reporter = UserFactory()
        prayer = PrayerFactory()
        ct = ContentType.objects.get_for_model(Prayer)
        report = Report.objects.create(
            reporter=reporter,
            content_type=ct,
            object_id=prayer.pk,
            reason="inappropriate",
        )
        assert report.content_type.model == "prayer"
        assert prayer.reports.count() == 1
