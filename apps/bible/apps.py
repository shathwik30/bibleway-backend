from django.apps import AppConfig


class BibleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bible"
    verbose_name = "Bible"

    def ready(self):
        import apps.bible.signals  # noqa: F401
