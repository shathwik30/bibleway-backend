from __future__ import annotations
import logging
from uuid import UUID
import razorpay
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q, QuerySet
from rest_framework.exceptions import ValidationError
from apps.common.exceptions import BadRequestError, ConflictError, NotFoundError
from apps.common.services import BaseService
from .models import Download, Product, Purchase
from .validators import validate_apple_receipt, validate_google_receipt

logger = logging.getLogger(__name__)


class ProductService(BaseService[Product]):
    """Business logic for browsing and retrieving digital products."""

    model = Product

    def get_queryset(self) -> QuerySet[Product]:
        return super().get_queryset().filter(is_active=True)

    def list_active_products(
        self,
        *,
        category: str | None = None,
    ) -> QuerySet[Product]:
        """Return active products, optionally filtered by category."""
        qs = self.get_queryset()

        if category:
            qs = qs.filter(category=category)

        return qs

    def get_product_detail(self, *, product_id: UUID) -> Product:
        """Retrieve a single active product by its primary key."""

        try:
            return self.get_queryset().get(pk=product_id)

        except Product.DoesNotExist:
            raise NotFoundError(detail=f"Product with id '{product_id}' not found.")

    def search_products(self, *, query: str) -> QuerySet[Product]:
        """Search active products by title or description (case-insensitive)."""

        if not query or not query.strip():
            raise BadRequestError(detail="Search query must not be empty.")

        return self.get_queryset().filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )


class PurchaseService(BaseService[Purchase]):
    """Business logic for verifying and recording in-app purchases."""

    model = Purchase

    def get_queryset(self) -> QuerySet[Purchase]:
        return super().get_queryset().select_related("product")

    @transaction.atomic
    def verify_purchase(
        self,
        *,
        user_id: UUID,
        product_id: UUID,
        platform: str,
        receipt_data: str,
        transaction_id: str,
    ) -> Purchase:
        """Validate a purchase receipt and create the purchase record.
        - Validates the receipt with the appropriate store (Apple/Google).
        - Checks the transaction_id is unique (prevents replay).
        - Creates a Purchase record only after successful validation.
        - Increments the product's purchase_count atomically.
        """

        try:
            product = Product.objects.get(pk=product_id, is_active=True)

        except Product.DoesNotExist:
            raise NotFoundError(
                detail=f"Product with id '{product_id}' not found or inactive."
            )

        if Purchase.objects.filter(transaction_id=transaction_id).exists():
            raise ConflictError(
                detail=f"Transaction '{transaction_id}' has already been processed."
            )

        try:
            if platform == Purchase.Platform.IOS:
                validate_apple_receipt(
                    receipt_data,
                    expected_product_id=product.apple_product_id or "",
                )

            elif platform == Purchase.Platform.ANDROID:
                validate_google_receipt(
                    product_id=product.google_product_id or product.apple_product_id,
                    purchase_token=receipt_data,
                )

            elif platform == Purchase.Platform.WEB:
                # Razorpay validation is done in RazorpayService.verify_payment()
                # before calling verify_purchase, so nothing extra needed here.
                pass

            else:
                raise ValidationError(f"Unsupported platform: {platform}")

        except ValueError as exc:
            raise ValidationError(f"Receipt validation failed: {exc}")

        try:
            purchase = Purchase.objects.create(
                user_id=user_id,
                product=product,
                platform=platform,
                receipt_data=receipt_data,
                transaction_id=transaction_id,
                is_validated=True,
            )

        except IntegrityError:
            raise ConflictError(
                detail=f"Transaction '{transaction_id}' has already been processed."
            )

        Product.objects.filter(pk=product_id).update(
            download_count=F("download_count") + 1
        )
        logger.info(
            "Purchase verified: user=%s product=%s txn=%s",
            user_id,
            product_id,
            transaction_id,
        )

        return purchase

    def list_user_purchases(self, *, user_id: UUID) -> QuerySet[Purchase]:
        """Return all purchases for a given user, newest first."""

        return self.get_queryset().filter(user_id=user_id)


