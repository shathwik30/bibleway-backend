from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.common.exceptions import BadRequestError, ForbiddenError
from apps.common.throttles import PurchaseRateThrottle as PurchaseThrottle
from apps.common.views import BaseAPIView

from .models import Purchase
from .serializers import (
    ProductDetailSerializer,
    ProductListSerializer,
    PurchaseCreateSerializer,
    PurchaseSerializer,
)
from .services import DownloadService, ProductService, PurchaseService


# ---------------------------------------------------------------------------
# Product views
# ---------------------------------------------------------------------------


class ProductListView(BaseAPIView):
    """GET /shop/products/ -- list active products with optional ?category= filter."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._product_service = ProductService()

    def get(self, request: Request) -> Response:
        category: str | None = request.query_params.get("category")
        products = self._product_service.list_active_products(category=category)
        return self.paginated_response(products, ProductListSerializer, request)


class ProductDetailView(BaseAPIView):
    """GET /shop/products/<uuid:pk>/ -- retrieve product detail."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._product_service = ProductService()

    def get(self, request: Request, pk: UUID) -> Response:
        product = self._product_service.get_product_detail(product_id=pk)
        serializer = ProductDetailSerializer(
            product,
            context={"request": request},
        )
        return self.success_response(data=serializer.data)


class ProductSearchView(BaseAPIView):
    """GET /shop/products/search/?q= -- search products by keyword."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._product_service = ProductService()

    def get(self, request: Request) -> Response:
        query: str = request.query_params.get("q", "")
        if not query.strip():
            raise BadRequestError(detail="Query parameter 'q' is required.")

        products = self._product_service.search_products(query=query)
        return self.paginated_response(products, ProductListSerializer, request)


# ---------------------------------------------------------------------------
# Purchase views
# ---------------------------------------------------------------------------


class PurchaseCreateView(BaseAPIView):
    """POST /shop/purchases/ -- verify and record an in-app purchase."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [PurchaseThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._purchase_service = PurchaseService()

    def post(self, request: Request) -> Response:
        serializer = PurchaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        purchase = self._purchase_service.verify_purchase(
            user_id=request.user.id,
            product_id=data["product_id"],
            platform=data["platform"],
            receipt_data=data["receipt_data"],
            transaction_id=data["transaction_id"],
        )

        out = PurchaseSerializer(purchase)
        return self.created_response(
            data=out.data,
            message="Purchase verified successfully.",
        )


class PurchaseListView(BaseAPIView):
    """GET /shop/purchases/ -- list current user's purchases."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._purchase_service = PurchaseService()

    def get(self, request: Request) -> Response:
        purchases = self._purchase_service.list_user_purchases(
            user_id=request.user.id,
        )
        return self.paginated_response(purchases, PurchaseSerializer, request)


# ---------------------------------------------------------------------------
# Download view
# ---------------------------------------------------------------------------


class DownloadThrottle(UserRateThrottle):
    """Rate limit download URL generation to prevent flooding."""

    rate = "30/hour"


class DownloadView(BaseAPIView):
    """GET /shop/downloads/<uuid:product_id>/ -- generate a download URL.

    For free products, anyone authenticated can download.
    For paid products, the user must have a validated purchase.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [DownloadThrottle]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._product_service = ProductService()
        self._download_service = DownloadService()

    def get(self, request: Request, product_id: UUID) -> Response:
        product = self._product_service.get_product_detail(product_id=product_id)

        # For paid products, verify the user has purchased
        purchase_id: UUID | None = None
        if not product.is_free:
            purchase = Purchase.objects.filter(
                user=request.user,
                product=product,
                is_validated=True,
            ).first()
            if purchase is None:
                raise ForbiddenError(
                    detail="You must purchase this product before downloading."
                )
            purchase_id = purchase.pk

        # Record the download
        self._download_service.record_download(
            user_id=request.user.id,
            product_id=product.pk,
            purchase_id=purchase_id,
        )

        # Generate the pre-signed URL
        download_url = DownloadService.generate_download_url(product=product)

        return self.success_response(
            data={"download_url": download_url},
            message="Download URL generated successfully.",
        )
