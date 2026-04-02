"""Tests for social and accounts signal-based denormalized counters.

Covers:
- Reaction create/delete -> Post.reaction_count, Prayer.reaction_count
- Comment create/delete -> Post.comment_count, Prayer.comment_count
- Post create/delete -> User.post_count
- Prayer create/delete -> User.prayer_count
- FollowRelationship create/delete -> User.follower_count, User.following_count
"""

from __future__ import annotations

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache

from apps.accounts.models import FollowRelationship, User
from apps.social.models import Comment, Post, Prayer, Reaction

from conftest import (
    FollowRelationshipFactory,
    PostFactory,
    PrayerFactory,
    UserFactory,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the cache before each test to avoid stale data."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestReactionCountSignals:
    """Creating/deleting Reactions increments/decrements Post/Prayer.reaction_count."""

    def test_create_reaction_increments_post_reaction_count(self):
        post = PostFactory()
        assert post.reaction_count == 0
        ct = ContentType.objects.get_for_model(Post)
        user = UserFactory()
        Reaction.objects.create(
            user=user, content_type=ct, object_id=post.pk, emoji_type="heart"
        )
        post.refresh_from_db()
        assert post.reaction_count == 1

    def test_delete_reaction_decrements_post_reaction_count(self):
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        user = UserFactory()
        reaction = Reaction.objects.create(
            user=user, content_type=ct, object_id=post.pk, emoji_type="heart"
        )
        post.refresh_from_db()
        assert post.reaction_count == 1
        reaction.delete()
        post.refresh_from_db()
        assert post.reaction_count == 0

    def test_multiple_reactions_increment_post_count(self):
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        for _ in range(3):
            Reaction.objects.create(
                user=UserFactory(),
                content_type=ct,
                object_id=post.pk,
                emoji_type="heart",
            )
        post.refresh_from_db()
        assert post.reaction_count == 3

    def test_create_reaction_increments_prayer_reaction_count(self):
        prayer = PrayerFactory()
        assert prayer.reaction_count == 0
        ct = ContentType.objects.get_for_model(Prayer)
        user = UserFactory()
        Reaction.objects.create(
            user=user, content_type=ct, object_id=prayer.pk, emoji_type="amen"
        )
        prayer.refresh_from_db()
        assert prayer.reaction_count == 1

    def test_delete_reaction_decrements_prayer_reaction_count(self):
        prayer = PrayerFactory()
        ct = ContentType.objects.get_for_model(Prayer)
        user = UserFactory()
        reaction = Reaction.objects.create(
            user=user, content_type=ct, object_id=prayer.pk, emoji_type="amen"
        )
        prayer.refresh_from_db()
        assert prayer.reaction_count == 1
        reaction.delete()
        prayer.refresh_from_db()
        assert prayer.reaction_count == 0

    def test_reaction_on_different_posts_independent(self):
        post1 = PostFactory()
        post2 = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        user = UserFactory()
        Reaction.objects.create(
            user=user, content_type=ct, object_id=post1.pk, emoji_type="heart"
        )
        post1.refresh_from_db()
        post2.refresh_from_db()
        assert post1.reaction_count == 1
        assert post2.reaction_count == 0


@pytest.mark.django_db
class TestCommentCountSignals:
    """Creating/deleting Comments increments/decrements Post/Prayer.comment_count."""

    def test_create_comment_increments_post_comment_count(self):
        post = PostFactory()
        assert post.comment_count == 0
        ct = ContentType.objects.get_for_model(Post)
        user = UserFactory()
        Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Nice!"
        )
        post.refresh_from_db()
        assert post.comment_count == 1

    def test_delete_comment_decrements_post_comment_count(self):
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        user = UserFactory()
        comment = Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Nice!"
        )
        post.refresh_from_db()
        assert post.comment_count == 1
        comment.delete()
        post.refresh_from_db()
        assert post.comment_count == 0

    def test_multiple_comments_increment_post_count(self):
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        for i in range(3):
            Comment.objects.create(
                user=UserFactory(),
                content_type=ct,
                object_id=post.pk,
                text=f"Comment {i}",
            )
        post.refresh_from_db()
        assert post.comment_count == 3

    def test_create_comment_increments_prayer_comment_count(self):
        prayer = PrayerFactory()
        assert prayer.comment_count == 0
        ct = ContentType.objects.get_for_model(Prayer)
        user = UserFactory()
        Comment.objects.create(
            user=user, content_type=ct, object_id=prayer.pk, text="Praying!"
        )
        prayer.refresh_from_db()
        assert prayer.comment_count == 1

    def test_delete_comment_decrements_prayer_comment_count(self):
        prayer = PrayerFactory()
        ct = ContentType.objects.get_for_model(Prayer)
        user = UserFactory()
        comment = Comment.objects.create(
            user=user, content_type=ct, object_id=prayer.pk, text="Praying!"
        )
        prayer.refresh_from_db()
        assert prayer.comment_count == 1
        comment.delete()
        prayer.refresh_from_db()
        assert prayer.comment_count == 0


