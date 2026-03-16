from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import SegregatedPage


@receiver(pre_save, sender=SegregatedPage)
def track_content_change(sender, instance, **kwargs):
    """Track whether the content field has changed before saving."""
    if instance.pk:
        try:
            old_instance = SegregatedPage.objects.get(pk=instance.pk)
            instance._content_changed = old_instance.content != instance.content
        except SegregatedPage.DoesNotExist:
            instance._content_changed = True
    else:
        # New instance, no translations to invalidate.
        instance._content_changed = False


@receiver(post_save, sender=SegregatedPage)
def invalidate_translation_cache(sender, instance, created, **kwargs):
    """When page content changes, delete cached translations to force re-translation."""
    if created:
        return

    content_changed = getattr(instance, "_content_changed", False)
    if content_changed:
        instance.translations.all().delete()
