from __future__ import annotations
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    BulkPostDetailView,
    CommentViewSet,
    MediaUploadView,
    PostViewSet,
    PrayerViewSet,
    ReplyViewSet,
    ReportCreateView,
    ReportListView,
)

app_name = "social"

router = DefaultRouter()

router.register(r"posts", PostViewSet, basename="post")

router.register(r"prayers", PrayerViewSet, basename="prayer")

router.register(r"comments", CommentViewSet, basename="comment")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "comments/<uuid:comment_pk>/replies/",
        ReplyViewSet.as_view({"get": "list", "post": "create"}),
        name="comment-replies-list",
    ),
    path(
        "comments/<uuid:comment_pk>/replies/<uuid:pk>/",
        ReplyViewSet.as_view({"delete": "destroy"}),
        name="comment-replies-detail",
    ),
    path("posts/bulk/", BulkPostDetailView.as_view(), name="bulk-post-detail"),
    path("media/upload/", MediaUploadView.as_view(), name="media-upload"),
    path("reports/", ReportCreateView.as_view(), name="report-create"),
    path("reports/pending/", ReportListView.as_view(), name="report-list-pending"),
]
