"""Tests for social app API views."""

from __future__ import annotations
import uuid
import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from rest_framework import status
from apps.social.models import Comment, Post, Prayer, Reaction, Reply, Report
from conftest import (
    BlockRelationshipFactory,
    PostFactory,
    PrayerFactory,
    UserFactory,
)

POSTS_URL = "/api/v1/social/posts/"

PRAYERS_URL = "/api/v1/social/prayers/"

COMMENTS_URL = "/api/v1/social/comments/"

REPORTS_URL = "/api/v1/social/reports/"

REPORTS_PENDING_URL = "/api/v1/social/reports/pending/"


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the cache before each test to avoid stale blocked-user data."""

    cache.clear()

    yield

    cache.clear()


@pytest.mark.django_db
class TestPostViewSetCreate:
    """Tests for POST /api/v1/social/posts/."""

    def test_create_post_text_only(self, auth_client, user):
        response = auth_client.post(POSTS_URL, {"text_content": "Hello world"})
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["text_content"] == "Hello world"
        assert Post.objects.filter(author=user).count() == 1

    def test_create_post_empty_fails(self, auth_client):
        response = auth_client.post(POSTS_URL, {"text_content": ""})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_post_unauthenticated(self, api_client):
        response = api_client.post(POSTS_URL, {"text_content": "Hello"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_post_returns_author_info(self, auth_client, user):
        response = auth_client.post(POSTS_URL, {"text_content": "My post"})
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["author"]["id"] == str(user.pk)

    def test_create_post_returns_default_counts(self, auth_client):
        response = auth_client.post(POSTS_URL, {"text_content": "My post"})
        data = response.json()
        assert data.get("reaction_count", 0) == 0
        assert data.get("comment_count", 0) == 0


@pytest.mark.django_db
class TestPostViewSetList:
    """Tests for GET /api/v1/social/posts/ (feed)."""

    def test_list_posts_authenticated(self, auth_client, user):
        PostFactory(author=user, text_content="Post 1")
        PostFactory(author=user, text_content="Post 2")
        response = auth_client.get(POSTS_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("data", data).get("results", data.get("results", []))
        assert len(results) == 2

    def test_list_posts_unauthenticated(self, api_client):
        response = api_client.get(POSTS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_posts_excludes_blocked_users(self, auth_client, user):
        blocked_author = UserFactory()
        PostFactory(author=blocked_author)
        visible_author = UserFactory()
        PostFactory(author=visible_author)
        BlockRelationshipFactory(blocker=user, blocked=blocked_author)
        response = auth_client.get(POSTS_URL)
        data = response.json()
        results = data.get("data", data).get("results", data.get("results", []))
        assert len(results) == 1

    def test_list_posts_cursor_pagination(self, auth_client, user):
        for i in range(25):
            PostFactory(author=user, text_content=f"Post {i}")

        response = auth_client.get(POSTS_URL)
        data = response.json()
        envelope = data.get("data", data)
        results = envelope.get("results", [])
        assert len(results) == 20
        assert envelope.get("next") is not None


@pytest.mark.django_db
class TestPostViewSetRetrieve:
    """Tests for GET /api/v1/social/posts/{id}/."""

    def test_retrieve_post(self, auth_client):
        post = PostFactory(text_content="Detail post")
        response = auth_client.get(f"{POSTS_URL}{post.pk}/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(post.pk)
        assert data["text_content"] == "Detail post"

    def test_retrieve_post_nonexistent(self, auth_client):
        response = auth_client.get(f"{POSTS_URL}{uuid.uuid4()}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_post_from_blocked_user(self, auth_client, user):
        blocked = UserFactory()
        post = PostFactory(author=blocked)
        BlockRelationshipFactory(blocker=blocked, blocked=user)
        response = auth_client.get(f"{POSTS_URL}{post.pk}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPostViewSetDestroy:
    """Tests for DELETE /api/v1/social/posts/{id}/."""

    def test_delete_own_post(self, auth_client, user):
        post = PostFactory(author=user)
        response = auth_client.delete(f"{POSTS_URL}{post.pk}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Post.objects.filter(pk=post.pk).exists()

    def test_delete_other_user_post_forbidden(self, auth_client, user):
        other = UserFactory()
        post = PostFactory(author=other)
        response = auth_client.delete(f"{POSTS_URL}{post.pk}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Post.objects.filter(pk=post.pk).exists()

    def test_delete_nonexistent_post(self, auth_client):
        response = auth_client.delete(f"{POSTS_URL}{uuid.uuid4()}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPostViewSetReact:
    """Tests for POST /api/v1/social/posts/{id}/react/."""

    def test_react_to_post_creates_reaction(self, auth_client, user):
        post = PostFactory()
        response = auth_client.post(
            f"{POSTS_URL}{post.pk}/react/", {"emoji_type": "heart"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Reaction.objects.filter(user=user).count() == 1

    def test_react_toggle_off_same_emoji(self, auth_client, user):
        post = PostFactory()
        auth_client.post(f"{POSTS_URL}{post.pk}/react/", {"emoji_type": "heart"})
        assert Reaction.objects.count() == 1
        response = auth_client.post(
            f"{POSTS_URL}{post.pk}/react/", {"emoji_type": "heart"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert Reaction.objects.count() == 0
        assert response.json()["message"] == "Reaction removed."

    def test_react_change_emoji(self, auth_client, user):
        post = PostFactory()
        auth_client.post(f"{POSTS_URL}{post.pk}/react/", {"emoji_type": "heart"})
        response = auth_client.post(
            f"{POSTS_URL}{post.pk}/react/", {"emoji_type": "fire"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Reaction.objects.count() == 1
        assert Reaction.objects.first().emoji_type == "fire"

    def test_react_invalid_emoji_type(self, auth_client):
        post = PostFactory()
        response = auth_client.post(
            f"{POSTS_URL}{post.pk}/react/", {"emoji_type": "invalid"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_react_to_nonexistent_post(self, auth_client):
        response = auth_client.post(
            f"{POSTS_URL}{uuid.uuid4()}/react/", {"emoji_type": "heart"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_react_blocked_user(self, auth_client, user):
        author = UserFactory()
        post = PostFactory(author=author)
        BlockRelationshipFactory(blocker=author, blocked=user)
        response = auth_client.post(
            f"{POSTS_URL}{post.pk}/react/", {"emoji_type": "heart"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_react_missing_emoji_type(self, auth_client):
        post = PostFactory()
        response = auth_client.post(f"{POSTS_URL}{post.pk}/react/", {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPostViewSetComments:
    """Tests for GET/POST /api/v1/social/posts/{id}/comments/."""

    def test_list_comments_on_post(self, auth_client, user):
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Comment.objects.create(
            user=UserFactory(), content_type=ct, object_id=post.pk, text="Comment 1"
        )
        Comment.objects.create(
            user=UserFactory(), content_type=ct, object_id=post.pk, text="Comment 2"
        )
        response = auth_client.get(f"{POSTS_URL}{post.pk}/comments/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("data", data).get("results", data.get("results", []))
        assert len(results) == 2

    def test_create_comment_on_post(self, auth_client, user):
        post = PostFactory()
        response = auth_client.post(
            f"{POSTS_URL}{post.pk}/comments/", {"text": "Nice post!"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Comment.objects.filter(user=user).count() == 1

    def test_create_comment_empty_text_fails(self, auth_client):
        post = PostFactory()
        response = auth_client.post(f"{POSTS_URL}{post.pk}/comments/", {"text": ""})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_comments_excludes_blocked_user_comments(self, auth_client, user):
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        blocked_user = UserFactory()
        visible_user = UserFactory()
        Comment.objects.create(
            user=blocked_user, content_type=ct, object_id=post.pk, text="Hidden"
        )
        Comment.objects.create(
            user=visible_user, content_type=ct, object_id=post.pk, text="Visible"
        )
        BlockRelationshipFactory(blocker=user, blocked=blocked_user)
        response = auth_client.get(f"{POSTS_URL}{post.pk}/comments/")
        data = response.json()
        results = data.get("data", data).get("results", data.get("results", []))
        assert len(results) == 1

    def test_create_comment_blocked_user_forbidden(self, auth_client, user):
        author = UserFactory()
        post = PostFactory(author=author)
        BlockRelationshipFactory(blocker=author, blocked=user)
        response = auth_client.post(
            f"{POSTS_URL}{post.pk}/comments/", {"text": "Hello"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestPostViewSetShare:
    """Tests for GET /api/v1/social/posts/{id}/share/."""

    def test_share_post(self, auth_client):
        post = PostFactory(text_content="Share me!")
        response = auth_client.get(f"{POSTS_URL}{post.pk}/share/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["type"] == "post"
        assert data["id"] == str(post.pk)
        assert f"bibleway://posts/{post.pk}" == data["deep_link"]

    def test_share_nonexistent_post(self, auth_client):
        response = auth_client.get(f"{POSTS_URL}{uuid.uuid4()}/share/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPrayerViewSetCreate:
    """Tests for POST /api/v1/social/prayers/."""

    def test_create_prayer(self, auth_client, user):
        response = auth_client.post(
            PRAYERS_URL,
            {"title": "Pray for me", "description": "I need prayer"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == "Pray for me"
        assert data["description"] == "I need prayer"
        assert Prayer.objects.filter(author=user).count() == 1

    def test_create_prayer_title_only(self, auth_client, user):
        response = auth_client.post(PRAYERS_URL, {"title": "Just a title"})
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_prayer_missing_title(self, auth_client):
        response = auth_client.post(PRAYERS_URL, {"description": "No title"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_prayer_unauthenticated(self, api_client):
        response = api_client.post(PRAYERS_URL, {"title": "Test"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_prayer_returns_author_info(self, auth_client, user):
        response = auth_client.post(PRAYERS_URL, {"title": "My prayer"})
        data = response.json()
        assert data["author"]["id"] == str(user.pk)


@pytest.mark.django_db
class TestPrayerViewSetList:
    """Tests for GET /api/v1/social/prayers/ (feed)."""

    def test_list_prayers_authenticated(self, auth_client, user):
        PrayerFactory(author=user)
        PrayerFactory(author=user)
        response = auth_client.get(PRAYERS_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("data", data).get("results", data.get("results", []))
        assert len(results) == 2

    def test_list_prayers_unauthenticated(self, api_client):
        response = api_client.get(PRAYERS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_prayers_excludes_blocked_users(self, auth_client, user):
        blocked = UserFactory()
        PrayerFactory(author=blocked)
        visible = UserFactory()
        PrayerFactory(author=visible)
        BlockRelationshipFactory(blocker=user, blocked=blocked)
        response = auth_client.get(PRAYERS_URL)
        data = response.json()
        results = data.get("data", data).get("results", data.get("results", []))
        assert len(results) == 1


@pytest.mark.django_db
class TestPrayerViewSetRetrieve:
    """Tests for GET /api/v1/social/prayers/{id}/."""

    def test_retrieve_prayer(self, auth_client):
        prayer = PrayerFactory(title="Detail prayer")
        response = auth_client.get(f"{PRAYERS_URL}{prayer.pk}/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(prayer.pk)
        assert data["title"] == "Detail prayer"

    def test_retrieve_prayer_nonexistent(self, auth_client):
        response = auth_client.get(f"{PRAYERS_URL}{uuid.uuid4()}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_prayer_from_blocked_user(self, auth_client, user):
        blocked = UserFactory()
        prayer = PrayerFactory(author=blocked)
        BlockRelationshipFactory(blocker=blocked, blocked=user)
        response = auth_client.get(f"{PRAYERS_URL}{prayer.pk}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPrayerViewSetDestroy:
    """Tests for DELETE /api/v1/social/prayers/{id}/."""

    def test_delete_own_prayer(self, auth_client, user):
        prayer = PrayerFactory(author=user)
        response = auth_client.delete(f"{PRAYERS_URL}{prayer.pk}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Prayer.objects.filter(pk=prayer.pk).exists()

    def test_delete_other_user_prayer_forbidden(self, auth_client):
        other = UserFactory()
        prayer = PrayerFactory(author=other)
        response = auth_client.delete(f"{PRAYERS_URL}{prayer.pk}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_nonexistent_prayer(self, auth_client):
        response = auth_client.delete(f"{PRAYERS_URL}{uuid.uuid4()}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPrayerViewSetReact:
    """Tests for POST /api/v1/social/prayers/{id}/react/."""

    def test_react_to_prayer(self, auth_client, user):
        prayer = PrayerFactory()
        response = auth_client.post(
            f"{PRAYERS_URL}{prayer.pk}/react/", {"emoji_type": "praying_hands"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Reaction.objects.filter(user=user).count() == 1

    def test_react_toggle_off_prayer(self, auth_client, user):
        prayer = PrayerFactory()
        auth_client.post(f"{PRAYERS_URL}{prayer.pk}/react/", {"emoji_type": "amen"})
        response = auth_client.post(
            f"{PRAYERS_URL}{prayer.pk}/react/", {"emoji_type": "amen"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert Reaction.objects.count() == 0

    def test_react_change_emoji_prayer(self, auth_client, user):
        prayer = PrayerFactory()
        auth_client.post(f"{PRAYERS_URL}{prayer.pk}/react/", {"emoji_type": "heart"})
        response = auth_client.post(
            f"{PRAYERS_URL}{prayer.pk}/react/", {"emoji_type": "cross"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Reaction.objects.first().emoji_type == "cross"

    def test_react_blocked_user_prayer(self, auth_client, user):
        author = UserFactory()
        prayer = PrayerFactory(author=author)
        BlockRelationshipFactory(blocker=author, blocked=user)
        response = auth_client.post(
            f"{PRAYERS_URL}{prayer.pk}/react/", {"emoji_type": "amen"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestPrayerViewSetComments:
    """Tests for GET/POST /api/v1/social/prayers/{id}/comments/."""

    def test_list_comments_on_prayer(self, auth_client):
        prayer = PrayerFactory()
        ct = ContentType.objects.get_for_model(Prayer)
        Comment.objects.create(
            user=UserFactory(), content_type=ct, object_id=prayer.pk, text="Praying!"
        )
        response = auth_client.get(f"{PRAYERS_URL}{prayer.pk}/comments/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("data", data).get("results", data.get("results", []))
        assert len(results) == 1

    def test_create_comment_on_prayer(self, auth_client, user):
        prayer = PrayerFactory()
        response = auth_client.post(
            f"{PRAYERS_URL}{prayer.pk}/comments/", {"text": "Praying for you!"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Comment.objects.filter(user=user).count() == 1


@pytest.mark.django_db
class TestPrayerViewSetShare:
    """Tests for GET /api/v1/social/prayers/{id}/share/."""

    def test_share_prayer(self, auth_client):
        prayer = PrayerFactory(title="Share prayer")
        response = auth_client.get(f"{PRAYERS_URL}{prayer.pk}/share/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["type"] == "prayer"
        assert data["id"] == str(prayer.pk)
        assert f"bibleway://prayers/{prayer.pk}" == data["deep_link"]

    def test_share_nonexistent_prayer(self, auth_client):
        response = auth_client.get(f"{PRAYERS_URL}{uuid.uuid4()}/share/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCommentViewSetDestroy:
    """Tests for DELETE /api/v1/social/comments/{id}/."""

    def test_delete_own_comment(self, auth_client, user):
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="My comment"
        )
        response = auth_client.delete(f"{COMMENTS_URL}{comment.pk}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Comment.objects.filter(pk=comment.pk).exists()

    def test_delete_other_user_comment_forbidden(self, auth_client, user):
        other = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=other, content_type=ct, object_id=post.pk, text="Other's comment"
        )
        response = auth_client.delete(f"{COMMENTS_URL}{comment.pk}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_nonexistent_comment(self, auth_client):
        response = auth_client.delete(f"{COMMENTS_URL}{uuid.uuid4()}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCommentViewSetList:
    """Tests for GET /api/v1/social/comments/?content_type_model=post&object_id=..."""

    def test_list_comments_with_query_params(self, auth_client):
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Comment.objects.create(
            user=UserFactory(), content_type=ct, object_id=post.pk, text="C1"
        )
        Comment.objects.create(
            user=UserFactory(), content_type=ct, object_id=post.pk, text="C2"
        )
        response = auth_client.get(
            COMMENTS_URL,
            {"content_type_model": "post", "object_id": str(post.pk)},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("data", data).get("results", data.get("results", []))
        assert len(results) == 2


def _make_comment(user=None, post=None):
    """Helper to create a comment on a post."""

    user = user or UserFactory()

    post = post or PostFactory()

    ct = ContentType.objects.get_for_model(Post)

    return Comment.objects.create(
        user=user, content_type=ct, object_id=post.pk, text="Test comment"
    )


@pytest.mark.django_db
class TestReplyViewSetList:
    """Tests for GET /api/v1/social/comments/{comment_pk}/replies/."""

    def test_list_replies(self, auth_client):
        comment = _make_comment()
        Reply.objects.create(user=UserFactory(), comment=comment, text="Reply 1")
        Reply.objects.create(user=UserFactory(), comment=comment, text="Reply 2")
        response = auth_client.get(f"{COMMENTS_URL}{comment.pk}/replies/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("data", data).get("results", data.get("results", []))
        assert len(results) == 2

    def test_list_replies_empty(self, auth_client):
        comment = _make_comment()
        response = auth_client.get(f"{COMMENTS_URL}{comment.pk}/replies/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("data", data).get("results", data.get("results", []))
        assert len(results) == 0

    def test_list_replies_nonexistent_comment(self, auth_client):
        response = auth_client.get(f"{COMMENTS_URL}{uuid.uuid4()}/replies/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestReplyViewSetCreate:
    """Tests for POST /api/v1/social/comments/{comment_pk}/replies/."""

    def test_create_reply(self, auth_client, user):
        comment = _make_comment()
        response = auth_client.post(
            f"{COMMENTS_URL}{comment.pk}/replies/", {"text": "My reply"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["text"] == "My reply"
        assert Reply.objects.filter(user=user, comment=comment).count() == 1

    def test_create_reply_empty_text_fails(self, auth_client):
        comment = _make_comment()
        response = auth_client.post(
            f"{COMMENTS_URL}{comment.pk}/replies/", {"text": ""}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_reply_nonexistent_comment(self, auth_client):
        response = auth_client.post(
            f"{COMMENTS_URL}{uuid.uuid4()}/replies/", {"text": "Reply"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_reply_blocked_user_forbidden(self, auth_client, user):
        blocker = UserFactory()
        post = PostFactory(author=blocker)
        comment = _make_comment(post=post)
        BlockRelationshipFactory(blocker=blocker, blocked=user)
        response = auth_client.post(
            f"{COMMENTS_URL}{comment.pk}/replies/", {"text": "Reply"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_reply_unauthenticated(self, api_client):
        comment = _make_comment()
        response = api_client.post(
            f"{COMMENTS_URL}{comment.pk}/replies/", {"text": "Reply"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestReplyViewSetDestroy:
    """Tests for DELETE /api/v1/social/comments/{comment_pk}/replies/{pk}/."""

    def test_delete_own_reply(self, auth_client, user):
        comment = _make_comment()
        reply = Reply.objects.create(user=user, comment=comment, text="My reply")
        response = auth_client.delete(f"{COMMENTS_URL}{comment.pk}/replies/{reply.pk}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Reply.objects.filter(pk=reply.pk).exists()

    def test_delete_other_user_reply_forbidden(self, auth_client, user):
        other = UserFactory()
        comment = _make_comment()
        reply = Reply.objects.create(user=other, comment=comment, text="Other's reply")
        response = auth_client.delete(f"{COMMENTS_URL}{comment.pk}/replies/{reply.pk}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_nonexistent_reply(self, auth_client):
        comment = _make_comment()
        response = auth_client.delete(
            f"{COMMENTS_URL}{comment.pk}/replies/{uuid.uuid4()}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestReportCreateView:
    """Tests for POST /api/v1/social/reports/."""

    def test_create_report(self, auth_client, user):
        post = PostFactory()
        response = auth_client.post(
            REPORTS_URL,
            {
                "content_type_model": "post",
                "object_id": str(post.pk),
                "reason": "spam",
                "description": "This is spam content",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["message"] == "Report submitted successfully."
        assert data["data"]["reason"] == "spam"
        assert data["data"]["status"] == "pending"
        assert Report.objects.filter(reporter=user).count() == 1

    def test_create_report_on_prayer(self, auth_client, user):
        prayer = PrayerFactory()
        response = auth_client.post(
            REPORTS_URL,
            {
                "content_type_model": "prayer",
                "object_id": str(prayer.pk),
                "reason": "inappropriate",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_report_on_comment(self, auth_client, user):
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=UserFactory(), content_type=ct, object_id=post.pk, text="Bad"
        )
        response = auth_client.post(
            REPORTS_URL,
            {
                "content_type_model": "comment",
                "object_id": str(comment.pk),
                "reason": "false_teaching",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_report_on_user(self, auth_client, user):
        target = UserFactory()
        response = auth_client.post(
            REPORTS_URL,
            {
                "content_type_model": "user",
                "object_id": str(target.pk),
                "reason": "other",
                "description": "Suspicious account",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_report_self_reporting_fails(self, auth_client, user):
        post = PostFactory(author=user)
        response = auth_client.post(
            REPORTS_URL,
            {
                "content_type_model": "post",
                "object_id": str(post.pk),
                "reason": "spam",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_report_duplicate_pending_fails(self, auth_client, user):
        post = PostFactory()
        auth_client.post(
            REPORTS_URL,
            {
                "content_type_model": "post",
                "object_id": str(post.pk),
                "reason": "spam",
            },
        )
        response = auth_client.post(
            REPORTS_URL,
            {
                "content_type_model": "post",
                "object_id": str(post.pk),
                "reason": "inappropriate",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_report_nonexistent_object(self, auth_client):
        response = auth_client.post(
            REPORTS_URL,
            {
                "content_type_model": "post",
                "object_id": str(uuid.uuid4()),
                "reason": "spam",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_report_invalid_reason(self, auth_client):
        post = PostFactory()
        response = auth_client.post(
            REPORTS_URL,
            {
                "content_type_model": "post",
                "object_id": str(post.pk),
                "reason": "invalid_reason",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_report_invalid_content_type(self, auth_client):
        response = auth_client.post(
            REPORTS_URL,
            {
                "content_type_model": "invalid",
                "object_id": str(uuid.uuid4()),
                "reason": "spam",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_report_unauthenticated(self, api_client):
        post = PostFactory()
        response = api_client.post(
            REPORTS_URL,
            {
                "content_type_model": "post",
                "object_id": str(post.pk),
                "reason": "spam",
            },
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_report_missing_fields(self, auth_client):
        response = auth_client.post(REPORTS_URL, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_report_without_description(self, auth_client, user):
        post = PostFactory()
        response = auth_client.post(
            REPORTS_URL,
            {
                "content_type_model": "post",
                "object_id": str(post.pk),
                "reason": "spam",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestReportListView:
    """Tests for GET /api/v1/social/reports/pending/."""

    def test_list_pending_reports_as_admin(self, admin_client, admin_user):
        reporter = UserFactory()
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Report.objects.create(
            reporter=reporter,
            content_type=ct,
            object_id=post.pk,
            reason="spam",
        )
        response = admin_client.get(REPORTS_PENDING_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Success"
        assert len(data["data"]) == 1
        assert data["data"][0]["reason"] == "spam"
        assert data["data"][0]["status"] == "pending"

    def test_list_pending_reports_non_admin_forbidden(self, auth_client):
        response = auth_client.get(REPORTS_PENDING_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_pending_reports_unauthenticated(self, api_client):
        response = api_client.get(REPORTS_PENDING_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_pending_reports_excludes_reviewed(self, admin_client, admin_user):
        reporter = UserFactory()
        post1 = PostFactory()
        post2 = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Report.objects.create(
            reporter=reporter,
            content_type=ct,
            object_id=post1.pk,
            reason="spam",
            status=Report.Status.PENDING,
        )
        Report.objects.create(
            reporter=reporter,
            content_type=ct,
            object_id=post2.pk,
            reason="inappropriate",
            status=Report.Status.REVIEWED,
        )
        response = admin_client.get(REPORTS_PENDING_URL)
        data = response.json()
        assert len(data["data"]) == 1

    def test_list_pending_reports_empty(self, admin_client, admin_user):
        response = admin_client.get(REPORTS_PENDING_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) == 0

    def test_list_pending_reports_contains_reporter_info(
        self, admin_client, admin_user
    ):

        reporter = UserFactory(full_name="Reporter Name")
        post = PostFactory()
        ct = ContentType.objects.get_for_model(Post)
        Report.objects.create(
            reporter=reporter,
            content_type=ct,
            object_id=post.pk,
            reason="spam",
        )
        response = admin_client.get(REPORTS_PENDING_URL)
        data = response.json()
        report_data = data["data"][0]
        assert report_data["reporter"]["id"] == str(reporter.pk)
        assert report_data["reporter"]["full_name"] == "Reporter Name"
        assert report_data["content_type"] == "post"
        assert "created_at" in report_data


@pytest.mark.django_db
class TestMultiUserInteractions:
    """Tests verifying interactions between multiple authenticated users."""

    def test_user2_can_comment_on_user1_post(
        self, auth_client, auth_client_user2, user, user2
    ):

        post = PostFactory(author=user)
        response = auth_client_user2.post(
            f"{POSTS_URL}{post.pk}/comments/", {"text": "Nice!"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Comment.objects.filter(user=user2, object_id=post.pk).count() == 1

    def test_user2_can_react_to_user1_post(self, auth_client_user2, user, user2):
        post = PostFactory(author=user)
        response = auth_client_user2.post(
            f"{POSTS_URL}{post.pk}/react/", {"emoji_type": "heart"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Reaction.objects.filter(user=user2).count() == 1

    def test_user1_cannot_delete_user2_post(self, auth_client, user2):
        post = PostFactory(author=user2)
        response = auth_client.delete(f"{POSTS_URL}{post.pk}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user2_can_reply_to_comment_on_user1_post(
        self, auth_client_user2, user, user2
    ):

        post = PostFactory(author=user)
        ct = ContentType.objects.get_for_model(Post)
        comment = Comment.objects.create(
            user=user, content_type=ct, object_id=post.pk, text="Comment"
        )
        response = auth_client_user2.post(
            f"{COMMENTS_URL}{comment.pk}/replies/", {"text": "Reply from user2"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Reply.objects.filter(user=user2).count() == 1

    def test_blocked_user_cannot_see_blocker_posts_in_feed(
        self, auth_client_user2, user, user2
    ):

        PostFactory(author=user)
        BlockRelationshipFactory(blocker=user, blocked=user2)
        response = auth_client_user2.get(POSTS_URL)
        data = response.json()
        results = data.get("data", data).get("results", data.get("results", []))
        assert len(results) == 0

    def test_user_who_blocked_cannot_see_blocked_user_posts(
        self, auth_client, user, user2
    ):

        PostFactory(author=user2)
        BlockRelationshipFactory(blocker=user, blocked=user2)
        response = auth_client.get(POSTS_URL)
        data = response.json()
        results = data.get("data", data).get("results", data.get("results", []))
        assert len(results) == 0


@pytest.mark.django_db
class TestBulkPostDetailView:
    """Tests for BulkPostDetailView.

    The view is registered at ``posts/bulk/`` but because the DRF router's
    ``posts/<pk>/`` pattern precedes it in URL resolution, the URL is
    currently shadowed. These tests exercise the view class directly via
    ``RequestFactory`` to validate its logic (input validation, blocked user
    filtering, serialization) independent of URL routing.
    """

    def _post(self, auth_client, data):
        """Call the view directly using force_authenticate + RequestFactory."""
        from rest_framework.test import APIRequestFactory
        from apps.social.views import BulkPostDetailView

        factory = APIRequestFactory()
        request = factory.post("/posts/bulk/", data, format="json")


        return request, BulkPostDetailView

    def test_bulk_returns_posts(self, user):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.social.views import BulkPostDetailView

        p1 = PostFactory(text_content="Post one")
        p2 = PostFactory(text_content="Post two")
        factory = APIRequestFactory()
        request = factory.post(
            "/posts/bulk/",
            {"post_ids": [str(p1.pk), str(p2.pk)]},
            format="json",
        )
        force_authenticate(request, user=user)
        view = BulkPostDetailView.as_view()
        response = view(request)
        response.render()
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert len(data) == 2
        returned_ids = {item["id"] for item in data}
        assert str(p1.pk) in returned_ids
        assert str(p2.pk) in returned_ids

    def test_bulk_filters_blocked_users(self, user):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.social.views import BulkPostDetailView

        blocked_author = UserFactory()
        visible_author = UserFactory()
        blocked_post = PostFactory(author=blocked_author)
        visible_post = PostFactory(author=visible_author)
        BlockRelationshipFactory(blocker=user, blocked=blocked_author)
        factory = APIRequestFactory()
        request = factory.post(
            "/posts/bulk/",
            {"post_ids": [str(blocked_post.pk), str(visible_post.pk)]},
            format="json",
        )
        force_authenticate(request, user=user)
        view = BulkPostDetailView.as_view()
        response = view(request)
        response.render()
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(visible_post.pk)

    def test_bulk_over_50_returns_400(self, user):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.social.views import BulkPostDetailView

        ids = [str(uuid.uuid4()) for _ in range(51)]
        factory = APIRequestFactory()
        request = factory.post("/posts/bulk/", {"post_ids": ids}, format="json")
        force_authenticate(request, user=user)
        view = BulkPostDetailView.as_view()
        response = view(request)
        response.render()
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_empty_list_returns_400(self, user):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.social.views import BulkPostDetailView

        factory = APIRequestFactory()
        request = factory.post("/posts/bulk/", {"post_ids": []}, format="json")
        force_authenticate(request, user=user)
        view = BulkPostDetailView.as_view()
        response = view(request)
        response.render()
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_missing_post_ids_returns_400(self, user):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.social.views import BulkPostDetailView

        factory = APIRequestFactory()
        request = factory.post("/posts/bulk/", {}, format="json")
        force_authenticate(request, user=user)
        view = BulkPostDetailView.as_view()
        response = view(request)
        response.render()
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_nonexistent_ids_returns_empty(self, user):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.social.views import BulkPostDetailView

        factory = APIRequestFactory()
        request = factory.post(
            "/posts/bulk/",
            {"post_ids": [str(uuid.uuid4()), str(uuid.uuid4())]},
            format="json",
        )
        force_authenticate(request, user=user)
        view = BulkPostDetailView.as_view()
        response = view(request)
        response.render()
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 0

    def test_bulk_filters_users_who_blocked_requester(self, user):
        """Posts by users who blocked the requester should be excluded."""
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.social.views import BulkPostDetailView

        blocker = UserFactory()
        post = PostFactory(author=blocker)
        BlockRelationshipFactory(blocker=blocker, blocked=user)
        factory = APIRequestFactory()
        request = factory.post(
            "/posts/bulk/",
            {"post_ids": [str(post.pk)]},
            format="json",
        )
        force_authenticate(request, user=user)
        view = BulkPostDetailView.as_view()
        response = view(request)
        response.render()
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 0
