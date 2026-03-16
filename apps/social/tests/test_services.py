"""Tests for social app services."""

from __future__ import annotations

import uuid

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache

from apps.common.exceptions import BadRequestError, ForbiddenError, NotFoundError
from apps.social.models import Comment, Post, Prayer, Reaction, Reply, Report
from apps.social.services import (
    COMMENTABLE_MODELS,
    REACTABLE_MODELS,
    REPORTABLE_MODELS,
    CommentService,
    PostService,
    PrayerService,
    ReactionService,
    ReplyService,
    ReportService,
    _check_block_for_content,
    _get_content_author_id,
    _resolve_content_type,
    _validate_object_exists,
)

from conftest import (
    BlockRelationshipFactory,
    CommentFactory,
    PostFactory,
    PrayerFactory,
    ReactionFactory,
    ReplyFactory,
    ReportFactory,
    UserFactory,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the cache before each test to avoid stale blocked-user data."""
    cache.clear()
    yield
    cache.clear()


# ──────────────────────────────────────────────────────────────
# Content-type resolution helpers
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestContentTypeHelpers:
    """Tests for the module-level helper functions."""

    def test_resolve_content_type_post(self):
        ct = _resolve_content_type("post", REACTABLE_MODELS)
        assert ct.model == "post"
        assert ct.app_label == "social"

    def test_resolve_content_type_prayer(self):
        ct = _resolve_content_type("prayer", REACTABLE_MODELS)
        assert ct.model == "prayer"

    def test_resolve_content_type_case_insensitive(self):
        ct = _resolve_content_type("Post", REACTABLE_MODELS)
        assert ct.model == "post"

    def test_resolve_content_type_invalid_raises_bad_request(self):
        with pytest.raises(BadRequestError, match="Invalid content type"):
            _resolve_content_type("invalid", REACTABLE_MODELS)

    def test_resolve_content_type_comment_not_in_reactable(self):
        with pytest.raises(BadRequestError):
            _resolve_content_type("comment", REACTABLE_MODELS)

    def test_resolve_content_type_comment_in_reportable(self):
        ct = _resolve_content_type("comment", REPORTABLE_MODELS)
        assert ct.model == "comment"

    def test_resolve_content_type_user_in_reportable(self):
        ct = _resolve_content_type("user", REPORTABLE_MODELS)
        assert ct.model == "user"

    def test_validate_object_exists_success(self):
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        # Should not raise
        _validate_object_exists(ct, post.pk)

    def test_validate_object_exists_not_found(self):
        ct = ContentType.objects.get_for_model(Post)
        with pytest.raises(NotFoundError, match="not found"):
            _validate_object_exists(ct, uuid.uuid4())

    def test_get_content_author_id_post(self):
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        author_id = _get_content_author_id(ct, post.pk)
        assert author_id == post.author_id

    def test_get_content_author_id_comment(self):
        post = PostFactory()
        ct_post = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=post.author,
            content_type=ct_post,
            object_id=post.pk,
            text="Test",
        )
        ct_comment = ContentType.objects.get_for_model(Comment)
        user_id = _get_content_author_id(ct_comment, comment.pk)
        assert user_id == post.author_id

    def test_get_content_author_id_nonexistent(self):
        ct = ContentType.objects.get_for_model(Post)
        result = _get_content_author_id(ct, uuid.uuid4())
        assert result is None

    def test_check_block_for_content_not_blocked(self):
        user = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        # Should not raise
        _check_block_for_content(user, ct, post.pk)

    def test_check_block_for_content_blocked(self):
        user = UserFactory()
        author = UserFactory()
        post = PostFactory(author=author)
        # author blocks user
        BlockRelationshipFactory(blocker=author, blocked=user)
        ct = ContentType.objects.get_for_model(Post)
        with pytest.raises(ForbiddenError, match="cannot interact"):
            _check_block_for_content(user, ct, post.pk)

    def test_check_block_for_content_user_blocked_author(self):
        user = UserFactory()
        author = UserFactory()
        post = PostFactory(author=author)
        # user blocks author
        BlockRelationshipFactory(blocker=user, blocked=author)
        ct = ContentType.objects.get_for_model(Post)
        with pytest.raises(ForbiddenError, match="cannot interact"):
            _check_block_for_content(user, ct, post.pk)


# ──────────────────────────────────────────────────────────────
# PostService
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPostService:
    """Tests for PostService."""

    def setup_method(self):
        self.service = PostService()

    def test_create_post_text_only(self):
        user = UserFactory()
        post = self.service.create_post(author=user, text_content="Hello world")
        assert post.text_content == "Hello world"
        assert post.author == user
        assert Post.objects.filter(pk=post.pk).exists()

    def test_create_post_empty_raises_bad_request(self):
        user = UserFactory()
        with pytest.raises(BadRequestError, match="must have text content"):
            self.service.create_post(author=user, text_content="", media_files=None)

    def test_get_feed_returns_posts(self):
        user = UserFactory()
        PostFactory(author=user, text_content="Post 1")
        PostFactory(author=user, text_content="Post 2")
        viewer = UserFactory()
        feed = list(self.service.get_feed(requesting_user=viewer))
        assert len(feed) == 2

    def test_get_feed_excludes_blocked_users(self):
        author = UserFactory()
        viewer = UserFactory()
        PostFactory(author=author, text_content="Visible")
        blocked_author = UserFactory()
        PostFactory(author=blocked_author, text_content="Hidden")
        BlockRelationshipFactory(blocker=viewer, blocked=blocked_author)

        feed = list(self.service.get_feed(requesting_user=viewer))
        assert len(feed) == 1
        assert feed[0].text_content == "Visible"

    def test_get_feed_excludes_users_who_blocked_viewer(self):
        author = UserFactory()
        viewer = UserFactory()
        PostFactory(author=author, text_content="Should see")
        blocker = UserFactory()
        PostFactory(author=blocker, text_content="Hidden")
        BlockRelationshipFactory(blocker=blocker, blocked=viewer)

        feed = list(self.service.get_feed(requesting_user=viewer))
        assert len(feed) == 1
        assert feed[0].text_content == "Should see"

    def test_get_feed_annotates_counts(self):
        author = UserFactory()
        post = PostFactory(author=author)
        # Add a reaction
        ct = ContentType.objects.get_for_model(Post)
        Reaction.objects.create(
            user=UserFactory(), content_type=ct, object_id=post.pk, emoji_type="heart"
        )
        # Add a comment
        Comment.objects.create(
            user=UserFactory(), content_type=ct, object_id=post.pk, text="Hello"
        )

        viewer = UserFactory()
        feed = list(self.service.get_feed(requesting_user=viewer))
        assert len(feed) == 1
        assert feed[0].reaction_count == 1
        assert feed[0].comment_count == 1

    def test_get_by_id_for_user_success(self):
        user = UserFactory()
        post = PostFactory(author=user)
        viewer = UserFactory()
        result = self.service.get_by_id_for_user(post.pk, requesting_user=viewer)
        assert result.pk == post.pk

    def test_get_by_id_for_user_blocked_raises_not_found(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author)
        BlockRelationshipFactory(blocker=author, blocked=viewer)
        with pytest.raises(NotFoundError):
            self.service.get_by_id_for_user(post.pk, requesting_user=viewer)

    def test_get_by_id_for_user_nonexistent_raises_not_found(self):
        viewer = UserFactory()
        with pytest.raises(NotFoundError):
            self.service.get_by_id_for_user(uuid.uuid4(), requesting_user=viewer)

    def test_delete_post_by_author(self):
        user = UserFactory()
        post = self.service.create_post(author=user, text_content="To delete")
        self.service.delete_post(post_id=post.pk, requesting_user=user)
        assert not Post.objects.filter(pk=post.pk).exists()

    def test_delete_post_by_non_author_raises_forbidden(self):
        author = UserFactory()
        other = UserFactory()
        post = PostFactory(author=author)
        with pytest.raises(ForbiddenError, match="only delete your own"):
            self.service.delete_post(post_id=post.pk, requesting_user=other)

    def test_delete_post_nonexistent_raises_not_found(self):
        user = UserFactory()
        with pytest.raises(NotFoundError):
            self.service.delete_post(post_id=uuid.uuid4(), requesting_user=user)

    def test_share_post(self):
        post = PostFactory(text_content="Share me!")
        share_data = self.service.share_post(post_id=post.pk)
        assert share_data["type"] == "post"
        assert share_data["id"] == str(post.pk)
        assert f"bibleway://posts/{post.pk}" == share_data["deep_link"]
        assert share_data["preview"] == "Share me!"

    def test_share_post_truncates_preview(self):
        long_text = "A" * 200
        post = PostFactory(text_content=long_text)
        share_data = self.service.share_post(post_id=post.pk)
        assert len(share_data["preview"]) == 100

    def test_share_post_empty_text(self):
        post = PostFactory(text_content="")
        share_data = self.service.share_post(post_id=post.pk)
        assert share_data["preview"] == ""

    def test_share_post_nonexistent_raises_not_found(self):
        with pytest.raises(NotFoundError):
            self.service.share_post(post_id=uuid.uuid4())

    def test_get_user_posts(self):
        author = UserFactory()
        viewer = UserFactory()
        PostFactory(author=author)
        PostFactory(author=author)
        PostFactory(author=UserFactory())  # another user's post
        posts = list(
            self.service.get_user_posts(user_id=author.pk, requesting_user=viewer)
        )
        assert len(posts) == 2

    def test_get_user_posts_blocked_returns_empty(self):
        author = UserFactory()
        viewer = UserFactory()
        PostFactory(author=author)
        BlockRelationshipFactory(blocker=author, blocked=viewer)
        posts = list(
            self.service.get_user_posts(user_id=author.pk, requesting_user=viewer)
        )
        assert len(posts) == 0


# ──────────────────────────────────────────────────────────────
# PrayerService
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPrayerService:
    """Tests for PrayerService."""

    def setup_method(self):
        self.service = PrayerService()

    def test_create_prayer(self):
        user = UserFactory()
        prayer = self.service.create_prayer(
            author=user, title="My prayer", description="Please pray"
        )
        assert prayer.title == "My prayer"
        assert prayer.description == "Please pray"
        assert prayer.author == user

    def test_create_prayer_with_title_only(self):
        user = UserFactory()
        prayer = self.service.create_prayer(author=user, title="Just title")
        assert prayer.title == "Just title"
        assert prayer.description == ""

    def test_get_feed_returns_prayers(self):
        user = UserFactory()
        PrayerFactory(author=user)
        PrayerFactory(author=user)
        viewer = UserFactory()
        feed = list(self.service.get_feed(requesting_user=viewer))
        assert len(feed) == 2

    def test_get_feed_excludes_blocked_users(self):
        author = UserFactory()
        blocked_author = UserFactory()
        viewer = UserFactory()
        PrayerFactory(author=author)
        PrayerFactory(author=blocked_author)
        BlockRelationshipFactory(blocker=viewer, blocked=blocked_author)

        feed = list(self.service.get_feed(requesting_user=viewer))
        assert len(feed) == 1

    def test_get_feed_excludes_users_who_blocked_viewer(self):
        blocker = UserFactory()
        viewer = UserFactory()
        PrayerFactory(author=blocker)
        PrayerFactory(author=UserFactory())
        BlockRelationshipFactory(blocker=blocker, blocked=viewer)

        feed = list(self.service.get_feed(requesting_user=viewer))
        assert len(feed) == 1

    def test_get_by_id_for_user_success(self):
        prayer = PrayerFactory()
        viewer = UserFactory()
        result = self.service.get_by_id_for_user(prayer.pk, requesting_user=viewer)
        assert result.pk == prayer.pk

    def test_get_by_id_for_user_blocked_raises_not_found(self):
        author = UserFactory()
        viewer = UserFactory()
        prayer = PrayerFactory(author=author)
        BlockRelationshipFactory(blocker=author, blocked=viewer)
        with pytest.raises(NotFoundError):
            self.service.get_by_id_for_user(prayer.pk, requesting_user=viewer)

    def test_get_by_id_for_user_nonexistent_raises_not_found(self):
        viewer = UserFactory()
        with pytest.raises(NotFoundError):
            self.service.get_by_id_for_user(uuid.uuid4(), requesting_user=viewer)

    def test_delete_prayer_by_author(self):
        user = UserFactory()
        prayer = self.service.create_prayer(author=user, title="To delete")
        self.service.delete_prayer(prayer_id=prayer.pk, requesting_user=user)
        assert not Prayer.objects.filter(pk=prayer.pk).exists()

    def test_delete_prayer_by_non_author_raises_forbidden(self):
        author = UserFactory()
        other = UserFactory()
        prayer = PrayerFactory(author=author)
        with pytest.raises(ForbiddenError, match="only delete your own"):
            self.service.delete_prayer(prayer_id=prayer.pk, requesting_user=other)

    def test_delete_prayer_nonexistent_raises_not_found(self):
        user = UserFactory()
        with pytest.raises(NotFoundError):
            self.service.delete_prayer(prayer_id=uuid.uuid4(), requesting_user=user)

    def test_share_prayer(self):
        prayer = PrayerFactory(title="Heal me")
        share_data = self.service.share_prayer(prayer_id=prayer.pk)
        assert share_data["type"] == "prayer"
        assert share_data["id"] == str(prayer.pk)
        assert f"bibleway://prayers/{prayer.pk}" == share_data["deep_link"]
        assert share_data["preview"] == "Heal me"

    def test_share_prayer_truncates_preview(self):
        long_title = "B" * 200
        prayer = PrayerFactory(title=long_title)
        share_data = self.service.share_prayer(prayer_id=prayer.pk)
        assert len(share_data["preview"]) == 100

    def test_share_prayer_nonexistent_raises_not_found(self):
        with pytest.raises(NotFoundError):
            self.service.share_prayer(prayer_id=uuid.uuid4())

    def test_get_user_prayers(self):
        author = UserFactory()
        viewer = UserFactory()
        PrayerFactory(author=author)
        PrayerFactory(author=author)
        PrayerFactory(author=UserFactory())
        prayers = list(
            self.service.get_user_prayers(user_id=author.pk, requesting_user=viewer)
        )
        assert len(prayers) == 2

    def test_get_user_prayers_blocked_returns_empty(self):
        author = UserFactory()
        viewer = UserFactory()
        PrayerFactory(author=author)
        BlockRelationshipFactory(blocker=author, blocked=viewer)
        prayers = list(
            self.service.get_user_prayers(user_id=author.pk, requesting_user=viewer)
        )
        assert len(prayers) == 0

    def test_get_feed_annotates_counts(self):
        author = UserFactory()
        prayer = PrayerFactory(author=author)
        ct = ContentType.objects.get_for_model(Prayer)
        Reaction.objects.create(
            user=UserFactory(), content_type=ct, object_id=prayer.pk, emoji_type="amen"
        )
        Comment.objects.create(
            user=UserFactory(), content_type=ct, object_id=prayer.pk, text="Praying!"
        )

        viewer = UserFactory()
        feed = list(self.service.get_feed(requesting_user=viewer))
        assert len(feed) == 1
        assert feed[0].reaction_count == 1
        assert feed[0].comment_count == 1


# ──────────────────────────────────────────────────────────────
# ReactionService
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestReactionService:
    """Tests for ReactionService."""

    def test_toggle_reaction_create_new(self):
        user = UserFactory()
        post = PostFactory()
        reaction = ReactionService.toggle_reaction(
            user=user,
            content_type_model="post",
            object_id=post.pk,
            emoji_type="heart",
        )
        assert reaction is not None
        assert reaction.emoji_type == "heart"
        assert reaction.user == user
        assert Reaction.objects.count() == 1

    def test_toggle_reaction_same_emoji_removes(self):
        user = UserFactory()
        post = PostFactory()
        # Create
        ReactionService.toggle_reaction(
            user=user,
            content_type_model="post",
            object_id=post.pk,
            emoji_type="heart",
        )
        assert Reaction.objects.count() == 1
        # Toggle off
        result = ReactionService.toggle_reaction(
            user=user,
            content_type_model="post",
            object_id=post.pk,
            emoji_type="heart",
        )
        assert result is None
        assert Reaction.objects.count() == 0

    def test_toggle_reaction_different_emoji_updates(self):
        user = UserFactory()
        post = PostFactory()
        # Create with heart
        ReactionService.toggle_reaction(
            user=user,
            content_type_model="post",
            object_id=post.pk,
            emoji_type="heart",
        )
        # Change to fire
        reaction = ReactionService.toggle_reaction(
            user=user,
            content_type_model="post",
            object_id=post.pk,
            emoji_type="fire",
        )
        assert reaction is not None
        assert reaction.emoji_type == "fire"
        assert Reaction.objects.count() == 1

    def test_toggle_reaction_on_prayer(self):
        user = UserFactory()
        prayer = PrayerFactory()
        reaction = ReactionService.toggle_reaction(
            user=user,
            content_type_model="prayer",
            object_id=prayer.pk,
            emoji_type="amen",
        )
        assert reaction is not None
        assert reaction.emoji_type == "amen"

    def test_toggle_reaction_invalid_content_type(self):
        user = UserFactory()
        with pytest.raises(BadRequestError, match="Invalid content type"):
            ReactionService.toggle_reaction(
                user=user,
                content_type_model="comment",
                object_id=uuid.uuid4(),
                emoji_type="heart",
            )

    def test_toggle_reaction_nonexistent_object(self):
        user = UserFactory()
        with pytest.raises(NotFoundError, match="not found"):
            ReactionService.toggle_reaction(
                user=user,
                content_type_model="post",
                object_id=uuid.uuid4(),
                emoji_type="heart",
            )

    def test_toggle_reaction_blocked_user_raises_forbidden(self):
        user = UserFactory()
        author = UserFactory()
        post = PostFactory(author=author)
        BlockRelationshipFactory(blocker=author, blocked=user)
        with pytest.raises(ForbiddenError, match="cannot interact"):
            ReactionService.toggle_reaction(
                user=user,
                content_type_model="post",
                object_id=post.pk,
                emoji_type="heart",
            )

    def test_remove_reaction_success(self):
        user = UserFactory()
        post = PostFactory()
        ReactionService.toggle_reaction(
            user=user,
            content_type_model="post",
            object_id=post.pk,
            emoji_type="heart",
        )
        ReactionService.remove_reaction(
            user=user, content_type_model="post", object_id=post.pk
        )
        assert Reaction.objects.count() == 0

    def test_remove_reaction_not_found(self):
        user = UserFactory()
        post = PostFactory()
        with pytest.raises(NotFoundError, match="No reaction found"):
            ReactionService.remove_reaction(
                user=user, content_type_model="post", object_id=post.pk
            )

    def test_get_reactions_for_content(self):
        post = PostFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        ReactionService.toggle_reaction(
            user=user1, content_type_model="post", object_id=post.pk, emoji_type="heart"
        )
        ReactionService.toggle_reaction(
            user=user2, content_type_model="post", object_id=post.pk, emoji_type="fire"
        )
        reactions = list(
            ReactionService.get_reactions_for_content(
                content_type_model="post", object_id=post.pk
            )
        )
        assert len(reactions) == 2

    def test_get_reactions_for_content_empty(self):
        post = PostFactory()
        reactions = list(
            ReactionService.get_reactions_for_content(
                content_type_model="post", object_id=post.pk
            )
        )
        assert len(reactions) == 0

    def test_get_reaction_count(self):
        post = PostFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        user3 = UserFactory()
        ReactionService.toggle_reaction(
            user=user1, content_type_model="post", object_id=post.pk, emoji_type="heart"
        )
        ReactionService.toggle_reaction(
            user=user2, content_type_model="post", object_id=post.pk, emoji_type="heart"
        )
        ReactionService.toggle_reaction(
            user=user3, content_type_model="post", object_id=post.pk, emoji_type="fire"
        )
        counts = ReactionService.get_reaction_count(
            content_type_model="post", object_id=post.pk
        )
        assert counts["heart"] == 2
        assert counts["fire"] == 1
        assert counts["total"] == 3

    def test_get_reaction_count_empty(self):
        post = PostFactory()
        counts = ReactionService.get_reaction_count(
            content_type_model="post", object_id=post.pk
        )
        assert counts["total"] == 0

    def test_toggle_reaction_all_emoji_types(self):
        """Verify all emoji types can be used."""
        user = UserFactory()
        for emoji in ["praying_hands", "heart", "fire", "amen", "cross"]:
            post = PostFactory()
            reaction = ReactionService.toggle_reaction(
                user=user,
                content_type_model="post",
                object_id=post.pk,
                emoji_type=emoji,
            )
            assert reaction.emoji_type == emoji


# ──────────────────────────────────────────────────────────────
# CommentService
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCommentService:
    """Tests for CommentService."""

    def setup_method(self):
        self.service = CommentService()

    def test_create_comment_on_post(self):
        user = UserFactory()
        post = PostFactory()
        comment = self.service.create_comment(
            user=user,
            content_type_model="post",
            object_id=post.pk,
            text="Nice post!",
        )
        assert comment.text == "Nice post!"
        assert comment.user == user
        assert comment.content_type.model == "post"
        assert comment.object_id == post.pk

    def test_create_comment_on_prayer(self):
        user = UserFactory()
        prayer = PrayerFactory()
        comment = self.service.create_comment(
            user=user,
            content_type_model="prayer",
            object_id=prayer.pk,
            text="Praying for you!",
        )
        assert comment.content_type.model == "prayer"

    def test_create_comment_invalid_content_type(self):
        user = UserFactory()
        with pytest.raises(BadRequestError, match="Invalid content type"):
            self.service.create_comment(
                user=user,
                content_type_model="user",
                object_id=uuid.uuid4(),
                text="Hello",
            )

    def test_create_comment_nonexistent_object(self):
        user = UserFactory()
        with pytest.raises(NotFoundError, match="not found"):
            self.service.create_comment(
                user=user,
                content_type_model="post",
                object_id=uuid.uuid4(),
                text="Hello",
            )

    def test_create_comment_blocked_raises_forbidden(self):
        user = UserFactory()
        author = UserFactory()
        post = PostFactory(author=author)
        BlockRelationshipFactory(blocker=author, blocked=user)
        with pytest.raises(ForbiddenError, match="cannot interact"):
            self.service.create_comment(
                user=user,
                content_type_model="post",
                object_id=post.pk,
                text="Hello",
            )

    def test_list_comments_for_content(self):
        post = PostFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        ct = ContentType.objects.get_for_model(Post)
        Comment.objects.create(
            user=user1, content_type=ct, object_id=post.pk, text="Comment 1"
        )
        Comment.objects.create(
            user=user2, content_type=ct, object_id=post.pk, text="Comment 2"
        )
        comments = list(
            self.service.list_comments_for_content(
                content_type_model="post", object_id=post.pk
            )
        )
        assert len(comments) == 2

    def test_list_comments_for_content_empty(self):
        post = PostFactory()
        comments = list(
            self.service.list_comments_for_content(
                content_type_model="post", object_id=post.pk
            )
        )
        assert len(comments) == 0

    def test_list_comments_for_nonexistent_content(self):
        with pytest.raises(NotFoundError):
            list(
                self.service.list_comments_for_content(
                    content_type_model="post", object_id=uuid.uuid4()
                )
            )

    def test_delete_comment_by_author(self):
        user = UserFactory()
        post = PostFactory()
        comment = self.service.create_comment(
            user=user, content_type_model="post", object_id=post.pk, text="To delete"
        )
        self.service.delete_comment(comment_id=comment.pk, requesting_user=user)
        assert not Comment.objects.filter(pk=comment.pk).exists()

    def test_delete_comment_by_non_author_raises_forbidden(self):
        user = UserFactory()
        other = UserFactory()
        post = PostFactory()
        comment = self.service.create_comment(
            user=user, content_type_model="post", object_id=post.pk, text="My comment"
        )
        with pytest.raises(ForbiddenError, match="only delete your own"):
            self.service.delete_comment(comment_id=comment.pk, requesting_user=other)

    def test_delete_comment_nonexistent_raises_not_found(self):
        user = UserFactory()
        with pytest.raises(NotFoundError):
            self.service.delete_comment(
                comment_id=uuid.uuid4(), requesting_user=user
            )

    def test_list_comments_annotates_reply_count(self):
        user = UserFactory()
        post = PostFactory()
        comment = self.service.create_comment(
            user=user, content_type_model="post", object_id=post.pk, text="Hello"
        )
        Reply.objects.create(user=UserFactory(), comment=comment, text="Reply 1")
        Reply.objects.create(user=UserFactory(), comment=comment, text="Reply 2")

        comments = list(
            self.service.list_comments_for_content(
                content_type_model="post", object_id=post.pk
            )
        )
        assert len(comments) == 1
        assert comments[0].reply_count == 2


# ──────────────────────────────────────────────────────────────
# ReplyService
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestReplyService:
    """Tests for ReplyService."""

    def setup_method(self):
        self.service = ReplyService()

    def _make_comment(self, user=None, post=None):
        """Helper to create a comment on a post."""
        user = user or UserFactory()
        post = post or PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        return Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Test comment"
        )

    def test_create_reply(self):
        user = UserFactory()
        comment = self._make_comment()
        reply = self.service.create_reply(
            user=user, comment_id=comment.pk, text="My reply"
        )
        assert reply.text == "My reply"
        assert reply.user == user
        assert reply.comment == comment

    def test_create_reply_nonexistent_comment_raises_not_found(self):
        user = UserFactory()
        with pytest.raises(NotFoundError, match="Comment.*not found"):
            self.service.create_reply(
                user=user, comment_id=uuid.uuid4(), text="Reply"
            )

    def test_create_reply_blocked_user_raises_forbidden(self):
        author = UserFactory()
        blocker_user = UserFactory()
        post = PostFactory(author=blocker_user)
        comment = self._make_comment(user=author, post=post)
        replying_user = UserFactory()
        BlockRelationshipFactory(blocker=blocker_user, blocked=replying_user)

        with pytest.raises(ForbiddenError, match="cannot interact"):
            self.service.create_reply(
                user=replying_user, comment_id=comment.pk, text="Reply"
            )

    def test_list_replies_for_comment(self):
        comment = self._make_comment()
        Reply.objects.create(user=UserFactory(), comment=comment, text="Reply 1")
        Reply.objects.create(user=UserFactory(), comment=comment, text="Reply 2")
        replies = list(self.service.list_replies_for_comment(comment_id=comment.pk))
        assert len(replies) == 2

    def test_list_replies_for_comment_ordered_oldest_first(self):
        comment = self._make_comment()
        r1 = Reply.objects.create(user=UserFactory(), comment=comment, text="First")
        r2 = Reply.objects.create(user=UserFactory(), comment=comment, text="Second")
        replies = list(self.service.list_replies_for_comment(comment_id=comment.pk))
        assert replies[0].pk == r1.pk
        assert replies[1].pk == r2.pk

    def test_list_replies_for_nonexistent_comment_raises_not_found(self):
        with pytest.raises(NotFoundError, match="Comment.*not found"):
            list(
                self.service.list_replies_for_comment(comment_id=uuid.uuid4())
            )

    def test_list_replies_for_comment_empty(self):
        comment = self._make_comment()
        replies = list(self.service.list_replies_for_comment(comment_id=comment.pk))
        assert len(replies) == 0

    def test_delete_reply_by_author(self):
        user = UserFactory()
        comment = self._make_comment()
        reply = self.service.create_reply(
            user=user, comment_id=comment.pk, text="To delete"
        )
        self.service.delete_reply(reply_id=reply.pk, requesting_user=user)
        assert not Reply.objects.filter(pk=reply.pk).exists()

    def test_delete_reply_by_non_author_raises_forbidden(self):
        user = UserFactory()
        other = UserFactory()
        comment = self._make_comment()
        reply = self.service.create_reply(
            user=user, comment_id=comment.pk, text="My reply"
        )
        with pytest.raises(ForbiddenError, match="only delete your own"):
            self.service.delete_reply(reply_id=reply.pk, requesting_user=other)

    def test_delete_reply_nonexistent_raises_not_found(self):
        user = UserFactory()
        with pytest.raises(NotFoundError):
            self.service.delete_reply(reply_id=uuid.uuid4(), requesting_user=user)


# ──────────────────────────────────────────────────────────────
# ReportService
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestReportService:
    """Tests for ReportService."""

    def setup_method(self):
        self.service = ReportService()

    def test_create_report_on_post(self):
        reporter = UserFactory()
        post = PostFactory()
        report = self.service.create_report(
            reporter=reporter,
            content_type_model="post",
            object_id=post.pk,
            reason="spam",
            description="This is spam",
        )
        assert report.reason == "spam"
        assert report.description == "This is spam"
        assert report.status == Report.Status.PENDING
        assert report.reporter == reporter

    def test_create_report_on_prayer(self):
        reporter = UserFactory()
        prayer = PrayerFactory()
        report = self.service.create_report(
            reporter=reporter,
            content_type_model="prayer",
            object_id=prayer.pk,
            reason="inappropriate",
        )
        assert report.content_type.model == "prayer"

    def test_create_report_on_comment(self):
        reporter = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=UserFactory(), content_type=ct, object_id=post.pk, text="Bad comment"
        )
        report = self.service.create_report(
            reporter=reporter,
            content_type_model="comment",
            object_id=comment.pk,
            reason="false_teaching",
        )
        assert report.content_type.model == "comment"

    def test_create_report_on_user(self):
        reporter = UserFactory()
        target_user = UserFactory()
        report = self.service.create_report(
            reporter=reporter,
            content_type_model="user",
            object_id=target_user.pk,
            reason="other",
            description="Suspicious account",
        )
        assert report.content_type.model == "user"

    def test_create_report_self_reporting_raises_bad_request(self):
        user = UserFactory()
        post = PostFactory(author=user)
        with pytest.raises(BadRequestError, match="cannot report your own"):
            self.service.create_report(
                reporter=user,
                content_type_model="post",
                object_id=post.pk,
                reason="spam",
            )

    def test_create_report_self_reporting_user_model_allowed(self):
        """The User model has no author/user FK, so _get_content_author_id
        returns None and the self-report check is skipped. This verifies the
        current behavior (self-reporting on the 'user' content type is not
        blocked by the service layer)."""
        user = UserFactory()
        report = self.service.create_report(
            reporter=user,
            content_type_model="user",
            object_id=user.pk,
            reason="spam",
        )
        # The report is created because User model lacks author/user FK.
        assert report.pk is not None

    def test_create_report_duplicate_pending_raises_bad_request(self):
        reporter = UserFactory()
        post = PostFactory()
        self.service.create_report(
            reporter=reporter,
            content_type_model="post",
            object_id=post.pk,
            reason="spam",
        )
        with pytest.raises(BadRequestError, match="already filed a pending report"):
            self.service.create_report(
                reporter=reporter,
                content_type_model="post",
                object_id=post.pk,
                reason="inappropriate",
            )

    def test_create_report_allows_after_previous_reviewed(self):
        reporter = UserFactory()
        post = PostFactory()
        report = self.service.create_report(
            reporter=reporter,
            content_type_model="post",
            object_id=post.pk,
            reason="spam",
        )
        # Mark the first report as reviewed
        report.status = Report.Status.REVIEWED
        report.save(update_fields=["status"])

        # Now a new pending report should be allowed
        new_report = self.service.create_report(
            reporter=reporter,
            content_type_model="post",
            object_id=post.pk,
            reason="inappropriate",
        )
        assert new_report.pk != report.pk
        assert new_report.status == Report.Status.PENDING

    def test_create_report_allows_after_previous_dismissed(self):
        reporter = UserFactory()
        post = PostFactory()
        report = self.service.create_report(
            reporter=reporter,
            content_type_model="post",
            object_id=post.pk,
            reason="spam",
        )
        report.status = Report.Status.DISMISSED
        report.save(update_fields=["status"])

        new_report = self.service.create_report(
            reporter=reporter,
            content_type_model="post",
            object_id=post.pk,
            reason="spam",
        )
        assert new_report.status == Report.Status.PENDING

    def test_create_report_nonexistent_object(self):
        reporter = UserFactory()
        with pytest.raises(NotFoundError, match="not found"):
            self.service.create_report(
                reporter=reporter,
                content_type_model="post",
                object_id=uuid.uuid4(),
                reason="spam",
            )

    def test_create_report_invalid_content_type(self):
        reporter = UserFactory()
        with pytest.raises(BadRequestError, match="Invalid content type"):
            self.service.create_report(
                reporter=reporter,
                content_type_model="invalid",
                object_id=uuid.uuid4(),
                reason="spam",
            )

    def test_list_pending_reports(self):
        reporter = UserFactory()
        post1 = PostFactory()
        post2 = PostFactory()
        post3 = PostFactory()

        self.service.create_report(
            reporter=reporter,
            content_type_model="post",
            object_id=post1.pk,
            reason="spam",
        )
        r2 = self.service.create_report(
            reporter=reporter,
            content_type_model="post",
            object_id=post2.pk,
            reason="inappropriate",
        )
        self.service.create_report(
            reporter=reporter,
            content_type_model="post",
            object_id=post3.pk,
            reason="other",
        )
        # Mark one as reviewed
        r2.status = Report.Status.REVIEWED
        r2.save(update_fields=["status"])

        pending = list(self.service.list_pending_reports())
        assert len(pending) == 2
        assert all(r.status == Report.Status.PENDING for r in pending)

    def test_list_pending_reports_empty(self):
        pending = list(self.service.list_pending_reports())
        assert len(pending) == 0

    def test_create_report_all_reason_types(self):
        reporter = UserFactory()
        for reason in ["inappropriate", "spam", "false_teaching", "other"]:
            post = PostFactory()
            report = self.service.create_report(
                reporter=reporter,
                content_type_model="post",
                object_id=post.pk,
                reason=reason,
            )
            assert report.reason == reason

    def test_different_reporters_can_report_same_content(self):
        reporter1 = UserFactory()
        reporter2 = UserFactory()
        post = PostFactory()
        r1 = self.service.create_report(
            reporter=reporter1,
            content_type_model="post",
            object_id=post.pk,
            reason="spam",
        )
        r2 = self.service.create_report(
            reporter=reporter2,
            content_type_model="post",
            object_id=post.pk,
            reason="spam",
        )
        assert r1.pk != r2.pk
        assert Report.objects.filter(object_id=post.pk).count() == 2
