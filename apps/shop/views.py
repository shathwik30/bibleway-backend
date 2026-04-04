from __future__ import annotations
import hashlib
import hmac
import json
import logging
from typing import Any
from uuid import UUID
from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
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
    RazorpayOrderCreateSerializer,
    RazorpayVerifySerializer,
)

from .services import DownloadService, ProductService, PurchaseService, RazorpayService


class ProductListView(BaseAPIView):
    """GET /shop/products/ -- list active products with optional ?category= filter.

    Supports ETag for 304 Not Modified based on latest product update time.
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._product_service = ProductService()

    def get(self, request: Request) -> Response:
        import hashlib
        from apps.shop.models import Product

        category: str | None = request.query_params.get("category")
        latest = (
            Product.objects.filter(is_active=True)
            .order_by("-updated_at")
            .values_list("updated_at", flat=True)
            .first()
        )
        etag_source = f"{category}:{latest}"
        etag = hashlib.md5(etag_source.encode()).hexdigest()

        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=304)

        products = self._product_service.list_active_products(category=category)
        resp = self.paginated_response(products, ProductListSerializer, request)
        resp["ETag"] = etag

        return resp


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

        self._download_service.record_download(
            user_id=request.user.id,
            product_id=product.pk,
            purchase_id=purchase_id,
        )
        download_url = DownloadService.generate_download_url(product=product)

        return self.success_response(
            data={"download_url": download_url},
            message="Download URL generated successfully.",
        )


logger = logging.getLogger(__name__)


class RazorpayCreateOrderView(BaseAPIView):
    """POST /shop/razorpay/create-order/ -- create a Razorpay order for a product.

    Returns the order_id, amount, currency, and razorpay_key needed by
    the frontend to open the Razorpay checkout widget.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [PurchaseThrottle]

    def post(self, request: Request) -> Response:
        serializer = RazorpayOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = RazorpayService()
        order_data = service.create_order(
            product_id=serializer.validated_data["product_id"],
            user_id=request.user.id,
        )

        return self.created_response(
            data=order_data,
            message="Razorpay order created successfully.",
        )


class RazorpayVerifyPaymentView(BaseAPIView):
    """POST /shop/razorpay/verify/ -- verify Razorpay payment and record purchase.

    Called by the frontend after the user completes payment in the
    Razorpay checkout widget.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [PurchaseThrottle]

    def post(self, request: Request) -> Response:
        serializer = RazorpayVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = RazorpayService()
        purchase = service.verify_payment(
            user_id=request.user.id,
            product_id=data["product_id"],
            razorpay_order_id=data["razorpay_order_id"],
            razorpay_payment_id=data["razorpay_payment_id"],
            razorpay_signature=data["razorpay_signature"],
        )

        out = PurchaseSerializer(purchase)

        return self.created_response(
            data=out.data,
            message="Payment verified and purchase recorded successfully.",
        )


class RazorpayWebhookView(BaseAPIView):
    """POST /shop/razorpay/webhook/ -- handle Razorpay server-to-server webhooks.

    Razorpay signs the webhook body with HMAC-SHA256 using the webhook secret.
    This endpoint acts as a fallback to catch payments that the frontend
    verify flow may have missed (e.g. network issues after payment).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")

        if not webhook_secret:
            logger.warning(
                "Razorpay webhook received but RAZORPAY_WEBHOOK_SECRET not configured."
            )
            return Response(status=200)

        signature = request.META.get("HTTP_X_RAZORPAY_SIGNATURE", "")
        body = request.body

        expected = hmac.new(
            webhook_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            logger.warning("Razorpay webhook signature mismatch.")
            return Response(status=400)

        payload = json.loads(body)
        event = payload.get("event", "")

        if event == "payment.captured":
            payment_entity = (
                payload.get("payload", {}).get("payment", {}).get("entity", {})
            )
            payment_id = payment_entity.get("id", "")
            order_id = payment_entity.get("order_id", "")
            notes = payment_entity.get("notes", {})
            product_id = notes.get("product_id", "")
            user_id = notes.get("user_id", "")

            if payment_id and order_id and product_id and user_id:
                from .models import Product, Purchase

                if not Purchase.objects.filter(transaction_id=payment_id).exists():
                    logger.info(
                        "Razorpay webhook: recording missed payment %s for product %s",
                        payment_id,
                        product_id,
                    )
                    try:
                        product = Product.objects.get(pk=product_id, is_active=True)
                        Purchase.objects.create(
                            user_id=user_id,
                            product=product,
                            platform=Purchase.Platform.WEB,
                            receipt_data="",
                            transaction_id=payment_id,
                            razorpay_order_id=order_id,
                            razorpay_payment_id=payment_id,
                            is_validated=True,
                        )
                        from django.db.models import F

                        Product.objects.filter(pk=product_id).update(
                            download_count=F("download_count") + 1
                        )
                    except Exception:
                        logger.exception(
                            "Razorpay webhook: failed to process payment %s", payment_id
                        )

        return Response(status=200)
