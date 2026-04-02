"""Signals to keep denormalized counters in sync.

Updates Post/Prayer reaction_count, comment_count and
User post_count, prayer_count on create/delete.
"""

from __future__ import annotations
from typing import Any
from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from .models import Comment, Post, Prayer, Reaction


def _update_reaction_count(instance: Reaction, delta: int) -> None:
    """Increment or decrement the reaction_count on the parent Post/Prayer."""

    ct = instance.content_type

    model_class = ct.model_class()

    if model_class in (Post, Prayer):
        model_class.objects.filter(pk=instance.object_id).update(
            reaction_count=F("reaction_count") + delta
        )


@receiver(post_save, sender=Reaction)
def increment_reaction_count(
    sender: type[Reaction], instance: Reaction, created: bool, **kwargs: Any
) -> None:
    if created:
        _update_reaction_count(instance, 1)


@receiver(post_delete, sender=Reaction)
def decrement_reaction_count(
    sender: type[Reaction], instance: Reaction, **kwargs: Any
) -> None:
    _update_reaction_count(instance, -1)


def _update_comment_count(instance: Comment, delta: int) -> None:
    """Increment or decrement the comment_count on the parent Post/Prayer."""

    ct = instance.content_type

    model_class = ct.model_class()

    if model_class in (Post, Prayer):
        model_class.objects.filter(pk=instance.object_id).update(
            comment_count=F("comment_count") + delta
        )


@receiver(post_save, sender=Comment)
def increment_comment_count(
    sender: type[Comment], instance: Comment, created: bool, **kwargs: Any
) -> None:
    if created:
        _update_comment_count(instance, 1)


@receiver(post_delete, sender=Comment)
def decrement_comment_count(
    sender: type[Comment], instance: Comment, **kwargs: Any
) -> None:
    _update_comment_count(instance, -1)


@receiver(post_save, sender=Post)
def increment_post_count(
    sender: type[Post], instance: Post, created: bool, **kwargs: Any
) -> None:
    if created:
        from apps.accounts.models import User

        User.objects.filter(pk=instance.author_id).update(
            post_count=F("post_count") + 1
        )


@receiver(post_delete, sender=Post)
def decrement_post_count(
    sender: type[Post], instance: Post, **kwargs: Any
) -> None:
    from apps.accounts.models import User

    User.objects.filter(pk=instance.author_id).update(post_count=F("post_count") - 1)


@receiver(post_save, sender=Prayer)
def increment_prayer_count(
    sender: type[Prayer], instance: Prayer, created: bool, **kwargs: Any
) -> None:
    if created:
        from apps.accounts.models import User

        User.objects.filter(pk=instance.author_id).update(
            prayer_count=F("prayer_count") + 1
        )


@receiver(post_delete, sender=Prayer)
def decrement_prayer_count(
    sender: type[Prayer], instance: Prayer, **kwargs: Any
) -> None:
    from apps.accounts.models import User

    User.objects.filter(pk=instance.author_id).update(
        prayer_count=F("prayer_count") - 1
    )
