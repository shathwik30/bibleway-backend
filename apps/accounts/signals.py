from __future__ import annotations
from typing import Any
from django.db.models import F, Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from apps.common.utils import invalidate_blocked_user_cache
from .models import BlockRelationship, FollowRelationship, User


@receiver(post_save, sender=BlockRelationship)
def remove_follow_on_block(
    sender: type[BlockRelationship],
    instance: BlockRelationship,
    created: bool,
    **kwargs: Any,
) -> None:
    """When user A blocks user B, remove any follow relationships between them."""

    if created:
        FollowRelationship.objects.filter(
            Q(follower=instance.blocker, following=instance.blocked)
            | Q(follower=instance.blocked, following=instance.blocker)
        ).delete()


@receiver(post_save, sender=BlockRelationship)
@receiver(post_delete, sender=BlockRelationship)
def invalidate_block_cache(
    sender: type[BlockRelationship], instance: BlockRelationship, **kwargs: Any
) -> None:
    """Clear the blocked-user cache for both parties when a block changes."""

    invalidate_blocked_user_cache(instance.blocker_id)

    invalidate_blocked_user_cache(instance.blocked_id)


@receiver(post_save, sender=FollowRelationship)
def increment_follow_counts(
    sender: type[FollowRelationship],
    instance: FollowRelationship,
    created: bool,
    **kwargs: Any,
) -> None:

    if created:
        User.objects.filter(pk=instance.follower_id).update(
            following_count=F("following_count") + 1
        )
        User.objects.filter(pk=instance.following_id).update(
            follower_count=F("follower_count") + 1
        )


@receiver(post_delete, sender=FollowRelationship)
def decrement_follow_counts(
    sender: type[FollowRelationship], instance: FollowRelationship, **kwargs: Any
) -> None:

    User.objects.filter(pk=instance.follower_id).update(
        following_count=F("following_count") - 1
    )

    User.objects.filter(pk=instance.following_id).update(
        follower_count=F("follower_count") - 1
    )