class DownloadService(BaseService[Download]):
    """Business logic for recording and serving product downloads."""

    model = Download

    def get_queryset(self) -> QuerySet[Download]:
        return super().get_queryset().select_related("product", "purchase")

    def record_download(
        self,
        *,
        user_id: UUID,
        product_id: UUID,
        purchase_id: UUID | None = None,
    ) -> Download:
        """Record a download event for a user.
        For free products, ``purchase_id`` may be ``None``.
        For paid products, the purchase must exist and belong to the user.
        """

        try:
            product = Product.objects.get(pk=product_id, is_active=True)

        except Product.DoesNotExist:
            raise NotFoundError(
                detail=f"Product with id '{product_id}' not found or inactive."
            )

        if not product.is_free and purchase_id is None:
            raise BadRequestError(
                detail="A purchase is required to download a paid product."
            )

        if purchase_id is not None:
            if not Purchase.objects.filter(
                pk=purchase_id, user_id=user_id, product_id=product_id
            ).exists():
                raise NotFoundError(
                    detail="Purchase not found or does not belong to this user."
                )

        download = Download.objects.create(
            user_id=user_id,
            product_id=product_id,
            purchase_id=purchase_id,
        )

        return download

    def list_user_downloads(self, *, user_id: UUID) -> QuerySet[Download]:
        """Return all downloads for a given user, newest first."""

        return self.get_queryset().filter(user_id=user_id)

    @staticmethod
    def generate_download_url(*, product: Product) -> str:
        """Generate a pre-signed URL for the product file.
        The ``PrivateMediaStorage`` backend produces a time-limited
        pre-signed S3 URL when ``url`` is called (``querystring_auth=True``).
        NOTE: Callers should apply throttling/rate-limiting to prevent
        excessive URL generation. The DownloadView uses DRF throttle classes
        for this purpose.
        """

        if not product.product_file:
            raise BadRequestError(
                detail="This product does not have a downloadable file."
            )

        return product.product_file.url


class RazorpayService:
    """Handles Razorpay order creation and payment verification for web purchases."""

    def __init__(self) -> None:
        key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
        key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")

        if not key_id or not key_secret:
            raise BadRequestError(detail="Razorpay credentials are not configured.")

        self._client = razorpay.Client(auth=(key_id, key_secret))

    def create_order(self, *, product_id: UUID, user_id: UUID) -> dict:
        """Create a Razorpay order for a product.

        Returns a dict with order_id, amount, currency, and razorpay_key
        that the frontend needs to open the checkout widget.
        """

        try:
            product = Product.objects.get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            raise NotFoundError(
                detail=f"Product with id '{product_id}' not found or inactive."
            )

        if product.is_free:
            raise BadRequestError(
                detail="Cannot create a payment order for a free product."
            )

        if not product.price:
            raise BadRequestError(
                detail="This product does not have a web price configured."
            )

        amount_paise = int(product.price * 100)

        order_data = self._client.order.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "notes": {
                    "product_id": str(product.id),
                    "product_title": product.title,
                    "user_id": str(user_id),
                },
            }
        )

        return {
            "order_id": order_data["id"],
            "amount": amount_paise,
            "currency": "INR",
            "razorpay_key": getattr(settings, "RAZORPAY_KEY_ID", ""),
            "product_id": str(product.id),
            "product_title": product.title,
        }

    @transaction.atomic
    def verify_payment(
        self,
        *,
        user_id: UUID,
        product_id: UUID,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> Purchase:
        """Verify the Razorpay payment signature and record the purchase.

        Uses the razorpay client's built-in utility to verify the signature,
        then delegates to PurchaseService to create the record.
        """

        try:
            self._client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": razorpay_order_id,
                    "razorpay_payment_id": razorpay_payment_id,
                    "razorpay_signature": razorpay_signature,
                }
            )
        except razorpay.errors.SignatureVerificationError:
            raise ValidationError("Razorpay payment signature verification failed.")

        try:
            product = Product.objects.get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            raise NotFoundError(
                detail=f"Product with id '{product_id}' not found or inactive."
            )

        if Purchase.objects.filter(transaction_id=razorpay_payment_id).exists():
            raise ConflictError(
                detail=f"Payment '{razorpay_payment_id}' has already been processed."
            )

        try:
            purchase = Purchase.objects.create(
                user_id=user_id,
                product=product,
                platform=Purchase.Platform.WEB,
                receipt_data="",
                transaction_id=razorpay_payment_id,
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                is_validated=True,
            )
        except IntegrityError:
            raise ConflictError(
                detail=f"Payment '{razorpay_payment_id}' has already been processed."
            )

        Product.objects.filter(pk=product_id).update(
            download_count=F("download_count") + 1
        )

        logger.info(
            "Razorpay purchase verified: user=%s product=%s payment=%s",
            user_id,
            product_id,
            razorpay_payment_id,
        )

        return purchase
