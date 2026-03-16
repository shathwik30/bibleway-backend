from __future__ import annotations

from django.urls import path

from .views import (
    DownloadView,
    ProductDetailView,
    ProductListView,
    ProductSearchView,
    PurchaseCreateView,
    PurchaseListView,
)

app_name = "shop"

urlpatterns = [
    # Products
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/search/", ProductSearchView.as_view(), name="product-search"),
    path("products/<uuid:pk>/", ProductDetailView.as_view(), name="product-detail"),
    # Purchases
    path("purchases/", PurchaseCreateView.as_view(), name="purchase-create"),
    path("purchases/list/", PurchaseListView.as_view(), name="purchase-list"),
    # Downloads
    path(
        "downloads/<uuid:product_id>/",
        DownloadView.as_view(),
        name="download",
    ),
]
