from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    """Liveness probe for Railway and uptime monitors."""
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "ok"
    except Exception:
        db_status = "error"

    return JsonResponse({"status": "ok", "db": db_status})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health_check, name="health-check"),
    path("api/v1/accounts/", include("apps.accounts.urls")),
    path("api/v1/social/", include("apps.social.urls")),
    path("api/v1/bible/", include("apps.bible.urls")),
    path("api/v1/shop/", include("apps.shop.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/analytics/", include("apps.analytics.urls")),
    path("api/v1/verse-of-day/", include("apps.verse_of_day.urls")),
    path("api/v1/admin/", include("apps.admin_panel.urls")),
]

if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