@pytest.mark.django_db
class TestPostCountSignals:
    """Creating/deleting Posts increments/decrements User.post_count."""

    def test_create_post_increments_user_post_count(self):
        user = UserFactory()
        assert user.post_count == 0
        PostFactory(author=user)
        user.refresh_from_db()
        assert user.post_count == 1

    def test_multiple_posts_increment_user_count(self):
        user = UserFactory()
        PostFactory(author=user)
        PostFactory(author=user)
        PostFactory(author=user)
        user.refresh_from_db()
        assert user.post_count == 3

    def test_delete_post_decrements_user_post_count(self):
        user = UserFactory()
        post = PostFactory(author=user)
        user.refresh_from_db()
        assert user.post_count == 1
        post.delete()
        user.refresh_from_db()
        assert user.post_count == 0

    def test_post_count_isolated_per_user(self):
        user1 = UserFactory()
        user2 = UserFactory()
        PostFactory(author=user1)
        PostFactory(author=user1)
        PostFactory(author=user2)
        user1.refresh_from_db()
        user2.refresh_from_db()
        assert user1.post_count == 2
        assert user2.post_count == 1


@pytest.mark.django_db
class TestPrayerCountSignals:
    """Creating/deleting Prayers increments/decrements User.prayer_count."""

    def test_create_prayer_increments_user_prayer_count(self):
        user = UserFactory()
        assert user.prayer_count == 0
        PrayerFactory(author=user)
        user.refresh_from_db()
        assert user.prayer_count == 1

    def test_multiple_prayers_increment_user_count(self):
        user = UserFactory()
        PrayerFactory(author=user)
        PrayerFactory(author=user)
        user.refresh_from_db()
        assert user.prayer_count == 2

    def test_delete_prayer_decrements_user_prayer_count(self):
        user = UserFactory()
        prayer = PrayerFactory(author=user)
        user.refresh_from_db()
        assert user.prayer_count == 1
        prayer.delete()
        user.refresh_from_db()
        assert user.prayer_count == 0

    def test_prayer_count_isolated_per_user(self):
        user1 = UserFactory()
        user2 = UserFactory()
        PrayerFactory(author=user1)
        PrayerFactory(author=user2)
        PrayerFactory(author=user2)
        user1.refresh_from_db()
        user2.refresh_from_db()
        assert user1.prayer_count == 1
        assert user2.prayer_count == 2


@pytest.mark.django_db
class TestFollowCountSignals:
    """Creating/deleting FollowRelationship increments/decrements
    User.follower_count and User.following_count.
    """

    def test_create_follow_increments_counts(self):
        follower = UserFactory()
        following = UserFactory()
        FollowRelationshipFactory(follower=follower, following=following)
        follower.refresh_from_db()
        following.refresh_from_db()
        assert follower.following_count == 1
        assert following.follower_count == 1

    def test_delete_follow_decrements_counts(self):
        follower = UserFactory()
        following = UserFactory()
        rel = FollowRelationshipFactory(follower=follower, following=following)
        follower.refresh_from_db()
        following.refresh_from_db()
        assert follower.following_count == 1
        assert following.follower_count == 1
        rel.delete()
        follower.refresh_from_db()
        following.refresh_from_db()
        assert follower.following_count == 0
        assert following.follower_count == 0

    def test_multiple_followers_increment_target_follower_count(self):
        target = UserFactory()
        FollowRelationshipFactory(follower=UserFactory(), following=target)
        FollowRelationshipFactory(follower=UserFactory(), following=target)
        FollowRelationshipFactory(follower=UserFactory(), following=target)
        target.refresh_from_db()
        assert target.follower_count == 3

    def test_following_multiple_users_increments_following_count(self):
        user = UserFactory()
        FollowRelationshipFactory(follower=user, following=UserFactory())
        FollowRelationshipFactory(follower=user, following=UserFactory())
        user.refresh_from_db()
        assert user.following_count == 2

    def test_follow_counts_isolated_per_user(self):
        user_a = UserFactory()
        user_b = UserFactory()
        user_c = UserFactory()
        FollowRelationshipFactory(follower=user_a, following=user_b)
        FollowRelationshipFactory(follower=user_c, following=user_b)
        user_a.refresh_from_db()
        user_b.refresh_from_db()
        user_c.refresh_from_db()
        assert user_a.following_count == 1
        assert user_a.follower_count == 0
        assert user_b.follower_count == 2
        assert user_b.following_count == 0
        assert user_c.following_count == 1
        assert user_c.follower_count == 0
