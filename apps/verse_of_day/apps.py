from django.apps import AppConfig


class VerseOfDayConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"

    name = "apps.verse_of_day"

    verbose_name = "Verse of the Day"
