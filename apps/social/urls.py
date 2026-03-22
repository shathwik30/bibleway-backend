from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
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
    # Router-managed endpoints:
    #   /posts/                     – list (feed), create
    #   /posts/{pk}/                – retrieve, destroy
    #   /posts/{pk}/react/          – toggle reaction
    #   /posts/{pk}/comments/       – list / create comments
    #   /posts/{pk}/share/          – share deep-link data
    #   /prayers/                   – list (feed), create
    #   /prayers/{pk}/              – retrieve, destroy
    #   /prayers/{pk}/react/        – toggle reaction
    #   /prayers/{pk}/comments/     – list / create comments
    #   /comments/                  – list (with query params), create
    #   /comments/{pk}/             – destroy
    path("", include(router.urls)),
    # Nested replies under a comment:
    #   /comments/{comment_pk}/replies/       – list, create
    #   /comments/{comment_pk}/replies/{pk}/  – destroy
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
    # Media upload
    path("media/upload/", MediaUploadView.as_view(), name="media-upload"),
    # Reports
    path("reports/", ReportCreateView.as_view(), name="report-create"),
    path("reports/pending/", ReportListView.as_view(), name="report-list-pending"),
]
