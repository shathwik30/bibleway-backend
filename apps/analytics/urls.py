from __future__ import annotations

from django.urls import path

from .views import (
    BoostAnalyticsView,
    PostAnalyticsView,
    PostBoostCreateView,
    PostBoostListView,
    UserAnalyticsView,
)

app_name = "analytics"

urlpatterns = [
    # Post analytics
    path(
        "posts/<uuid:post_id>/",
        PostAnalyticsView.as_view(),
        name="post-analytics",
    ),
    # User aggregate analytics
    path("me/", UserAnalyticsView.as_view(), name="user-analytics"),
    # Boosts
    path("boosts/", PostBoostCreateView.as_view(), name="boost-create"),
    path("boosts/list/", PostBoostListView.as_view(), name="boost-list"),
    path(
        "boosts/<uuid:boost_id>/analytics/",
        BoostAnalyticsView.as_view(),
        name="boost-analytics",
    ),
]
