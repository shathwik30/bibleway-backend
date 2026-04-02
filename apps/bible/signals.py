from __future__ import annotations
from typing import Any
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import SegregatedPage


@receiver(pre_save, sender=SegregatedPage)
def track_content_change(
    sender: type[SegregatedPage], instance: SegregatedPage, **kwargs: Any
) -> None:
    """Track whether the content field has changed before saving."""

    if instance.pk:
        try:
            old_instance = SegregatedPage.objects.get(pk=instance.pk)
            instance._content_changed = old_instance.content != instance.content

        except SegregatedPage.DoesNotExist:
            instance._content_changed = True

    else:
        instance._content_changed = False


@receiver(post_save, sender=SegregatedPage)
def invalidate_translation_cache(
    sender: type[SegregatedPage], instance: SegregatedPage, created: bool, **kwargs: Any
) -> None:
    """When page content changes, delete cached translations to force re-translation."""

    if created:
        return

    content_changed: bool = getattr(instance, "_content_changed", False)

    if content_changed:
        instance.translations.all().delete()
