from __future__ import annotations
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "bible"

router = DefaultRouter()

router.register(r"bookmarks", views.BookmarkViewSet, basename="bookmark")

router.register(r"highlights", views.HighlightViewSet, basename="highlight")

router.register(r"notes", views.NoteViewSet, basename="note")

urlpatterns = [
    path(
        "sections/",
        views.SegregatedSectionListView.as_view(),
        name="section-list",
    ),
    path(
        "sections/<uuid:section_id>/chapters/",
        views.ChapterListView.as_view(),
        name="chapter-list",
    ),
    path(
        "chapters/<uuid:chapter_id>/pages/",
        views.PageListView.as_view(),
        name="page-list",
    ),
    path(
        "pages/<uuid:page_id>/",
        views.PageDetailView.as_view(),
        name="page-detail",
    ),
    path(
        "pages/<uuid:page_id>/comments/",
        views.PageCommentCreateView.as_view(),
        name="page-comment-create",
    ),
    path(
        "search/",
        views.BibleSearchView.as_view(),
        name="search",
    ),
    path(
        "api-bible/<path:path>",
        views.ApiBibleProxyView.as_view(),
        name="api-bible-proxy",
    ),
    path(
        "api-bible/",
        views.ApiBibleProxyView.as_view(),
        name="api-bible-proxy-root",
    ),
    path("", include(router.urls)),
]
