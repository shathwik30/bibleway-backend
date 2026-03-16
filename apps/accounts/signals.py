from django.db.models import Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.common.utils import invalidate_blocked_user_cache

from .models import BlockRelationship, FollowRelationship


@receiver(post_save, sender=BlockRelationship)
def remove_follow_on_block(sender, instance, created, **kwargs):
    """When user A blocks user B, remove any follow relationships between them."""
    if created:
        FollowRelationship.objects.filter(
            Q(follower=instance.blocker, following=instance.blocked)
            | Q(follower=instance.blocked, following=instance.blocker)
        ).delete()


@receiver(post_save, sender=BlockRelationship)
@receiver(post_delete, sender=BlockRelationship)
def invalidate_block_cache(sender, instance, **kwargs):
    """Clear the blocked-user cache for both parties when a block changes."""
    invalidate_blocked_user_cache(instance.blocker_id)
    invalidate_blocked_user_cache(instance.blocked_id)
