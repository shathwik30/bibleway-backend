from __future__ import annotations
from django.urls import path
from .views import (
    BoostAnalyticsView,
    BoostRazorpayCreateOrderView,
    BoostRazorpayVerifyPaymentView,
    PostAnalyticsView,
    PostBoostCreateView,
    PostBoostListView,
    RecordViewView,
    UserAnalyticsView,
)

app_name = "analytics"

urlpatterns = [
    path("views/", RecordViewView.as_view(), name="record-view"),
    path(
        "posts/<uuid:post_id>/",
        PostAnalyticsView.as_view(),
        name="post-analytics",
    ),
    path("me/", UserAnalyticsView.as_view(), name="user-analytics"),
    path("boosts/", PostBoostCreateView.as_view(), name="boost-create"),
    path("boosts/list/", PostBoostListView.as_view(), name="boost-list"),
    path(
        "boosts/<uuid:boost_id>/analytics/",
        BoostAnalyticsView.as_view(),
        name="boost-analytics",
    ),
    # Razorpay (web boost payments)
    path(
        "boosts/razorpay/create-order/",
        BoostRazorpayCreateOrderView.as_view(),
        name="boost-razorpay-create-order",
    ),
    path(
        "boosts/razorpay/verify/",
        BoostRazorpayVerifyPaymentView.as_view(),
        name="boost-razorpay-verify",
    ),
]
