from __future__ import annotations
from django.urls import path
from .views import (
    DownloadView,
    ProductDetailView,
    ProductListView,
    ProductSearchView,
    PurchaseCreateView,
    PurchaseListView,
    RazorpayCreateOrderView,
    RazorpayVerifyPaymentView,
    RazorpayWebhookView,
)

app_name = "shop"

urlpatterns = [
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/search/", ProductSearchView.as_view(), name="product-search"),
    path("products/<uuid:pk>/", ProductDetailView.as_view(), name="product-detail"),
    path("purchases/", PurchaseCreateView.as_view(), name="purchase-create"),
    path("purchases/list/", PurchaseListView.as_view(), name="purchase-list"),
    path(
        "downloads/<uuid:product_id>/",
        DownloadView.as_view(),
        name="download",
    ),
    # Razorpay (web payments)
    path(
        "razorpay/create-order/",
        RazorpayCreateOrderView.as_view(),
        name="razorpay-create-order",
    ),
    path(
        "razorpay/verify/",
        RazorpayVerifyPaymentView.as_view(),
        name="razorpay-verify",
    ),
    path(
        "razorpay/webhook/",
        RazorpayWebhookView.as_view(),
        name="razorpay-webhook",
    ),
]
